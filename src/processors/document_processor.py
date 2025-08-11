"""Universal PDF Document Processing System

This module provides a flexible, extensible system for processing any type of structured PDF document.
It uses IBM Docling for PDF-to-Markdown conversion with intelligent segmentation capabilities.

Key Features:
- Universal PDF processing pipeline
- Intelligent document type detection
- Content-aware segmentation strategies
- Extensible for different document types (municipal code, meeting docs, reports)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import json

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.document import ConversionResult
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    DocumentConverter = None
    InputFormat = None
    PdfPipelineOptions = None
    ConversionResult = None

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    PyPDF2 = None

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Types of documents the system can process."""
    MUNICIPAL_CODE = "municipal_code"
    MEETING_AGENDA = "meeting_agenda" 
    MEETING_MINUTES = "meeting_minutes"
    MEETING_PACKET = "meeting_packet"
    REPORT = "report"
    LEGAL_DOCUMENT = "legal_document"
    SINGLE_DOCUMENT = "single_document"
    UNKNOWN = "unknown"


class SegmentationType(Enum):
    """Different ways to segment documents."""
    CHAPTER_BASED = "chapter_based"      # Municipal code chapters
    SECTION_BASED = "section_based"      # Report sections
    AGENDA_ITEM_BASED = "agenda_based"   # Meeting agenda items
    PAGE_BASED = "page_based"            # Simple page ranges
    SINGLE_FILE = "single_file"          # No segmentation


@dataclass
class DocumentSegment:
    """Represents a logical segment of a document with hierarchical context."""
    source_path: Path
    start_page: int
    end_page: int
    title: str
    segment_type: str
    metadata: Dict[str, Any]
    output_filename: Optional[str] = None
    
    # Hierarchical context
    level: int = 1
    section_id: Optional[str] = None
    parent_id: Optional[str] = None
    hierarchical_path: Optional[str] = None
    chapter_context: Optional[Dict[str, Any]] = None  # Info about the containing chapter
    
    def get_safe_filename(self) -> str:
        """Generate a safe filename that reflects hierarchical structure."""
        # Create base from section type and level
        prefix = f"L{self.level:02d}"  # Level prefix (L01, L02, etc.)
        
        if self.section_id:
            prefix += f"-{self.section_id.replace('.', '-')}"
        
        # Clean title for filename
        clean_title = self._clean_title_for_filename(self.title)
        
        return f"{prefix}-{clean_title}"
    
    def _clean_title_for_filename(self, title: str) -> str:
        """Clean title for filesystem-safe filename."""
        import re
        # Remove chapter/section prefixes for cleaner names
        clean = re.sub(r'^(chapter|section|§)\s*\d*:?\s*', '', title.lower())
        # Replace special characters
        clean = re.sub(r'[^\w\s-]', '', clean)
        # Replace spaces with dashes and limit length
        clean = re.sub(r'\s+', '-', clean.strip())[:50]
        return clean or 'untitled'


@dataclass
class TableOfContents:
    """Structured representation of document TOC."""
    entries: List[Dict[str, Any]]
    has_page_numbers: bool = False
    hierarchy_levels: int = 1


@dataclass
class DocumentAnalysis:
    """Results of document structure analysis."""
    page_count: int
    document_type: DocumentType
    toc: Optional[TableOfContents] = None
    segmentation_strategy: SegmentationType = SegmentationType.SINGLE_FILE
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ProcessedDocument:
    """A processed document segment."""
    content: str
    metadata: Dict[str, Any]
    cross_references: List[str] = None
    output_path: Optional[Path] = None

    def __post_init__(self):
        if self.cross_references is None:
            self.cross_references = []


