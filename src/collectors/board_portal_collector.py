"""North Castle Board Portal Collector

Handles authentication, session management, and document collection
from the North Castle board portal system.
"""

import asyncio
import json
import logging
import os
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
                return self._load_existing_metadata(meeting_dir)
            
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
        # Navigate to agendas page
        agendas_url = urljoin(self.base_url, '/Agendas')
        
        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.get(agendas_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for meeting links with matching dates
                # This will need to be customized based on the actual HTML structure
                meeting_links = soup.find_all('a', href=True)
                
                for link in meeting_links:
                    href = link.get('href')
                    text = link.get_text().strip()
                    
                    # Check if this link matches our target date
                    if self._matches_meeting_date(text, meeting_date):
                        return urljoin(self.base_url, href)
                        
                return None
                
            except httpx.RequestError as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt == self.retry_attempts - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
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