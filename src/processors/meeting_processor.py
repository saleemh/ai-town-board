"""Meeting Document Processor

Specialized processor for meeting documents (agendas, minutes, packets) that leverages
the universal PDF processing system with meeting-specific segmentation and formatting.

This processor handles multiple document types within meeting folders and uses 
intelligent segmentation based on document content and structure.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import time
from datetime import datetime

from .document_processor import (
    UniversalDocumentProcessor, 
    DocumentAnalysis,
    DocumentSegment, 
    ProcessedDocument,
    DocumentType,
    SegmentationType,
    TableOfContents
)

logger = logging.getLogger(__name__)


class MeetingDocumentProcessor(UniversalDocumentProcessor):
    """Specialized processor for meeting documents."""
    
    def __init__(self, config: Dict):
        """Initialize meeting document processor.
        
        Args:
            config: System configuration
        """
        super().__init__(config)
        self.meeting_config = self.segmentation_config.get('meeting_documents', {})
        self.min_segment_pages = self.meeting_config.get('min_segment_pages', 2)
        self.preserve_agenda_structure = self.meeting_config.get('preserve_agenda_structure', True)
    
    def process_meeting_directory(self, meeting_dir: Path, force: bool = False) -> Dict[str, Any]:
        """Process all PDF documents in a meeting directory.
        
        Args:
            meeting_dir: Meeting directory containing originals/ subdirectory
            force: If True, reprocess existing files
            
        Returns:
            Processing results with document information
        """
        logger.info(f"Processing meeting directory: {meeting_dir}")
        
        # Setup directory structure
        originals_dir = meeting_dir / 'originals'
        markdown_dir = meeting_dir / 'markdown'
        markdown_dir.mkdir(parents=True, exist_ok=True)
        
        # Create PDF segments directory for traceability
        pdf_segments_dir = markdown_dir / 'pdf-segments'
        pdf_segments_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean up previous files if force=True
        if force:
            self._cleanup_previous_processing(markdown_dir, pdf_segments_dir)
        
        if not originals_dir.exists():
            raise FileNotFoundError(f"Originals directory not found: {originals_dir}")
        
        # Find all PDF files
        pdf_files = list(originals_dir.glob('*.pdf'))
        if not pdf_files:
            raise FileNotFoundError(f"No PDF files found in: {originals_dir}")
        
        logger.info(f"📄 Found {len(pdf_files)} PDF files to process")
        for pdf_file in pdf_files:
            logger.info(f"   - {pdf_file.name}")
        
        # Process each PDF
        processed_documents = []
        total_start_time = time.time()
        
        for pdf_idx, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"")
            logger.info(f"📄 PROCESSING PDF {pdf_idx} of {len(pdf_files)}: {pdf_file.name}")
            
            try:
                # Check if already processed (unless force=True)
                expected_output = markdown_dir / f"{pdf_file.stem}.md"
                if expected_output.exists() and not force:
                    logger.info(f"⏭️  Skipping {pdf_file.name} (already processed, use --force to reprocess)")
                    continue
                
                # Analyze document structure
                analysis = self.analyze_document(pdf_file)
                logger.info(f"   Document type: {analysis.document_type.value}")
                logger.info(f"   Pages: {analysis.page_count}")
                logger.info(f"   TOC entries: {len(analysis.toc.entries) if analysis.toc else 0}")
                
                # Process based on document complexity
                if analysis.segmentation_strategy == SegmentationType.SINGLE_FILE:
                    # Process as single document
                    result = self._process_single_meeting_document(pdf_file, markdown_dir, pdf_segments_dir, analysis)
                    processed_documents.append(result)
                else:
                    # Process with segmentation
                    results = self._process_segmented_meeting_document(pdf_file, markdown_dir, pdf_segments_dir, analysis)
                    processed_documents.extend(results)
                
                logger.info(f"✅ Successfully processed: {pdf_file.name}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process {pdf_file.name}: {e}")
                processed_documents.append({
                    'source_file': pdf_file.name,
                    'filename': None,
                    'error': str(e),
                    'status': 'failed'
                })
        
        total_time = time.time() - total_start_time
        
        # Create master index for the meeting
        index_file = markdown_dir / 'index.md'
        self._create_meeting_index(processed_documents, index_file, meeting_dir)
        
        # Create metadata
        metadata = {
            'meeting_date': meeting_dir.name.split('-')[0:3],
            'processing_date': datetime.utcnow().isoformat() + 'Z',
            'total_pdfs': len(pdf_files),
            'processed_documents': len([d for d in processed_documents if d.get('filename')]),
            'failed_documents': len([d for d in processed_documents if d.get('error')]),
            'processing_time_minutes': total_time / 60,
            'documents': processed_documents
        }
        
        metadata_file = markdown_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"")
        logger.info(f"✅ MEETING PROCESSING COMPLETE")
        logger.info(f"   📊 Total time: {total_time/60:.1f} minutes")
        logger.info(f"   📄 Processed: {metadata['processed_documents']} documents")
        logger.info(f"   ❌ Failed: {metadata['failed_documents']} documents")
        
        return {
            'status': 'completed',
            'meeting_directory': meeting_dir,
            'processed_documents': processed_documents,
            'metadata': metadata,
            'output_files': {
                'markdown_directory': markdown_dir,
                'pdf_segments_directory': pdf_segments_dir,
                'index_file': index_file,
                'metadata_file': metadata_file
            }
        }
    
    def _process_single_meeting_document(self, pdf_path: Path, output_dir: Path, pdf_segments_dir: Path, analysis: DocumentAnalysis) -> Dict[str, Any]:
        """Process a single meeting document without segmentation."""
        logger.info(f"   Processing as single document (no segmentation)")
        
        # Create single segment
        segment = DocumentSegment(
            source_path=pdf_path,
            start_page=1,
            end_page=analysis.page_count,
            title=self._clean_filename_for_title(pdf_path.stem),
            segment_type="complete_document",
            metadata={
                **analysis.metadata,
                'document_type': analysis.document_type.value,
                'processing_strategy': 'single_document'
            }
        )
        
        # Process with PDF saving
        processed_doc = self._process_segment_with_pdf_save(segment, pdf_segments_dir)
        
        # Enhance for meeting context
        processed_doc = self._enhance_meeting_formatting(processed_doc, segment)
        
        # Save markdown
        output_file = output_dir / f"{pdf_path.stem}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(processed_doc.content)
        
        return {
            'source_file': pdf_path.name,
            'filename': output_file.name,
            'document_type': analysis.document_type.value,
            'page_count': analysis.page_count,
            'segments': 1,
            'status': 'success',
            'processing_strategy': 'single_document'
        }
    
    def _process_segmented_meeting_document(self, pdf_path: Path, output_dir: Path, pdf_segments_dir: Path, analysis: DocumentAnalysis) -> List[Dict[str, Any]]:
        """Process a meeting document with intelligent segmentation."""
        logger.info(f"   Processing with segmentation strategy: {analysis.segmentation_strategy.value}")
        
        # Segment the document
        segments = self.segment_document(pdf_path, analysis)
        logger.info(f"   Created {len(segments)} segments")
        
        processed_results = []
        
        for seg_idx, segment in enumerate(segments, 1):
            logger.info(f"      🔄 Processing segment {seg_idx}/{len(segments)}: {segment.title}")
            
            try:
                # Process segment with PDF saving
                processed_doc = self._process_segment_with_pdf_save(segment, pdf_segments_dir)
                
                # Enhance for meeting context
                processed_doc = self._enhance_meeting_formatting(processed_doc, segment)
                
                # Create safe filename for segment
                safe_filename = self._create_meeting_segment_filename(pdf_path.stem, segment, seg_idx)
                output_file = output_dir / f"{safe_filename}.md"
                
                # Save markdown
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(processed_doc.content)
                
                processed_results.append({
                    'source_file': pdf_path.name,
                    'filename': output_file.name,
                    'segment_title': segment.title,
                    'page_range': f"{segment.start_page}-{segment.end_page}",
                    'page_count': segment.end_page - segment.start_page + 1,
                    'status': 'success'
                })
                
                logger.info(f"         ✅ Segment completed: {output_file.name}")
                
            except Exception as e:
                logger.error(f"         ❌ Segment failed: {e}")
                processed_results.append({
                    'source_file': pdf_path.name,
                    'filename': None,
                    'segment_title': segment.title,
                    'error': str(e),
                    'status': 'failed'
                })
        
        return processed_results
    
    def _process_segment_with_pdf_save(self, segment: DocumentSegment, pdf_segments_dir: Path) -> ProcessedDocument:
        """Process segment and save the PDF fragment for traceability."""
        if not self.docling_converter:
            logger.warning("Docling not available, using placeholder content")
            return self._create_placeholder_meeting_document(segment)
        
        try:
            # Use the same PDF segmentation approach as municipal code
            if segment.start_page != 1 or segment.end_page < self._get_page_count(segment.source_path):
                # Create segment PDF and process
                markdown_content = self._process_pdf_segment_with_docling(segment, pdf_segments_dir)
            else:
                # Full document - still save as permanent segment
                markdown_content = self._process_full_document_with_docling_save(segment, pdf_segments_dir)
            
            return ProcessedDocument(
                content=markdown_content,
                metadata=segment.metadata,
                cross_references=self._extract_references(markdown_content)
            )
            
        except Exception as e:
            logger.error(f"Error processing segment with Docling: {e}")
            return self._create_placeholder_meeting_document(segment)
    
    def _process_full_document_with_docling_save(self, segment: DocumentSegment, pdf_segments_dir: Path) -> str:
        """Process full document and save as permanent segment."""
        import shutil
        
        # Create safe filename for the segment
        segment_filename = self._create_safe_pdf_filename(segment)
        segment_pdf_path = pdf_segments_dir / segment_filename
        
        # Copy the original file
        shutil.copy2(segment.source_path, segment_pdf_path)
        logger.info(f"      📄 Saved full document as segment: {segment_filename}")
        
        # Process with Docling
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
        
        # Add document header with metadata
        header = f"""# {segment.title}

