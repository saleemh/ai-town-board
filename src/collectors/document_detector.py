"""Document Detector for Board Portal

Discovers and identifies downloadable documents from meeting pages.
"""

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag


logger = logging.getLogger(__name__)


class DocumentDetector:
    """Detects and catalogs downloadable documents from board portal pages."""
    
    def __init__(self, config: Dict):
        """Initialize document detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.base_url = config['board_portal']['base_url']
        
    async def discover_documents(
        self, 
        client: httpx.AsyncClient, 
        meeting_url: str
    ) -> List[Dict]:
        """Discover all downloadable documents from a meeting page.
        
        Args:
            client: Authenticated HTTP client
            meeting_url: URL of the meeting page
            
        Returns:
            List of document metadata dictionaries
        """
        logger.info(f"Discovering documents from: {meeting_url}")
        
        try:
            response = await client.get(meeting_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            documents = []
            
            # TEMPORARY FIX: Instead of returning navigation links, let's try to find the 
            # actual PDF download patterns that work for this specific portal
            documents = await self._discover_civicclerk_documents(client, meeting_url, soup)
            
            if not documents:
                # Fall back to the old method if new method doesn't work
                download_links = self._find_download_links(soup)
                
                for link in download_links:
                    doc_info = self._extract_document_info(link, meeting_url)
                    if doc_info:
                        # CRITICAL FIX: Don't add documents that point to HTML pages
                        if self._is_valid_document_url(doc_info['download_url']):
                            documents.append(doc_info)
                    
            logger.info(f"Found {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error discovering documents: {e}")
            raise
            
    def _find_download_links(self, soup: BeautifulSoup) -> List[Tag]:
        """Find all potential download links on the page.
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            List of link elements
        """
        download_links = []
        
        # Look for links with common document extensions
        doc_extensions = ['.pdf', '.doc', '.docx', '.xlsx', '.xls', '.txt', '.rtf']
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            
            # Check if link points to a document
            if any(ext in href for ext in doc_extensions):
                download_links.append(link)
                continue
                
            # Check for download attributes or classes
            if (link.get('download') or 
                'download' in link.get('class', []) or
                'attachment' in link.get('class', []) or
                'document' in link.get('class', [])):
                download_links.append(link)
                continue
                
            # Check link text for document indicators
            link_text = link.get_text().strip().lower()
            if any(word in link_text for word in ['agenda', 'packet', 'minutes', 'attachment', 'document']):
                download_links.append(link)
                
        # Also look for form submissions that might download documents
        for form in soup.find_all('form'):
            for button in form.find_all(['input', 'button'], type=['submit']):
                if any(word in button.get('value', '').lower() for word in ['download', 'view', 'open']):
                    # Convert form to a pseudo-link for processing
                    pseudo_link = soup.new_tag('a')
                    pseudo_link['href'] = form.get('action', '')
                    pseudo_link['data-form'] = 'true'
                    pseudo_link.string = button.get('value', 'Document')
                    download_links.append(pseudo_link)
                    
        return download_links
        
    def _extract_document_info(self, link: Tag, base_url: str) -> Optional[Dict]:
        """Extract document information from a link element.
        
        Args:
            link: BeautifulSoup link element
            base_url: Base URL for resolving relative links
            
        Returns:
            Document metadata dictionary or None
        """
        try:
            href = link.get('href', '').strip()
            if not href:
                return None
                
            # Resolve relative URLs
            if href.startswith('/') or not href.startswith('http'):
                download_url = urljoin(base_url, href)
            else:
                download_url = href
                
            # Extract filename from URL or link text
            filename = self._extract_filename(download_url, link.get_text().strip())
            
            if not filename:
                return None
                
            # Determine document type
            doc_type = self._classify_document_type(filename, link.get_text().strip())
            
            # Get file size if available (usually not in HTML, but check)
            file_size = self._extract_file_size(link)
            
            document_info = {
                'filename': filename,
                'download_url': download_url,
                'document_type': doc_type,
                'link_text': link.get_text().strip(),
                'file_size': file_size,
                'processed': False
            }
            
            # Add form data if this is a form submission
            if link.get('data-form') == 'true':
                document_info['is_form_submission'] = True
                
            logger.debug(f"Extracted document: {filename} ({doc_type})")
            return document_info
            
        except Exception as e:
            logger.warning(f"Error extracting document info from link: {e}")
            return None
            
    def _extract_filename(self, url: str, link_text: str) -> Optional[str]:
        """Extract filename from URL or link text.
        
        Args:
            url: Download URL
            link_text: Link display text
            
        Returns:
            Filename or None
        """
        # Try to get filename from URL
        parsed_url = urlparse(url)
        url_filename = parsed_url.path.split('/')[-1]
        
        if url_filename and '.' in url_filename:
            return url_filename
            
        # Try to extract from link text
        text_lower = link_text.lower().strip()
        
        # Look for common patterns in link text
        patterns = [
            r'(agenda.*?\.pdf)',
            r'(packet.*?\.pdf)', 
            r'(minutes.*?\.pdf)',
            r'(\w+.*?\.(?:pdf|doc|docx|xlsx|xls))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).replace(' ', '_')
                
        # Generate filename from link text
        if text_lower:
            # Clean up text and add extension
            clean_text = re.sub(r'[^\w\s-]', '', text_lower)
            clean_text = re.sub(r'\s+', '_', clean_text)
            
            if clean_text:
                # Guess extension based on content
                if 'agenda' in clean_text:
                    return f"{clean_text}.pdf"
                elif 'packet' in clean_text:
                    return f"{clean_text}.pdf"
                elif 'minutes' in clean_text:
                    return f"{clean_text}.pdf"
                else:
                    return f"{clean_text}.pdf"
                    
        return None
        
    def _classify_document_type(self, filename: str, link_text: str) -> str:
        """Classify the type of document based on filename and link text.
        
        Args:
            filename: Document filename
            link_text: Link display text
            
        Returns:
            Document type classification
        """
        filename_lower = filename.lower()
        text_lower = link_text.lower()
        combined = f"{filename_lower} {text_lower}"
        
        # Classification rules
        if any(word in combined for word in ['agenda']):
            return 'agenda'
        elif any(word in combined for word in ['packet', 'board packet']):
            return 'packet'
        elif any(word in combined for word in ['minutes']):
            return 'minutes'
        elif any(word in combined for word in ['attachment', 'exhibit', 'supporting']):
            return 'attachment'
        elif any(word in combined for word in ['resolution']):
            return 'resolution'
        elif any(word in combined for word in ['ordinance']):
            return 'ordinance'
        elif any(word in combined for word in ['budget']):
            return 'budget'
        elif any(word in combined for word in ['presentation', 'slides']):
            return 'presentation'
        else:
            return 'document'
            
    def _extract_file_size(self, link: Tag) -> Optional[int]:
        """Extract file size if available in the HTML.
        
        Args:
            link: BeautifulSoup link element
            
        Returns:
            File size in bytes or None
        """
        # Look for size information in link text or nearby elements
        size_text = link.get_text() + ' ' + str(link.parent) if link.parent else link.get_text()
        
        # Look for size patterns like "1.2 MB", "500 KB", etc.
        size_pattern = r'(\d+(?:\.\d+)?)\s*(kb|mb|gb|bytes?)'
        match = re.search(size_pattern, size_text.lower())
        
        if match:
            size_value = float(match.group(1))
            size_unit = match.group(2).lower()
            
            # Convert to bytes
            multipliers = {
                'bytes': 1,
                'byte': 1,
                'kb': 1024,
                'mb': 1024 * 1024,
                'gb': 1024 * 1024 * 1024
            }
            
            return int(size_value * multipliers.get(size_unit, 1))
            
        return None
        
    async def _discover_civicclerk_documents(
        self, 
        client: httpx.AsyncClient, 
        meeting_url: str, 
        soup: BeautifulSoup
    ) -> List[Dict]:
        """Discover documents using CivicClerk-specific patterns.
        
        This method attempts to find the actual PDF download URLs instead of 
        navigation page links.
        
        Args:
            client: HTTP client
            meeting_url: Meeting page URL
            soup: Parsed HTML
            
        Returns:
            List of document dictionaries
        """
        documents = []
        
        # Extract date from meeting URL (format: ?date=YYYY-MM-DD)
        import re
        from urllib.parse import urlparse, parse_qs
        
        parsed_url = urlparse(meeting_url)
        query_params = parse_qs(parsed_url.query)
        meeting_date = query_params.get('date', [None])[0]
        
        if not meeting_date:
            logger.warning("Could not extract meeting date from URL")
            return documents
            
        logger.debug(f"Searching for documents for meeting date: {meeting_date}")
        
        # First, try to find document IDs or session-specific URLs in the HTML/JavaScript
        documents_from_page = self._extract_document_ids_from_page(soup, meeting_date)
        if documents_from_page:
            return documents_from_page
        
        # Try common CivicClerk document endpoint patterns with date variations
        base_url = self.base_url
        
        # Try different date formats that might work
        date_formats = [
            meeting_date,  # 2025-08-13
            meeting_date.replace('-', '/'),  # 2025/08/13
            meeting_date.replace('-', ''),   # 20250813
        ]
        
        potential_endpoints = []
        for date_fmt in date_formats:
            potential_endpoints.extend([
                # Direct PDF patterns
                f"/Agendas/GetAgenda/{date_fmt}",
                f"/Minutes/GetMinutes/{date_fmt}",
                f"/Documents/GetPacket/{date_fmt}",
                f"/Documents/GetAgenda/{date_fmt}",
                f"/Documents/GetMinutes/{date_fmt}",
                # API patterns
                f"/API/Documents/{date_fmt}/agenda/download",
                f"/API/Documents/{date_fmt}/minutes/download", 
                f"/API/Documents/{date_fmt}/packet/download",
                f"/API/Meetings/{date_fmt}/agenda",
                f"/API/Meetings/{date_fmt}/minutes",
                f"/API/Meetings/{date_fmt}/packet",
                # File serving patterns
                f"/Files/Meeting/{date_fmt}/agenda.pdf",
                f"/Files/Meeting/{date_fmt}/minutes.pdf",
                f"/Files/Meeting/{date_fmt}/packet.pdf",
                # Alternative patterns
                f"/Documents/{date_fmt}/agenda.pdf",
                f"/Documents/{date_fmt}/minutes.pdf",
                f"/Documents/{date_fmt}/packet.pdf",
                f"/Download/{date_fmt}/agenda",
                f"/Download/{date_fmt}/minutes",
                f"/Download/{date_fmt}/packet",
            ])
        
        for endpoint in potential_endpoints:
            try:
                test_url = base_url + endpoint
                logger.debug(f"Testing document endpoint: {test_url}")
                
                response = await client.get(test_url)
                
                # Check if this returned a PDF or valid document
                if (response.status_code == 200 and 
                    len(response.content) > 1000 and
                    self._looks_like_pdf(response)):
                    
                    # Determine document type from endpoint
                    doc_type = 'document'
                    filename = 'document.pdf'
                    
                    if 'agenda' in endpoint.lower():
                        doc_type = 'agenda'
                        filename = 'agenda.pdf'
                    elif 'minutes' in endpoint.lower():
                        doc_type = 'minutes' 
                        filename = 'minutes.pdf'
                    elif 'packet' in endpoint.lower():
                        doc_type = 'packet'
                        filename = 'packet.pdf'
                        
                    doc_info = {
                        'filename': filename,
                        'download_url': test_url,
                        'document_type': doc_type,
                        'link_text': f'{doc_type.title()} Document',
                        'file_size': len(response.content),
                        'processed': False
                    }
                    
                    documents.append(doc_info)
                    logger.info(f"Found {doc_type} document: {test_url} ({len(response.content)} bytes)")
                    
            except Exception as e:
                logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue
                
        return documents
        
    def _looks_like_pdf(self, response) -> bool:
        """Check if HTTP response looks like a PDF file.
        
        Args:
            response: HTTP response object
            
        Returns:
            True if response appears to be a PDF
        """
        content_type = response.headers.get('content-type', '').lower()
        
        # Check content type
        if 'application/pdf' in content_type:
            return True
            
        # Check if content starts with PDF magic bytes
        if response.content.startswith(b'%PDF'):
            return True
            
        # Check if it's NOT HTML (our main problem)
        if 'text/html' in content_type:
            return False
            
        # If content is substantial and not HTML, could be a PDF
        if len(response.content) > 1000 and not response.content.startswith(b'<!DOCTYPE'):
            return True
            
        return False
        
    def _is_valid_document_url(self, url: str) -> bool:
        """Check if URL appears to be a valid document download URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears to be a document download
        """
        url_lower = url.lower()
        
        # Check for obvious PDF URLs
        if '.pdf' in url_lower:
            return True
            
        # Reject navigation page URLs
        navigation_patterns = [
            '/agendas$',
            '/minutes$', 
            '/documents$',
            '/agendas/$',
            '/minutes/$',
            '/documents/$'
        ]
        
        for pattern in navigation_patterns:
            if re.search(pattern, url_lower):
                return False
                
        # Accept URLs that look like document endpoints
        document_patterns = [
            'download',
            'getdocument',
            'getfile',
            'pdf',
            'attachment'
        ]
        
        return any(pattern in url_lower for pattern in document_patterns)
        
    def _extract_document_ids_from_page(self, soup: BeautifulSoup, meeting_date: str) -> List[Dict]:
        """Try to extract document IDs or URLs from JavaScript/HTML content.
        
        Args:
            soup: Parsed HTML content
            meeting_date: Meeting date string
            
        Returns:
            List of document dictionaries found in page content
        """
        documents = []
        
        # Look for JavaScript variables that might contain document info
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
                
            script_content = script.string
            
            # Look for common patterns that might indicate document URLs or IDs
            patterns_to_search = [
                # Look for URL patterns in JavaScript
                r'"(/[^"]*(?:agenda|minutes|packet)[^"]*\.pdf)"',
                r"'(/[^']*(?:agenda|minutes|packet)[^']*\.pdf)'",
                # Look for object IDs that might be used to construct URLs
                r'agenda_object_id["\']?\s*:\s*["\']?(\d+)',
                r'document_id["\']?\s*:\s*["\']?(\d+)',
                r'meeting_id["\']?\s*:\s*["\']?(\d+)',
                # Look for download functions or endpoints
                r'download[^(]*\([^)]*["\']([^"\']*(?:agenda|minutes|packet)[^"\']*)',
            ]
            
            for pattern in patterns_to_search:
                matches = re.findall(pattern, script_content, re.IGNORECASE)
                
                for match in matches:
                    # Try to construct a document info from this match
                    if match.startswith('/'):
                        # This looks like a URL path
                        full_url = self.base_url + match
                        doc_type = self._classify_document_type(match, match)
                        filename = f"{doc_type}.pdf"
                        
                        doc_info = {
                            'filename': filename,
                            'download_url': full_url,
                            'document_type': doc_type,
                            'link_text': f'{doc_type.title()} (from JS)',
                            'file_size': None,
                            'processed': False
                        }
                        documents.append(doc_info)
                        logger.info(f"Found document URL in JavaScript: {full_url}")
                        
                    elif match.isdigit():
                        # This might be a document ID - try common URL patterns with this ID
                        doc_id = match
                        potential_urls = [
                            f"/Documents/Download/{doc_id}",
                            f"/API/Documents/{doc_id}/download",
                            f"/Agendas/Download/{doc_id}",
                            f"/Minutes/Download/{doc_id}",
                        ]
                        
                        # We'd need to test these URLs, but for now just log them
                        logger.debug(f"Found potential document ID: {doc_id}")
                        
        # Look for data attributes in HTML elements that might contain document info
        elements_with_data = soup.find_all(attrs={"data-url": True})
        elements_with_data += soup.find_all(attrs={"data-download": True})
        elements_with_data += soup.find_all(attrs={"data-document-id": True})
        
        for element in elements_with_data:
            for attr_name, attr_value in element.attrs.items():
                if attr_name.startswith('data-') and isinstance(attr_value, str):
                    if any(word in attr_value.lower() for word in ['agenda', 'minutes', 'packet', 'download']):
                        logger.debug(f"Found data attribute {attr_name}='{attr_value}' that might be document-related")
                        
                        if attr_value.startswith('/') or attr_value.startswith('http'):
                            # This could be a document URL
                            if attr_value.startswith('/'):
                                full_url = self.base_url + attr_value
                            else:
                                full_url = attr_value
                                
                            doc_type = self._classify_document_type(attr_value, element.get_text())
                            filename = f"{doc_type}.pdf"
                            
                            doc_info = {
                                'filename': filename,
                                'download_url': full_url,
                                'document_type': doc_type,
                                'link_text': f'{doc_type.title()} (from data attr)',
                                'file_size': None,
                                'processed': False
                            }
                            documents.append(doc_info)
                            logger.info(f"Found document URL in data attribute: {full_url}")
        
        return documents