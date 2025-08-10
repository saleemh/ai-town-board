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
            
            # Find all downloadable links
            download_links = self._find_download_links(soup)
            
            for link in download_links:
                doc_info = self._extract_document_info(link, meeting_url)
                if doc_info:
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