## Document Information
- **Source**: {segment.source_path.name}
- **Pages**: {segment.start_page}-{segment.end_page}
- **PDF Segment**: {segment_filename}
- **Processing**: IBM Docling (Meeting Document)
- **Document Type**: {segment.metadata.get('document_type', 'Meeting Document')}

---

"""
        
        return header + markdown_content
    
    def _create_safe_pdf_filename(self, segment: DocumentSegment) -> str:
        """Create safe PDF filename for segment."""
        # Clean the original filename and segment title
        clean_source = re.sub(r'[^\w\s-]', '', segment.source_path.stem).strip()
        clean_title = re.sub(r'[^\w\s-]', '', segment.title).strip()
        
        # Create filename
        if segment.start_page != 1 or segment.end_page != self._get_page_count(segment.source_path):
            # Segmented file
            filename = f"{clean_source}-pg{segment.start_page}-{segment.end_page}-{clean_title}"
        else:
            # Full file
            filename = f"{clean_source}-complete"
        
        # Replace spaces and limit length
        filename = re.sub(r'\s+', '-', filename)[:80]
        return f"{filename}.pdf"
    
    def _create_meeting_segment_filename(self, source_stem: str, segment: DocumentSegment, seg_idx: int) -> str:
        """Create safe filename for meeting segment markdown."""
        # Clean source filename
        clean_source = re.sub(r'[^\w\s-]', '', source_stem).strip()
        clean_source = re.sub(r'\s+', '-', clean_source)[:30]
        
        # Clean segment title
        clean_title = re.sub(r'[^\w\s-]', '', segment.title).strip()
        clean_title = re.sub(r'\s+', '-', clean_title)[:40]
        
        # Create filename with segment index
        filename = f"{clean_source}-{seg_idx:02d}-{clean_title}"
        
        return filename[:80]  # Limit total length
    
    def _enhance_meeting_formatting(self, document: ProcessedDocument, segment: DocumentSegment) -> ProcessedDocument:
        """Enhance markdown with meeting-specific formatting."""
        
        doc_type = segment.metadata.get('document_type', 'Meeting Document')
        
        header = f"""# {segment.title}

