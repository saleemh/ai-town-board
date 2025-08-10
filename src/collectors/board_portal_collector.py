"""North Castle Board Portal Collector

Handles authentication, session management, and document collection
from the North Castle board portal system.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiofiles
import httpx
from bs4 import BeautifulSoup

from .auth_manager import AuthManager
from .document_detector import DocumentDetector
from .session_manager import SessionManager
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processors.document_processor import DocumentProcessor


logger = logging.getLogger(__name__)


class BoardPortalCollector:
    """Collects meeting documents from North Castle board portal."""
    
    def __init__(self, config: Dict):
        """Initialize collector with configuration.
        
        Args:
            config: Configuration dictionary containing board portal settings
        """
        self.config = config
        self.base_url = config['board_portal']['base_url']
        self.timeout = config['board_portal'].get('timeout', 30)
        self.retry_attempts = config['board_portal'].get('retry_attempts', 3)
        self.data_directory = Path(config['storage']['data_directory'])
        
        # Initialize components
        self.auth_manager = AuthManager(config)
        self.session_manager = SessionManager(config)
        self.document_detector = DocumentDetector(config)
        self.document_processor = DocumentProcessor(config)
        
        # HTTP client with session persistence
        self.client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
            
    async def collect_meeting_data(self, meeting_date: str, refresh: bool = False) -> Dict:
        """Collect all documents for a specific meeting date.
        
        Args:
            meeting_date: Date in YYYY-MM-DD format
            refresh: If True, re-download existing documents
            
        Returns:
            Dictionary with collection results and metadata
        """
        logger.info(f"Starting collection for meeting date: {meeting_date}")
        
        try:
            # Parse and validate date
            parsed_date = datetime.strptime(meeting_date, '%Y-%m-%d')
            
            # Setup meeting directory
            meeting_dir = self._setup_meeting_directory(meeting_date)
            
            # Check if already collected and not refreshing
            if not refresh and self._is_already_collected(meeting_dir):
                logger.info(f"Meeting {meeting_date} already collected. Use --refresh to update.")
                return await self._load_existing_metadata(meeting_dir)
            
            # Authenticate and get session
            await self._ensure_authenticated()
            
            # Navigate to meeting date
            meeting_url = await self._find_meeting_url(parsed_date)
            if not meeting_url:
                logger.warning(f"No meeting found for date {meeting_date}")
                return {'status': 'no_meeting', 'date': meeting_date}
            
            # Discover available documents
            documents = await self.document_detector.discover_documents(
                self.client, meeting_url
            )
            
            # Download documents
            download_results = await self._download_documents(
                documents, meeting_dir, refresh
            )
            
            # Process documents (convert to markdown)
            processed_results = await self.document_processor.process_documents(
                download_results, meeting_dir
            )
            
            # Parse agenda items
            agenda_items = await self._parse_agenda_items(processed_results)
            
            # Create metadata
            metadata = {
                'meeting_date': meeting_date,
                'meeting_type': 'regular',  # TODO: detect meeting type
                'collection_timestamp': datetime.utcnow().isoformat() + 'Z',
                'board_portal_url': meeting_url,
                'documents': processed_results,
                'agenda_items': agenda_items,
                'status': 'completed'
            }
            
            # Save metadata
            await self._save_metadata(meeting_dir, metadata)
            
            logger.info(f"Successfully collected {len(processed_results)} documents for {meeting_date}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error collecting meeting data for {meeting_date}: {e}")
            raise
            
    async def collect_date_range(
        self, 
        start_date: str, 
        end_date: str, 
        refresh: bool = False
    ) -> Dict[str, Dict]:
        """Collect documents for a range of dates.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            refresh: If True, re-download existing documents
            
        Returns:
            Dictionary mapping dates to collection results
        """
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        results = {}
        current_date = start_dt
        
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            try:
                results[date_str] = await self.collect_meeting_data(date_str, refresh)
            except Exception as e:
                logger.error(f"Failed to collect data for {date_str}: {e}")
                results[date_str] = {'status': 'error', 'error': str(e)}
                
            current_date += timedelta(days=1)
            
        return results
        
    async def discover_available_meetings(self) -> List[Dict]:
        """Discover all available meetings from the board portal.
        
        Returns:
            List of meeting information dictionaries
        """
        logger.info("Discovering available meetings from board portal")
        
        try:
            # Ensure we're authenticated
            await self._ensure_authenticated()
            
            # Navigate to agendas page first
            agendas_url = urljoin(self.base_url, '/Agendas')
            response = await self.client.get(agendas_url)
            response.raise_for_status()
            
            # Try to find AJAX endpoints for meeting data
            meetings = []
            
            # Common API endpoints for CivicClerk systems
            # Based on the debug output, let's try POST requests and different endpoint patterns
            api_endpoints = [
                ('/Agendas/GetAgendas', 'POST'),
                ('/Agendas/Search', 'POST'), 
                ('/Agendas/RefreshList', 'POST'),
                ('/Agendas/LoadAgendas', 'POST'),
                ('/API/Agendas/Search', 'POST'),
                ('/Meeting/Search', 'POST'),
                ('/Agendas/GetAgendas', 'GET'),
                ('/API/Agendas', 'GET'),
                ('/API/Meetings', 'GET'),
                ('/Meeting/GetMeetings', 'GET')
            ]
            
            for endpoint_info in api_endpoints:
                try:
                    endpoint, method = endpoint_info
                    api_url = urljoin(self.base_url, endpoint)
                    logger.debug(f"Trying API endpoint: {method} {api_url}")
                    
                    # Try different parameter combinations based on the JS variables we saw
                    if method == 'POST':
                        # For POST requests, send data as form data
                        data_to_try = [
                            {'page': 0, 'keyword': '', 'startDate': '01/01/2020', 'endDate': '12/31/2025'},
                            {'page': 0, 'keyword': '', 'startDate': '01/01/2000', 'endDate': '01/01/2050'},
                            {'page': 0},
                            {},
                        ]
                        
                        for data in data_to_try:
                            api_response = await self.client.post(
                                api_url, 
                                data=data,
                                headers={'Content-Type': 'application/x-www-form-urlencoded'}
                            )
                            if api_response.status_code == 200:
                                if await self._try_parse_response(api_response, endpoint, meetings):
                                    break
                    else:
                        # For GET requests, use query parameters
                        params_to_try = [
                            {},  # No parameters
                            {'page': 0, 'keyword': '', 'startDate': '01/01/2020', 'endDate': '12/31/2025'},
                            {'start': '2020-01-01', 'end': '2025-12-31'},
                            {'limit': 50, 'offset': 0},
                        ]
                        
                        for params in params_to_try:
                            api_response = await self.client.get(api_url, params=params)
                            if api_response.status_code == 200:
                                if await self._try_parse_response(api_response, endpoint, meetings):
                                    break
                                
                    if meetings:
                        break  # Found meetings, stop trying other endpoints
                        
                except Exception as e:
                    logger.debug(f"API endpoint {endpoint} failed: {e}")
                    continue
            
            # If API endpoints didn't work, try date-based URL pattern we discovered
            if not meetings:
                logger.info("API endpoints failed, trying date-based URL discovery")
                meetings = await self._discover_meetings_by_date_range()
                
            # If that didn't work, fall back to HTML parsing
            if not meetings:
                soup = BeautifulSoup(response.text, 'html.parser')
                meeting_links = soup.find_all('a', href=True)
                
                for link in meeting_links:
                    href = link.get('href')
                    text = link.get_text().strip()
                    
                    # Skip if no text or href
                    if not text or not href:
                        continue
                        
                    # Look for patterns that suggest this is a meeting link
                    text_lower = text.lower()
                    href_lower = href.lower()
                    
                    # Check if this looks like a meeting
                    is_meeting = (
                        any(word in text_lower for word in ['agenda', 'meeting', 'board', 'town board']) or
                        any(word in href_lower for word in ['agenda', 'meeting', 'board']) or
                        # Look for date patterns in text
                        self._extract_date_from_text(text)
                    )
                    
                    if is_meeting:
                        # Try to extract date from the text or URL
                        meeting_date = self._extract_date_from_text(text) or self._extract_date_from_url(href)
                        
                        if meeting_date:
                            meeting_info = {
                                'date': meeting_date,
                                'title': text,
                                'url': urljoin(self.base_url, href),
                                'type': self._classify_meeting_type(text)
                            }
                            meetings.append(meeting_info)
            
            # Remove duplicates and sort by date (most recent first)
            unique_meetings = {}
            for meeting in meetings:
                key = meeting['date']
                if key not in unique_meetings or len(meeting['title']) > len(unique_meetings[key]['title']):
                    unique_meetings[key] = meeting
                    
            sorted_meetings = sorted(unique_meetings.values(), 
                                   key=lambda x: x['date'], reverse=True)
            
            logger.info(f"Found {len(sorted_meetings)} unique meetings")
            return sorted_meetings
            
        except Exception as e:
            logger.error(f"Error discovering meetings: {e}")
            raise
            
    async def _try_parse_response(self, response: httpx.Response, endpoint: str, meetings: List[Dict]) -> bool:
        """Try to parse API response for meeting data.
        
        Args:
            response: HTTP response object
            endpoint: API endpoint name
            meetings: List to append discovered meetings to
            
        Returns:
            True if meetings were found and parsed
        """
        try:
            # Try JSON first
            try:
                data = response.json()
                if isinstance(data, list) and data:
                    logger.info(f"Found {len(data)} meetings from JSON response at {endpoint}")
                    meetings.extend(self._parse_api_meetings(data))
                    return True
                elif isinstance(data, dict) and ('meetings' in data or 'agendas' in data):
                    meeting_list = data.get('meetings', data.get('agendas', []))
                    logger.info(f"Found {len(meeting_list)} meetings from JSON response at {endpoint}")
                    meetings.extend(self._parse_api_meetings(meeting_list))
                    return True
            except:
                pass
                
            # Try HTML parsing
            content = response.text
            if 'meeting' in content.lower() or 'agenda' in content.lower():
                soup = BeautifulSoup(content, 'html.parser')
                
                # Look for table rows or list items that might contain meeting data
                rows = soup.find_all('tr') + soup.find_all('li') + soup.find_all('div', class_=lambda x: x and 'meeting' in x.lower())
                
                for row in rows:
                    text = row.get_text().strip()
                    if text and self._extract_date_from_text(text):
                        # Found potential meeting data
                        logger.debug(f"Found potential meeting HTML at {endpoint}: {text[:100]}")
                        # This would need more specific parsing based on the actual HTML structure
                        
            return False
            
        except Exception as e:
            logger.debug(f"Failed to parse response from {endpoint}: {e}")
            return False
            
    async def _discover_meetings_by_date_range(self) -> List[Dict]:
        """Discover meetings by testing date-based URLs.
        
        Returns:
            List of meeting dictionaries found by checking date URLs
        """
        meetings = []
        from datetime import datetime, timedelta
        
        # Check the last 6 months and next 3 months for meetings
        start_date = datetime.now() - timedelta(days=180)  # 6 months ago
        end_date = datetime.now() + timedelta(days=90)     # 3 months ahead
        
        current_date = start_date
        test_count = 0
        max_tests = 30  # Limit to avoid too many requests
        
        logger.info(f"Testing date-based URLs from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        while current_date <= end_date and test_count < max_tests:
            # Test first and third Monday of each month (common meeting days)
            if current_date.weekday() == 0:  # Monday
                day_of_month = current_date.day
                if day_of_month <= 7 or (15 <= day_of_month <= 21):  # First or third Monday
                    date_str = current_date.strftime('%Y-%m-%d')
                    
                    try:
                        # Test the URL pattern we found: /Agendas?date=YYYY-MM-DD
                        test_url = f"{self.base_url}/Agendas?date={date_str}"
                        response = await self.client.get(test_url)
                        
                        if response.status_code == 200:
                            # Parse the response to see if it has meeting content
                            soup = BeautifulSoup(response.text, 'html.parser')
                            
                            # Look for signs this is a real meeting page
                            page_text = soup.get_text().lower()
                            
                            # Check for meeting-specific content
                            meeting_indicators = [
                                'agenda', 'meeting', 'minutes', 'board meeting',
                                'town board', 'call to order', 'resolution'
                            ]
                            
                            has_meeting_content = any(indicator in page_text for indicator in meeting_indicators)
                            
                            # Also check for document links or downloads
                            doc_links = soup.find_all('a', href=lambda x: x and ('.pdf' in x.lower() or 'download' in x.lower()))
                            
                            if has_meeting_content or doc_links:
                                logger.info(f"Found meeting content for {date_str}")
                                
                                # Extract meeting title from the page
                                title_elem = soup.find('h1') or soup.find('title')
                                title = title_elem.get_text().strip() if title_elem else f"Board Meeting - {date_str}"
                                
                                meeting_info = {
                                    'date': date_str,
                                    'title': title,
                                    'url': test_url,
                                    'type': self._classify_meeting_type(title),
                                    'document_count': len(doc_links)
                                }
                                meetings.append(meeting_info)
                                
                        test_count += 1
                        
                    except Exception as e:
                        logger.debug(f"Failed to test date {date_str}: {e}")
                        
            # Move to next day
            current_date += timedelta(days=1)
            
        logger.info(f"Found {len(meetings)} meetings through date-based discovery")
        return meetings
            
    def _parse_api_meetings(self, meeting_data: List[Dict]) -> List[Dict]:
        """Parse meeting data from API response.
        
        Args:
            meeting_data: List of meeting dictionaries from API
            
        Returns:
            List of normalized meeting dictionaries
        """
        meetings = []
        
        for item in meeting_data:
            try:
                # Common fields in CivicClerk APIs
                meeting_id = item.get('Id', item.get('id', item.get('meetingId')))
                title = item.get('Title', item.get('title', item.get('name', 'Meeting')))
                
                # Date extraction from various possible fields
                date_str = (item.get('MeetingDate') or item.get('meetingDate') or 
                           item.get('Date') or item.get('date') or 
                           item.get('StartDate') or item.get('startDate'))
                
                if date_str:
                    # Parse the date (might be in various formats)
                    meeting_date = self._parse_api_date(date_str)
                    if meeting_date:
                        # Build meeting URL
                        meeting_url = self._build_meeting_url(meeting_id, item)
                        
                        meeting_info = {
                            'date': meeting_date,
                            'title': title,
                            'url': meeting_url,
                            'type': self._classify_meeting_type(title),
                            'id': meeting_id,
                            'raw_data': item  # Keep original for debugging
                        }
                        meetings.append(meeting_info)
                        
            except Exception as e:
                logger.debug(f"Failed to parse meeting item: {e}")
                continue
                
        return meetings
        
    def _parse_api_date(self, date_str: str) -> Optional[str]:
        """Parse date from API response into YYYY-MM-DD format.
        
        Args:
            date_str: Date string from API
            
        Returns:
            Date in YYYY-MM-DD format or None
        """
        from datetime import datetime
        
        # Common date formats from CivicClerk APIs
        date_formats = [
            '%Y-%m-%dT%H:%M:%S',  # ISO format
            '%Y-%m-%dT%H:%M:%S.%f',  # ISO with microseconds
            '%m/%d/%Y',  # MM/DD/YYYY
            '%Y-%m-%d',  # YYYY-MM-DD
            '%m-%d-%Y',  # MM-DD-YYYY
        ]
        
        # Handle .NET style dates like "/Date(1234567890000)/"
        if date_str.startswith('/Date(') and date_str.endswith(')/'):
            try:
                timestamp = int(date_str[6:-2])  # Extract timestamp
                dt = datetime.fromtimestamp(timestamp / 1000)  # Convert from milliseconds
                return dt.strftime('%Y-%m-%d')
            except:
                pass
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
                
        # Try to extract date using our existing method
        return self._extract_date_from_text(date_str)
        
    def _build_meeting_url(self, meeting_id: Optional[str], meeting_data: Dict) -> str:
        """Build the URL for accessing a specific meeting.
        
        Args:
            meeting_id: Meeting ID
            meeting_data: Raw meeting data
            
        Returns:
            URL to access the meeting
        """
        if meeting_id:
            # Try common URL patterns
            possible_paths = [
                f'/Agendas/Details/{meeting_id}',
                f'/Meeting/{meeting_id}',
                f'/Agenda/{meeting_id}',
                f'/Agendas/{meeting_id}'
            ]
            
            # Use the first pattern for now - we can refine this based on testing
            return urljoin(self.base_url, possible_paths[0])
        else:
            # Fallback to agendas page
            return urljoin(self.base_url, '/Agendas')
            
    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Extract date from meeting text in YYYY-MM-DD format.
        
        Args:
            text: Text to search for dates
            
        Returns:
            Date string in YYYY-MM-DD format or None
        """
        
        # Common date patterns
        patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY or M/D/YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY or M-D-YYYY
            r'(\d{4})/(\d{1,2})/(\d{1,2})',  # YYYY/MM/DD
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',  # Month DD, YYYY
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})',  # Mon DD, YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    
                    if len(groups) == 3:
                        if groups[0].isdigit() and len(groups[0]) == 4:  # YYYY format
                            year, month, day = groups
                        elif groups[2].isdigit() and len(groups[2]) == 4:  # Year at end
                            if groups[0].isdigit():  # MM/DD/YYYY
                                month, day, year = groups
                            else:  # Month name
                                month_name, day, year = groups
                                month_map = {
                                    'january': '01', 'february': '02', 'march': '03', 'april': '04',
                                    'may': '05', 'june': '06', 'july': '07', 'august': '08',
                                    'september': '09', 'october': '10', 'november': '11', 'december': '12',
                                    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                                    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
                                    'oct': '10', 'nov': '11', 'dec': '12'
                                }
                                month = month_map.get(month_name.lower())
                                if not month:
                                    continue
                        else:
                            continue
                            
                        # Normalize to YYYY-MM-DD
                        year = int(year)
                        month = int(month) if month.isdigit() else int(month)
                        day = int(day)
                        
                        # Validate date
                        datetime(year, month, day)
                        return f"{year:04d}-{month:02d}-{day:02d}"
                        
                except (ValueError, TypeError):
                    continue
                    
        return None
        
    def _extract_date_from_url(self, url: str) -> Optional[str]:
        """Extract date from URL parameters or path.
        
        Args:
            url: URL to search for dates
            
        Returns:
            Date string in YYYY-MM-DD format or None
        """
        return self._extract_date_from_text(url)
        
    def _classify_meeting_type(self, text: str) -> str:
        """Classify the type of meeting based on title text.
        
        Args:
            text: Meeting title text
            
        Returns:
            Meeting type classification
        """
        text_lower = text.lower()
        
        if 'special' in text_lower:
            return 'special'
        elif 'workshop' in text_lower:
            return 'workshop'  
        elif 'public hearing' in text_lower:
            return 'public_hearing'
        elif 'budget' in text_lower:
            return 'budget'
        else:
            return 'regular'

    def _setup_meeting_directory(self, meeting_date: str) -> Path:
        """Create directory structure for meeting data.
        
        Args:
            meeting_date: Date in YYYY-MM-DD format
            
        Returns:
            Path to meeting directory
        """
        meeting_dir = self.data_directory / 'meetings' / f"{meeting_date}-regular"
        meeting_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (meeting_dir / 'originals').mkdir(exist_ok=True)
        (meeting_dir / 'originals' / 'attachments').mkdir(exist_ok=True)
        (meeting_dir / 'markdown').mkdir(exist_ok=True) 
        (meeting_dir / 'markdown' / 'attachments').mkdir(exist_ok=True)
        (meeting_dir / 'analysis').mkdir(exist_ok=True)
        
        return meeting_dir
        
    def _is_already_collected(self, meeting_dir: Path) -> bool:
        """Check if meeting data has already been collected.
        
        Args:
            meeting_dir: Path to meeting directory
            
        Returns:
            True if metadata file exists
        """
        return (meeting_dir / 'metadata.json').exists()
        
    async def _load_existing_metadata(self, meeting_dir: Path) -> Dict:
        """Load existing meeting metadata.
        
        Args:
            meeting_dir: Path to meeting directory
            
        Returns:
            Metadata dictionary
        """
        metadata_file = meeting_dir / 'metadata.json'
        async with aiofiles.open(metadata_file, 'r') as f:
            return json.loads(await f.read())
            
    async def _ensure_authenticated(self):
        """Ensure we have a valid authenticated session."""
        if not await self.session_manager.has_valid_session(self.client):
            await self.auth_manager.authenticate(self.client)
            await self.session_manager.save_session(self.client)
        else:
            await self.session_manager.restore_session(self.client)
            
    async def _find_meeting_url(self, meeting_date: datetime) -> Optional[str]:
        """Find the URL for a specific meeting date.
        
        Args:
            meeting_date: Meeting date to search for
            
        Returns:
            URL for the meeting page, or None if not found
        """
        date_str = meeting_date.strftime('%Y-%m-%d')
        
        # Use the URL pattern we discovered: /Agendas?date=YYYY-MM-DD
        test_url = f"{self.base_url}/Agendas?date={date_str}"
        
        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.get(test_url)
                
                if response.status_code == 200:
                    # Parse the response to see if it has meeting content
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for signs this is a real meeting page
                    page_text = soup.get_text().lower()
                    
                    # Check for meeting-specific content
                    meeting_indicators = [
                        'agenda', 'meeting', 'minutes', 'board meeting',
                        'town board', 'call to order', 'resolution'
                    ]
                    
                    has_meeting_content = any(indicator in page_text for indicator in meeting_indicators)
                    
                    # Also check for document links or downloads
                    doc_links = soup.find_all('a', href=lambda x: x and ('.pdf' in x.lower() or 'download' in x.lower()))
                    
                    if has_meeting_content or doc_links:
                        logger.info(f"Found meeting content for {date_str} at {test_url}")
                        return test_url
                        
                return None
                
            except httpx.RequestError as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt == self.retry_attempts - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        return None
                
    def _matches_meeting_date(self, text: str, target_date: datetime) -> bool:
        """Check if link text matches target meeting date.
        
        Args:
            text: Link text to analyze
            target_date: Target meeting date
            
        Returns:
            True if text appears to reference the target date
        """
        # Look for date patterns in various formats
        date_patterns = [
            target_date.strftime('%Y/%m/%d'),
            target_date.strftime('%m/%d/%Y'), 
            target_date.strftime('%Y-%m-%d'),
            target_date.strftime('%B %d, %Y'),
            target_date.strftime('%b %d, %Y'),
        ]
        
        text_lower = text.lower()
        for pattern in date_patterns:
            if pattern.lower() in text_lower:
                return True
                
        return False
        
    async def _download_documents(
        self, 
        documents: List[Dict], 
        meeting_dir: Path, 
        refresh: bool
    ) -> List[Dict]:
        """Download all discovered documents.
        
        Args:
            documents: List of document metadata
            meeting_dir: Meeting directory path
            refresh: Whether to re-download existing files
            
        Returns:
            List of download results with metadata
        """
        results = []
        
        for doc in documents:
            try:
                result = await self._download_single_document(
                    doc, meeting_dir, refresh
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to download {doc.get('filename', 'unknown')}: {e}")
                results.append({
                    **doc,
                    'download_status': 'error',
                    'error': str(e)
                })
                
        return results
        
    async def _download_single_document(
        self, 
        doc: Dict, 
        meeting_dir: Path, 
        refresh: bool
    ) -> Dict:
        """Download a single document.
        
        Args:
            doc: Document metadata
            meeting_dir: Meeting directory path  
            refresh: Whether to re-download existing files
            
        Returns:
            Download result with metadata
        """
        filename = doc['filename']
        download_url = doc['download_url']
        
        # Determine file path
        if doc.get('document_type') == 'attachment':
            file_path = meeting_dir / 'originals' / 'attachments' / filename
        else:
            file_path = meeting_dir / 'originals' / filename
            
        # Skip if exists and not refreshing
        if file_path.exists() and not refresh:
            return {
                **doc,
                'download_status': 'skipped',
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size
            }
            
        # Download file
        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.get(download_url)
                response.raise_for_status()
                
                # Save file
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(response.content)
                    
                logger.info(f"Downloaded {filename} ({len(response.content)} bytes)")
                
                return {
                    **doc,
                    'download_status': 'success',
                    'file_path': str(file_path),
                    'file_size': len(response.content),
                    'processed': False
                }
                
            except httpx.RequestError as e:
                logger.warning(f"Download failed (attempt {attempt + 1}): {e}")
                if attempt == self.retry_attempts - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                
    async def _parse_agenda_items(self, documents: List[Dict]) -> List[Dict]:
        """Parse agenda items from downloaded documents.
        
        Args:
            documents: List of downloaded document metadata
            
        Returns:
            List of agenda items with metadata
        """
        # This is a placeholder - actual implementation would parse
        # the agenda PDF/document to extract individual items
        agenda_items = []
        
        # Find the main agenda document
        agenda_doc = next((d for d in documents if d.get('document_type') == 'agenda'), None)
        
        if agenda_doc and agenda_doc.get('download_status') == 'success':
            # TODO: Parse actual agenda content
            # For now, create a placeholder item
            agenda_items.append({
                'id': 'item_001', 
                'section': 'PLACEHOLDER',
                'title': 'Agenda parsing not yet implemented',
                'description': 'This will be populated when document processing is added',
                'documents': [agenda_doc['filename']],
                'analysis_complete': False
            })
            
        return agenda_items
        
    async def _save_metadata(self, meeting_dir: Path, metadata: Dict):
        """Save meeting metadata to JSON file.
        
        Args:
            meeting_dir: Meeting directory path
            metadata: Metadata to save
        """
        metadata_file = meeting_dir / 'metadata.json'
        async with aiofiles.open(metadata_file, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))