class UniversalDocumentProcessor(ABC):
    """Base class for all document processors."""
    
    def __init__(self, config: Dict):
        """Initialize the processor.
        
        Args:
            config: System configuration dictionary
        """
        self.config = config
        self.docling_config = config.get('document_processing', {}).get('docling', {})
        self.segmentation_config = config.get('document_processing', {}).get('segmentation', {})
        
        # Initialize Docling converter
        self.docling_converter = None
        if DOCLING_AVAILABLE:
            self._init_docling_converter()
        else:
            logger.warning("Docling not available. Install with: pip install docling")
    
    def _init_docling_converter(self):
        """Initialize the Docling document converter with configuration."""
        try:
            # Initialize converter with default options first
            self.docling_converter = DocumentConverter()
            logger.info("Docling converter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docling converter: {e}")
            self.docling_converter = None
        
    def analyze_document(self, pdf_path: Path) -> DocumentAnalysis:
        """Analyze PDF structure and determine processing strategy.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            DocumentAnalysis with structure information
        """
        logger.info(f"Analyzing document: {pdf_path}")
        
        # For now, implement basic analysis
        # TODO: Integrate with docling for advanced analysis
        page_count = self._get_page_count(pdf_path)
        doc_type = self._detect_document_type(pdf_path)
        toc = self._extract_table_of_contents(pdf_path)
        segmentation = self._determine_segmentation_strategy(doc_type, page_count, toc)
        
        return DocumentAnalysis(
            page_count=page_count,
            document_type=doc_type,
            toc=toc,
            segmentation_strategy=segmentation,
            metadata={
                'source_file': str(pdf_path),
                'file_size': pdf_path.stat().st_size if pdf_path.exists() else 0
            }
        )
    
    def segment_document(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Split document into logical segments based on structure.
        
        Args:
            pdf_path: Path to source PDF
            analysis: Document analysis results
            
        Returns:
            List of document segments to process
        """
        logger.info(f"Segmenting document using strategy: {analysis.segmentation_strategy}")
        
        if analysis.segmentation_strategy == SegmentationType.CHAPTER_BASED:
            return self._segment_by_chapters(pdf_path, analysis)
        elif analysis.segmentation_strategy == SegmentationType.SECTION_BASED:
            return self._segment_by_sections(pdf_path, analysis)
        elif analysis.segmentation_strategy == SegmentationType.AGENDA_ITEM_BASED:
            return self._segment_by_agenda_items(pdf_path, analysis)
        elif analysis.segmentation_strategy == SegmentationType.PAGE_BASED:
            return self._segment_by_pages(pdf_path, analysis)
        else:  # SINGLE_FILE
            return [DocumentSegment(
                source_path=pdf_path,
                start_page=1,
                end_page=analysis.page_count,
                title=pdf_path.stem,
                segment_type="complete_document",
                metadata=analysis.metadata
            )]
    
    def process_segment(self, segment: DocumentSegment) -> ProcessedDocument:
        """Convert PDF segment to structured markdown.
        
        Args:
            segment: Document segment to process
            
        Returns:
            Processed document with markdown content
        """
        logger.info(f"Processing segment: {segment.title}")
        
        if not DOCLING_AVAILABLE or not self.docling_converter:
            logger.warning("Docling not available, using placeholder content")
            markdown_content = self._create_placeholder_markdown(segment)
        else:
            try:
                # Use Docling to process the actual PDF content
                markdown_content = self._process_with_docling(segment)
            except Exception as e:
                logger.error(f"Error processing segment with Docling: {e}")
                logger.info("Falling back to placeholder content")
                markdown_content = self._create_placeholder_markdown(segment)
        
        return ProcessedDocument(
            content=markdown_content,
            metadata=segment.metadata,
            cross_references=self._extract_references(markdown_content)
        )
    
    def _process_with_docling(self, segment: DocumentSegment) -> str:
        """Process PDF segment using Docling to extract actual content."""
        logger.info(f"Processing {segment.source_path} pages {segment.start_page}-{segment.end_page} with Docling")
        
        # If it's a specific page range (not the full document), create a temporary PDF with just those pages
        if segment.start_page != 1 or segment.end_page < self._get_page_count(segment.source_path):
            return self._process_pdf_segment_with_docling(segment)
        else:
            # Process the full document
            return self._process_full_document_with_docling(segment)
    
    def _process_pdf_segment_with_docling(self, segment: DocumentSegment, permanent_pdf_dir: Path = None) -> str:
        """Process a specific page range by creating a PDF segment and processing with Docling."""
        if not PYPDF2_AVAILABLE:
            raise Exception("PyPDF2 required for PDF segmentation")
        
        # Create PDF segment (permanent if output dir provided, otherwise temporary)
        if permanent_pdf_dir:
            segment_pdf_path = self._create_permanent_pdf_segment(
                segment.source_path, 
                segment.start_page, 
                segment.end_page,
                permanent_pdf_dir,
                segment.get_safe_filename()
            )
            cleanup_pdf = False
        else:
            segment_pdf_path = self._create_temp_pdf_segment(
                segment.source_path, 
                segment.start_page, 
                segment.end_page
            )
            cleanup_pdf = True
        
        try:
            # Process the PDF with Docling
            result = self.docling_converter.convert(segment_pdf_path)
            
            if not result:
                raise Exception("No result returned from Docling conversion")
            
            # Extract markdown content
            markdown_content = ""
            if hasattr(result, 'document') and hasattr(result.document, 'export_to_markdown'):
                markdown_content = result.document.export_to_markdown()
            elif hasattr(result, 'document'):
                markdown_content = self._extract_content_from_docling_document(result.document)
            
            if not markdown_content or markdown_content.strip() == "":
                raise Exception("No content extracted from document")
            
            # Add document header with metadata including PDF reference
            pdf_reference = segment_pdf_path.name if permanent_pdf_dir else "temporary segment"
            
            header = f"""# {segment.title}

## Document Information
- **Source**: {segment.source_path.name}
- **Pages**: {segment.start_page}-{segment.end_page}
- **PDF Segment**: {pdf_reference}
- **Processing**: IBM Docling (Segmented)

---

"""
            
            return header + markdown_content
            
        finally:
            # Clean up temporary file only if it was temporary
            if cleanup_pdf and segment_pdf_path.exists():
                segment_pdf_path.unlink()
    
    def _create_permanent_pdf_segment(
        self, 
        source_pdf: Path, 
        start_page: int, 
        end_page: int, 
        output_dir: Path, 
        filename_base: str
    ) -> Path:
        """Create a permanent PDF segment file for traceability."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{filename_base}.pdf"
        
        try:
            with open(source_pdf, 'rb') as input_file:
                reader = PyPDF2.PdfReader(input_file)
                writer = PyPDF2.PdfWriter()
                
                # Add pages (convert to 0-based indexing)
                for page_num in range(start_page - 1, min(end_page, len(reader.pages))):
                    if page_num < len(reader.pages):
                        writer.add_page(reader.pages[page_num])
                
                # Write to permanent file
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
            
            logger.info(f"Created permanent PDF segment: {output_path.name} (pages {start_page}-{end_page})")
            return output_path
            
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise e
    
    def _create_temp_pdf_segment(self, source_pdf: Path, start_page: int, end_page: int) -> Path:
        """Create a temporary PDF containing only the specified page range."""
        import tempfile
        
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
        temp_pdf_path = Path(temp_path)
        
        try:
            with open(source_pdf, 'rb') as input_file:
                reader = PyPDF2.PdfReader(input_file)
                writer = PyPDF2.PdfWriter()
                
                # Add pages (convert to 0-based indexing)
                for page_num in range(start_page - 1, min(end_page, len(reader.pages))):
                    if page_num < len(reader.pages):
                        writer.add_page(reader.pages[page_num])
                
                # Write to temporary file
                with open(temp_pdf_path, 'wb') as output_file:
                    writer.write(output_file)
            
            logger.info(f"Created temporary PDF segment: {temp_pdf_path} (pages {start_page}-{end_page})")
            return temp_pdf_path
            
        except Exception as e:
            # Clean up on error
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
            raise e
        finally:
            # Close the temporary file descriptor
            import os
            os.close(temp_fd)
    
    def _process_full_document_with_docling(self, segment: DocumentSegment) -> str:
        """Process complete PDF document with Docling."""
        try:
            # Convert the PDF to markdown
            result = self.docling_converter.convert(segment.source_path)
            
            if not result:
                raise Exception("No result returned from Docling conversion")
            
            # Get the markdown content - Docling returns a ConversionResult
            markdown_content = ""
            
            # Try to get markdown export
            if hasattr(result, 'document') and hasattr(result.document, 'export_to_markdown'):
                markdown_content = result.document.export_to_markdown()
            elif hasattr(result, 'document'):
                # Try to convert document to markdown format
                try:
                    # Use Docling's markdown export if available
                    markdown_content = result.document.export_to_markdown()
                except:
                    # Fallback to extracting text content manually
                    markdown_content = self._extract_content_from_docling_document(result.document)
            else:
                raise Exception("Could not access document from Docling result")
            
            if not markdown_content or markdown_content.strip() == "":
                raise Exception("No content extracted from document")
            
            # Add document header with metadata
            header = f"""# {segment.title}

## Document Information
- **Source**: {segment.source_path.name}
- **Pages**: {segment.start_page}-{segment.end_page}
- **Processed**: {Path(__file__).stat().st_mtime}
- **Processing**: IBM Docling

---

"""
            
            return header + markdown_content
            
        except Exception as e:
            logger.error(f"Error in Docling processing: {e}")
            raise e
    
    def _extract_content_from_docling_document(self, document) -> str:
        """Extract content from Docling document object."""
        content_parts = []
        
        # Try different attributes that might contain the text
        for attr in ['main_text', 'text', 'content', 'body']:
            if hasattr(document, attr):
                text = getattr(document, attr)
                if text and isinstance(text, str):
                    content_parts.append(text)
                    break
        
        # If we found text content, use it
        if content_parts:
            return '\n'.join(content_parts)
        
        # Otherwise, try to convert the whole document to string
        return str(document)
    
    def _convert_docling_to_markdown(self, document) -> str:
        """Convert Docling document structure to markdown."""
        markdown_lines = []
        
        # Extract main text content
        if hasattr(document, 'main_text') and document.main_text:
            markdown_lines.append(document.main_text)
        
        # Extract tables if available
        if hasattr(document, 'tables') and document.tables:
            markdown_lines.append("\n## Tables\n")
            for i, table in enumerate(document.tables):
                markdown_lines.append(f"\n### Table {i+1}\n")
                if hasattr(table, 'to_markdown'):
                    markdown_lines.append(table.to_markdown())
                else:
                    markdown_lines.append(str(table))
        
        # Extract any other structured content
        if hasattr(document, 'figures') and document.figures:
            markdown_lines.append("\n## Figures\n")
            for i, figure in enumerate(document.figures):
                markdown_lines.append(f"\n### Figure {i+1}\n")
                if hasattr(figure, 'caption'):
                    markdown_lines.append(f"Caption: {figure.caption}")
        
        return "\n".join(markdown_lines)
    
    def _get_page_count(self, pdf_path: Path) -> int:
        """Get number of pages in PDF using PyPDF2."""
        if not PYPDF2_AVAILABLE:
            logger.warning("PyPDF2 not available, estimating page count")
            file_size = pdf_path.stat().st_size
            estimated_pages = max(1, file_size // 50000)  # Rough estimate: 1 page per 50KB
            return estimated_pages
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                return len(reader.pages)
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            # Last resort: estimate based on file size
            file_size = pdf_path.stat().st_size
            estimated_pages = max(1, file_size // 50000)  # Rough estimate
            logger.warning(f"Using estimated page count: {estimated_pages}")
            return estimated_pages
    
    def _detect_document_type(self, pdf_path: Path) -> DocumentType:
        """Detect document type based on filename and content."""
        filename = pdf_path.name.lower()
        
        # Check filename patterns
        if 'town' in filename and ('code' in filename or 'ordinance' in filename):
            return DocumentType.MUNICIPAL_CODE
        elif 'town' in filename and ('castle' in filename or 'ny' in filename):
            # Handle "Town of North Castle, NY.pdf" format
            return DocumentType.MUNICIPAL_CODE
        elif 'agenda' in filename:
            return DocumentType.MEETING_AGENDA
        elif 'minutes' in filename:
            return DocumentType.MEETING_MINUTES
        elif 'packet' in filename:
            return DocumentType.MEETING_PACKET
        else:
            # For documents with unknown filenames, check if they have a substantial TOC
            # that suggests municipal code structure
            toc = self._extract_table_of_contents(pdf_path)
            if toc and len(toc.entries) > 50:  # Municipal codes typically have many TOC entries
                # Look for chapter patterns in TOC
                chapter_count = sum(1 for entry in toc.entries if 'chapter' in entry.get('title', '').lower())
                if chapter_count > 5:  # If it has many chapters, likely municipal code
                    return DocumentType.MUNICIPAL_CODE
            
            return DocumentType.SINGLE_DOCUMENT
    
    def _extract_table_of_contents(self, pdf_path: Path) -> Optional[TableOfContents]:
        """Extract table of contents from PDF using PyPDF2 bookmarks."""
        if not PYPDF2_AVAILABLE:
            logger.warning("PyPDF2 not available, cannot extract TOC")
            return None
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Get PDF bookmarks/outline
                outline = reader.outline
                if not outline:
                    logger.info("No PDF bookmarks found")
                    return None
                
                # Convert PyPDF2 outline to our TOC format
                toc_entries = self._parse_pdf_outline(outline, reader)
                
                if not toc_entries:
                    logger.info("No TOC entries found in PDF bookmarks")
                    return None
                
                return TableOfContents(
                    entries=toc_entries,
                    has_page_numbers=any(entry.get('page_number', 0) > 0 for entry in toc_entries),
                    hierarchy_levels=max((entry.get('level', 1) for entry in toc_entries), default=1)
                )
                
        except Exception as e:
            logger.error(f"Error extracting TOC with PyPDF2: {e}")
            return None
    
    def _parse_pdf_outline(self, outline, reader, level=1, parent_path="", parent_id=None) -> List[Dict[str, Any]]:
        """Parse PyPDF2 outline structure into hierarchical TOC entries."""
        toc_entries = []
        
        for idx, item in enumerate(outline):
            if isinstance(item, list):
                # Nested outline level - process recursively
                current_parent_path = parent_path
                toc_entries.extend(self._parse_pdf_outline(item, reader, level + 1, current_parent_path, parent_id))
            else:
                # Individual bookmark
                try:
                    title = str(item.title) if hasattr(item, 'title') else str(item)
                    
                    # Create unique ID for this entry
                    entry_id = f"{parent_id}.{idx}" if parent_id else str(idx)
                    
                    # Build hierarchical path
                    current_path = f"{parent_path} > {title}" if parent_path else title
                    
                    # Get page number
                    page_number = self._extract_page_number_from_bookmark(item, reader)
                    
                    # Determine section type based on level and content
                    section_type = self._determine_section_type(title, level)
                    
                    entry = {
                        'id': entry_id,
                        'title': title,
                        'page_number': page_number,
                        'level': level,
                        'section_type': section_type,
                        'parent_id': parent_id,
                        'hierarchical_path': current_path,
                        'index_in_parent': idx
                    }
                    
                    toc_entries.append(entry)
                    
                    # If this item has children, they would be processed in the next iteration
                    # with this entry as their parent
                    
                except Exception as e:
                    logger.warning(f"Error parsing outline item: {e}")
                    continue
        
        return toc_entries
    
    def _extract_page_number_from_bookmark(self, item, reader) -> int:
        """Extract page number from PyPDF2 bookmark."""
        page_number = 1
        if hasattr(item, 'page') and item.page:
            try:
                page_ref = item.page
                if hasattr(page_ref, 'idnum'):
                    # Find page number from page reference
                    for page_num, page in enumerate(reader.pages):
                        if hasattr(page, 'indirect_reference') and page.indirect_reference.idnum == page_ref.idnum:
                            page_number = page_num + 1  # Convert to 1-based
                            break
                else:
                    # Direct page number
                    page_number = int(page_ref) + 1 if isinstance(page_ref, int) else 1
            except:
                page_number = 1
        return page_number
    
    def _determine_section_type(self, title: str, level: int) -> str:
        """Determine the type of section based on title and level."""
        title_lower = title.lower().strip()
        
        # Chapter level (usually level 1)
        if level <= 1 or 'chapter' in title_lower:
            return 'chapter'
        elif level == 2:
            return 'section'
        elif level == 3:
            return 'subsection'
        else:
            return 'subsubsection'
    
    def _extract_toc_from_text(self, text_content: str) -> List[Dict[str, Any]]:
        """Extract TOC entries by detecting heading patterns in text."""
        import re
        
        toc_entries = []
        lines = text_content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Look for common heading patterns
            # Chapter patterns
            chapter_match = re.match(r'^(Chapter\s+(\d+)|CHAPTER\s+(\d+))\s*[-:]?\s*(.+)?', line, re.IGNORECASE)
            if chapter_match:
                chapter_num = chapter_match.group(2) or chapter_match.group(3)
                title = chapter_match.group(4) or f"Chapter {chapter_num}"
                toc_entries.append({
                    'title': line,
                    'page_number': 0,  # Page numbers would need to be determined differently
                    'level': 1,
                    'chapter_number': chapter_num
                })
                continue
            
            # Section patterns (like "§ 123-45")
            section_match = re.match(r'^§\s*(\d+(?:-\d+)?)\s*(.+)?', line)
            if section_match:
                section_num = section_match.group(1)
                title = section_match.group(2) or f"Section {section_num}"
                toc_entries.append({
                    'title': line,
                    'page_number': 0,
                    'level': 2,
                    'section_number': section_num
                })
                continue
            
            # Numbered list patterns (like "1.", "1.1", etc.)
            numbered_match = re.match(r'^(\d+(?:\.\d+)*)\.\s+(.+)', line)
            if numbered_match:
                number = numbered_match.group(1)
                title = numbered_match.group(2)
                level = len(number.split('.'))
                toc_entries.append({
                    'title': line,
                    'page_number': 0,
                    'level': min(level, 3),  # Cap at level 3
                    'number': number
                })
        
        return toc_entries
    
    def _determine_segmentation_strategy(
        self, 
        doc_type: DocumentType, 
        page_count: int, 
        toc: Optional[TableOfContents]
    ) -> SegmentationType:
        """Determine how to segment the document."""
        
        if doc_type == DocumentType.MUNICIPAL_CODE:
            return SegmentationType.CHAPTER_BASED
        elif doc_type in [DocumentType.MEETING_AGENDA, DocumentType.MEETING_PACKET]:
            if page_count > 50:
                return SegmentationType.SECTION_BASED
            else:
                return SegmentationType.SINGLE_FILE
        elif page_count > 100 and toc is not None:
            return SegmentationType.SECTION_BASED
        else:
            return SegmentationType.SINGLE_FILE
    
    def _segment_by_chapters(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Segment municipal code by chapters."""
        # TODO: Implement chapter detection from TOC
        logger.warning("Chapter segmentation not implemented, using single file")
        return [DocumentSegment(
            source_path=pdf_path,
            start_page=1,
            end_page=analysis.page_count,
            title="Complete Document",
            segment_type="chapter",
            metadata=analysis.metadata
        )]
    
    def _segment_by_sections(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Segment by major sections."""
        logger.warning("Section segmentation not implemented, using single file")
        return [DocumentSegment(
            source_path=pdf_path,
            start_page=1,
            end_page=analysis.page_count,
            title="Complete Document",
            segment_type="section",
            metadata=analysis.metadata
        )]
    
    def _segment_by_agenda_items(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Segment meeting documents by agenda items."""
        logger.info("Segmenting meeting document using agenda item-based approach")
        
        if not analysis.toc or not analysis.toc.entries:
            logger.warning("No TOC found, using single document processing")
            return [DocumentSegment(
                source_path=pdf_path,
                start_page=1,
                end_page=analysis.page_count,
                title="Complete Agenda", 
                segment_type="agenda",
                metadata=analysis.metadata
            )]
        
        # Create segments based on TOC structure
        segments = []
        sorted_entries = sorted(analysis.toc.entries, key=lambda x: x.get('page_number', 0))
        
        # Filter for reasonable agenda items (level 1 and 2)
        agenda_entries = [entry for entry in sorted_entries 
                         if entry.get('level', 1) <= 2 and entry.get('page_number', 0) > 0]
        
        logger.info(f"Processing {len(agenda_entries)} agenda-level entries from {len(analysis.toc.entries)} total TOC entries")
        
        for i, entry in enumerate(agenda_entries):
            start_page = entry.get('page_number', 1)
            
            # Find end page (start of next agenda item or end of document)
            if i + 1 < len(agenda_entries):
                end_page = agenda_entries[i + 1].get('page_number', analysis.page_count) - 1
            else:
                end_page = analysis.page_count
            
            # Skip very small segments (less than 1 page)
            if end_page < start_page:
                continue
            
            # Create segment
            title = entry.get('title', f'Agenda Item {i+1}')
            level = entry.get('level', 1)
            section_id = entry.get('id', str(i))
            
            segment = DocumentSegment(
                source_path=pdf_path,
                start_page=start_page,
                end_page=end_page,
                title=title,
                segment_type=f"agenda_item_level_{level}",
                metadata={
                    **analysis.metadata,
                    'original_toc_entry': entry,
                    'agenda_item_index': i,
                    'agenda_item_level': level,
                    'page_count': end_page - start_page + 1
                },
                level=level,
                section_id=section_id
            )
            
            segments.append(segment)
        
        if not segments:
            logger.warning("No valid agenda segments created, using single document")
            return [DocumentSegment(
                source_path=pdf_path,
                start_page=1,
                end_page=analysis.page_count,
                title="Complete Meeting Document",
                segment_type="complete_agenda",
                metadata=analysis.metadata
            )]
        
        logger.info(f"Created {len(segments)} agenda-based segments")
        return segments
    
    def _segment_by_pages(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Segment by page ranges."""
        # For very large documents, split into manageable chunks
        chunk_size = 50  # pages per chunk
        segments = []
        
        for i in range(0, analysis.page_count, chunk_size):
            start_page = i + 1
            end_page = min(i + chunk_size, analysis.page_count)
            
            segments.append(DocumentSegment(
                source_path=pdf_path,
                start_page=start_page,
                end_page=end_page,
                title=f"Pages {start_page}-{end_page}",
                segment_type="page_range",
                metadata=analysis.metadata
            ))
        
        return segments
    
    def _create_placeholder_markdown(self, segment: DocumentSegment) -> str:
        """Create placeholder markdown content."""
        return f"""# {segment.title}

**Document Segment Information:**
- Source: {segment.source_path.name}
- Pages: {segment.start_page}-{segment.end_page}
- Type: {segment.segment_type}

*Note: This is a placeholder. Full content will be available when Docling integration is complete.*

## Processing Status
- ⏳ Awaiting Docling integration for PDF content extraction
- 🔄 Placeholder content generated on {Path(__file__).stat().st_mtime}

## Next Steps
1. Integrate IBM Docling for PDF processing
2. Extract actual content with OCR and table detection
3. Preserve document structure and formatting
4. Generate cross-references and metadata
"""
    
    def _extract_references(self, content: str) -> List[str]:
        """Extract cross-references from content."""
        # TODO: Implement reference extraction
        return []
    
    @abstractmethod
    def process(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Process a complete document.
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output files
            
        Returns:
            Processing results dictionary
        """
        pass


class DocumentProcessor(UniversalDocumentProcessor):
    """Standard document processor for meeting documents."""
    
    def process(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Process a meeting document.
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output files
            
        Returns:
            Processing results
        """
        # Analyze document
        analysis = self.analyze_document(pdf_path)
        
        # Segment if needed
        segments = self.segment_document(pdf_path, analysis)
        
        # Process segments
        processed_docs = []
        for segment in segments:
            processed_doc = self.process_segment(segment)
            
            # Save to output directory
            output_file = output_dir / f"{segment.title.replace(' ', '-').lower()}.md"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(processed_doc.content)
            
            processed_doc.output_path = output_file
            processed_docs.append(processed_doc)
        
        return {
            'status': 'completed',
            'analysis': analysis,
            'processed_documents': processed_docs,
            'output_directory': output_dir
        }
    
    def process_meeting_documents(self, meeting_dir: Path, force: bool = False) -> List[Dict[str, Any]]:
        """Process all PDF documents in a meeting directory.
        
        Args:
            meeting_dir: Meeting directory containing originals/ subdirectory
            force: If True, reprocess existing files
            
        Returns:
            List of processing results
        """
        originals_dir = meeting_dir / 'originals'
        markdown_dir = meeting_dir / 'markdown'
        
        if not originals_dir.exists():
            raise FileNotFoundError(f"Originals directory not found: {originals_dir}")
        
        # Find PDF files
        pdf_files = list(originals_dir.glob('*.pdf'))
        if not pdf_files:
            raise FileNotFoundError(f"No PDF files found in: {originals_dir}")
        
        # Process each PDF
        results = []
        for pdf_file in pdf_files:
            logger.info(f"Processing: {pdf_file.name}")
            
            # Check if already processed
            expected_output = markdown_dir / f"{pdf_file.stem}.md"
            if expected_output.exists() and not force:
                logger.info(f"Skipping {pdf_file.name} (already processed, use --force to reprocess)")
                continue
            
            try:
                result = self.process(pdf_file, markdown_dir)
                results.append({
                    'filename': pdf_file.name,
                    'status': 'success',
                    'markdown_file': expected_output.name,
                    'result': result
                })
            except Exception as e:
                logger.error(f"Failed to process {pdf_file.name}: {e}")
                results.append({
                    'filename': pdf_file.name,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results