## Meeting Document Context
- **Document Type**: {doc_type}
- **Source File**: {segment.source_path.name}
- **Page Range**: {segment.start_page}-{segment.end_page} ({segment.end_page - segment.start_page + 1} pages)
- **Processing**: IBM Docling with OCR
- **Segment Type**: {segment.segment_type.title()}

## Navigation
- **Source Document**: {segment.source_path.name}
- **Processing Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

---

"""
        
        enhanced_content = header + document.content
        
        return ProcessedDocument(
            content=enhanced_content,
            metadata={
                **document.metadata,
                'meeting_context': {
                    'document_type': doc_type,
                    'source_file': segment.source_path.name,
                    'page_range': f"{segment.start_page}-{segment.end_page}"
                }
            },
            cross_references=document.cross_references,
            output_path=document.output_path
        )
    
    def _create_placeholder_meeting_document(self, segment: DocumentSegment) -> ProcessedDocument:
        """Create placeholder ProcessedDocument for failed processing."""
        
        markdown_content = f"""# {segment.title}

**Meeting Document Information:**
- Source: {segment.source_path.name}
- Pages: {segment.start_page}-{segment.end_page}
- Type: {segment.segment_type}
- Document Type: {segment.metadata.get('document_type', 'Meeting Document')}

*Note: This is a placeholder. Processing failed or Docling not available.*

## Processing Status
- ❌ Processing failed
- 🔄 Placeholder content generated
- 📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Next Steps
1. Check Docling installation and configuration
2. Verify PDF segment creation
3. Review error logs for details
4. Ensure OCR capabilities are working for scanned documents
"""
        
        return ProcessedDocument(
            content=markdown_content,
            metadata=segment.metadata,
            cross_references=[]
        )
    
    def _clean_filename_for_title(self, filename: str) -> str:
        """Clean filename to create readable title."""
        # Remove common file patterns
        title = re.sub(r'^\d{4}-\d{2}-\d{2}\s*', '', filename)  # Remove date prefix
        title = re.sub(r'\s*-\s*(BOARD|AGENDA|PACKET|MINUTES)\s*', ' ', title, flags=re.IGNORECASE)
        
        # Replace underscores and dashes with spaces
        title = re.sub(r'[-_]+', ' ', title)
        
        # Clean up spacing
        title = ' '.join(title.split())
        
        return title.strip() or filename
    
    def _create_meeting_index(self, processed_documents: List[Dict[str, Any]], index_file: Path, meeting_dir: Path):
        """Create master index for meeting documents."""
        
        meeting_name = meeting_dir.name
        successful_docs = [d for d in processed_documents if d.get('filename')]
        failed_docs = [d for d in processed_documents if d.get('error')]
        
        content = f"""# Meeting Documents: {meeting_name}

## Processing Summary

**Meeting Directory**: {meeting_name}  
**Processing Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  
**Total Documents**: {len(processed_documents)}  
**Successfully Processed**: {len(successful_docs)}  
**Failed Processing**: {len(failed_docs)}

## Documents

"""
        
        # Group by source file
        source_files = {}
        for doc in successful_docs:
            source = doc.get('source_file', 'Unknown')
            if source not in source_files:
                source_files[source] = []
            source_files[source].append(doc)
        
        for source_file, docs in source_files.items():
            content += f"### 📄 {source_file}\n\n"
            
            if len(docs) == 1:
                doc = docs[0]
                content += f"- **File**: [{doc['filename']}]({doc['filename']})\n"
                if 'page_count' in doc:
                    content += f"- **Pages**: {doc['page_count']}\n"
                if 'document_type' in doc:
                    content += f"- **Type**: {doc['document_type']}\n"
            else:
                content += f"**Segments**: {len(docs)}\n\n"
                for doc in docs:
                    content += f"- [{doc['filename']}]({doc['filename']}) - {doc.get('segment_title', 'Untitled')}\n"
                    if 'page_range' in doc:
                        content += f"  - Pages: {doc['page_range']}\n"
            
            content += "\n"
        
        # Add failed documents
        if failed_docs:
            content += "## Processing Failures\n\n"
            for doc in failed_docs:
                content += f"- ❌ **{doc['source_file']}**: {doc.get('error', 'Unknown error')}\n"
            content += "\n"
        
        content += """## Usage

Each document has been processed with IBM Docling for optimal text extraction and OCR.
PDF segments are preserved in the `pdf-segments/` directory for complete traceability.

For questions about specific agenda items or meeting content, refer to the individual document files above.
"""
        
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"📄 Created meeting index: {index_file.name}")
    
    def _detect_document_type(self, pdf_path: Path) -> DocumentType:
        """Detect meeting document type based on filename and content."""
        filename = pdf_path.name.lower()
        
        # Meeting document patterns
        if 'agenda' in filename:
            return DocumentType.MEETING_AGENDA
        elif 'minutes' in filename:
            return DocumentType.MEETING_MINUTES  
        elif 'packet' in filename or 'board' in filename:
            return DocumentType.MEETING_PACKET
        else:
            # Analyze TOC to determine if it's a complex multi-document packet
            toc = self._extract_table_of_contents(pdf_path)
            if toc and len(toc.entries) > 10:  # Likely a complex packet
                return DocumentType.MEETING_PACKET
            else:
                return DocumentType.MEETING_AGENDA  # Default for meeting docs
    
    def _determine_segmentation_strategy(self, doc_type: DocumentType, page_count: int, toc: Optional[TableOfContents]) -> SegmentationType:
        """Determine how to segment meeting documents."""
        
        # For meeting documents, use different thresholds than municipal code
        if doc_type == DocumentType.MEETING_PACKET:
            if toc and len(toc.entries) > 5:
                return SegmentationType.AGENDA_ITEM_BASED  # Segment by agenda items (packets have agenda items too)
            elif page_count > 20:
                return SegmentationType.PAGE_BASED     # Large packet, segment by page ranges
            else:
                return SegmentationType.SINGLE_FILE
        
        elif doc_type == DocumentType.MEETING_AGENDA:
            if toc and len(toc.entries) > 3:
                return SegmentationType.AGENDA_ITEM_BASED  # Segment by agenda items
            elif page_count > 15:
                return SegmentationType.AGENDA_ITEM_BASED  # Large agenda, still use agenda items
            else:
                return SegmentationType.SINGLE_FILE
        
        elif doc_type == DocumentType.MEETING_MINUTES:
            if page_count > 25:
                return SegmentationType.SECTION_BASED      # Long minutes, segment by topics
            else:
                return SegmentationType.SINGLE_FILE
        
        else:
            return SegmentationType.SINGLE_FILE
    
    def process(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Process a single meeting document.
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output files
            
        Returns:
            Processing results dictionary
        """
        # This method is required by the abstract base class
        # but for meetings, we use process_meeting_directory instead
        # This method handles the case where someone calls the base process method
        
        # Analyze document
        analysis = self.analyze_document(pdf_path)
        
        # Create a temporary meeting directory structure
        temp_meeting_dir = output_dir.parent
        temp_originals_dir = temp_meeting_dir / 'originals'
        temp_originals_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy PDF to originals directory temporarily if not already there
        if pdf_path.parent.name != 'originals':
            import shutil
            temp_pdf_path = temp_originals_dir / pdf_path.name
            shutil.copy2(pdf_path, temp_pdf_path)
            pdf_path = temp_pdf_path
        
        # Process using the meeting directory method
        result = self.process_meeting_directory(temp_meeting_dir, force=True)
        
        return {
            'status': 'completed',
            'analysis': analysis,
            'processed_documents': result['processed_documents'],
            'output_directory': output_dir
        }
    
    def _cleanup_previous_processing(self, markdown_dir: Path, pdf_segments_dir: Path):
        """Clean up all previous markdown files and PDF segments when using --force."""
        logger.info("🧹 Cleaning up previous processing files...")
        
        cleanup_count = 0
        
        # Remove all existing markdown files (except directories)
        for file_path in markdown_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.md':
                file_path.unlink()
                cleanup_count += 1
                logger.debug(f"   Removed: {file_path.name}")
            elif file_path.is_file() and file_path.name in ['metadata.json']:
                file_path.unlink()
                cleanup_count += 1
                logger.debug(f"   Removed: {file_path.name}")
        
        # Remove all existing PDF segments
        if pdf_segments_dir.exists():
            for pdf_file in pdf_segments_dir.iterdir():
                if pdf_file.is_file() and pdf_file.suffix == '.pdf':
                    pdf_file.unlink()
                    cleanup_count += 1
                    logger.debug(f"   Removed PDF segment: {pdf_file.name}")
        
        if cleanup_count > 0:
            logger.info(f"   ✅ Cleaned up {cleanup_count} previous files")
        else:
            logger.info("   ℹ️  No previous files to clean up")