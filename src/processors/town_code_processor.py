"""Town Code Document Processor

Specialized processor for municipal code documents that leverages the universal PDF processing
system with town code-specific segmentation and formatting.

This processor uses the PDF's built-in Table of Contents to intelligently segment the
municipal code into chapter-based markdown files for optimal navigation and AI analysis.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import re
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


class TownCodeProcessor(UniversalDocumentProcessor):
    """Specialized processor for municipal code documents."""
    
    def __init__(self, config: Dict):
        """Initialize town code processor.
        
        Args:
            config: System configuration
        """
        super().__init__(config)
        self.town_code_config = self.segmentation_config.get('municipal_code', {})
        self.min_chapter_pages = self.town_code_config.get('min_chapter_pages', 3)
        self.preserve_legal_numbering = self.town_code_config.get('preserve_legal_numbering', True)
    
    def process(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Process municipal code PDF into chapter-based markdown files.
        
        Args:
            pdf_path: Path to the municipal code PDF
            output_dir: Directory for chapter markdown files
            
        Returns:
            Processing results with chapter information
        """
        logger.info(f"Processing municipal code: {pdf_path}")
        
        # Analyze the document structure
        analysis = self.analyze_document(pdf_path)
        
        if analysis.document_type != DocumentType.MUNICIPAL_CODE:
            logger.warning(f"Document type detected as {analysis.document_type}, not municipal code")
        
        # Create output structure
        chapters_dir = output_dir / 'chapters'
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        # Create PDF segments directory for traceability
        pdf_segments_dir = output_dir / 'pdf-segments'
        pdf_segments_dir.mkdir(parents=True, exist_ok=True)
        
        # Segment by chapters using TOC
        segments = self.segment_document(pdf_path, analysis)
        
        total_segments = len(segments)
        total_pages = sum(seg.end_page - seg.start_page + 1 for seg in segments)
        
        logger.info(f"📚 PROCESSING PLAN:")
        logger.info(f"   Total segments: {total_segments}")
        logger.info(f"   Total pages: {total_pages}")
        logger.info(f"   Estimated processing time: {total_segments * 2}-{total_segments * 5} minutes")
        logger.info(f"   Each segment will be processed individually with Docling")
        
        # Process each chapter with hierarchical context
        processed_chapters = []
        start_time = time.time()
        
        for idx, segment in enumerate(segments, 1):
            current_time = time.time()
            elapsed = current_time - start_time
            
            logger.info(f"")
            logger.info(f"🔄 PROCESSING SEGMENT {idx} of {total_segments}")
            logger.info(f"   Section: {segment.hierarchical_path or segment.title}")
            logger.info(f"   Pages: {segment.start_page}-{segment.end_page} ({segment.end_page - segment.start_page + 1} pages)")
            logger.info(f"   Progress: {idx-1}/{total_segments} completed ({((idx-1)/total_segments)*100:.1f}%)")
            
            if idx > 1:  # Show time estimates after first segment
                avg_time_per_segment = elapsed / (idx - 1)
                remaining_segments = total_segments - idx + 1
                estimated_remaining = avg_time_per_segment * remaining_segments
                logger.info(f"   Elapsed: {elapsed/60:.1f} minutes")
                logger.info(f"   Estimated remaining: {estimated_remaining/60:.1f} minutes")
                logger.info(f"   Average per segment: {avg_time_per_segment/60:.1f} minutes")
            
            segment_start_time = time.time()
            
            try:
                logger.info(f"   🔄 Starting Docling processing for segment...")
                chapter_doc = self.process_segment_with_pdf_save(segment, pdf_segments_dir)
                
                logger.info(f"   ✅ Docling processing complete, enhancing formatting...")
                # Enhanced processing for legal documents with hierarchical context
                chapter_doc = self._enhance_legal_formatting_with_hierarchy(chapter_doc, segment)
                chapter_doc = self._extract_legal_definitions(chapter_doc)
                
                # Use hierarchical filename
                safe_filename = segment.get_safe_filename()
                output_file = chapters_dir / f"{safe_filename}.md"
                
                logger.info(f"   💾 Saving to: {output_file.name}")
                # Save chapter markdown
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(chapter_doc.content)
                
                chapter_doc.output_path = output_file
                
                segment_time = time.time() - segment_start_time
                logger.info(f"   ✅ SEGMENT {idx} COMPLETED in {segment_time/60:.1f} minutes")
                logger.info(f"      File: {output_file.name}")
                logger.info(f"      Content length: {len(chapter_doc.content)} characters")
                
                processed_chapters.append({
                    'title': segment.title,
                    'filename': output_file.name,
                    'hierarchical_path': segment.hierarchical_path,
                    'level': segment.level,
                    'section_id': segment.section_id,
                    'chapter_number': segment.metadata.get('chapter_number'),
                    'page_range': f"{segment.start_page}-{segment.end_page}",
                    'page_count': segment.end_page - segment.start_page + 1,
                    'child_sections_count': len(segment.metadata.get('child_sections', [])),
                    'document': chapter_doc,
                    'segment_metadata': segment.metadata,
                    'processing_time_minutes': segment_time / 60
                })
                
            except Exception as e:
                segment_time = time.time() - segment_start_time
                logger.error(f"   ❌ SEGMENT {idx} FAILED after {segment_time/60:.1f} minutes")
                logger.error(f"      Error: {e}")
                logger.error(f"      Section: {segment.title}")
                
                processed_chapters.append({
                    'title': segment.title,
                    'filename': None,
                    'error': str(e),
                    'status': 'failed',
                    'processing_time_minutes': segment_time / 60,
                    'hierarchical_path': segment.hierarchical_path
                })
        
        # Generate cross-references and search index
        cross_references = self._generate_cross_references(processed_chapters)
        search_index = self._build_search_index(processed_chapters)
        
        # Create master index file
        index_file = output_dir / 'index.md'
        self._create_master_index(processed_chapters, index_file, analysis)
        
        # Create metadata file
        metadata = {
            'source_file': pdf_path.name,
            'processing_date': datetime.utcnow().isoformat() + 'Z',
            'total_pages': analysis.page_count,
            'total_chapters': len(processed_chapters),
            'successful_chapters': len([c for c in processed_chapters if c.get('filename')]),
            'document_type': analysis.document_type.value,
            'segmentation_strategy': analysis.segmentation_strategy.value,
            'chapters': [
                {
                    'title': c['title'],
                    'filename': c.get('filename'),
                    'chapter_number': c.get('chapter_number'),
                    'page_range': c.get('page_range'),
                    'status': 'success' if c.get('filename') else 'failed'
                }
                for c in processed_chapters
            ]
        }
        
        metadata_file = output_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Create search index file
        search_index_file = output_dir / 'search-index.json'
        with open(search_index_file, 'w', encoding='utf-8') as f:
            json.dump(search_index, f, indent=2)
        
        return {
            'status': 'completed',
            'analysis': analysis,
            'processed_chapters': processed_chapters,
            'cross_references': cross_references,
            'search_index': search_index,
            'output_files': {
                'chapters_directory': chapters_dir,
                'index_file': index_file,
                'metadata_file': metadata_file,
                'search_index_file': search_index_file
            }
        }
    
    def _segment_by_chapters(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Segment municipal code by chapters using hierarchical PDF TOC.
        
        This method uses the PDF's built-in table of contents to create intelligent
        segments that preserve the hierarchical structure of the municipal code.
        """
        logger.info("Segmenting municipal code using hierarchical PDF TOC")
        
        if not analysis.toc or not analysis.toc.entries:
            logger.warning("No TOC found, falling back to single document processing")
            return [self._create_fallback_segment(pdf_path, analysis)]
        
        # Create hierarchical segments based on TOC structure
        segments = self._create_hierarchical_segments(pdf_path, analysis.toc.entries, analysis)
        
        if not segments:
            logger.warning("No valid segments created, using single document")
            return [self._create_fallback_segment(pdf_path, analysis)]
        
        logger.info(f"Created {len(segments)} hierarchical segments")
        return segments
    
    def _create_hierarchical_segments(self, pdf_path: Path, toc_entries: List[Dict], analysis: DocumentAnalysis) -> List[DocumentSegment]:
        """Create document segments that preserve hierarchical structure."""
        segments = []
        
        # Sort entries by page number to establish sequential order
        sorted_entries = sorted(toc_entries, key=lambda x: x.get('page_number', 0))
        
        # Filter for chapter-level entries (level 1) as primary segments
        chapter_entries = [entry for entry in sorted_entries if entry.get('level', 1) == 1]
        
        logger.info(f"Processing {len(chapter_entries)} chapter-level entries")
        
        for i, chapter_entry in enumerate(chapter_entries):
            start_page = chapter_entry.get('page_number', 1)
            
            # Find end page (start of next chapter or end of document)
            if i + 1 < len(chapter_entries):
                end_page = chapter_entries[i + 1].get('page_number', analysis.page_count) - 1
            else:
                end_page = analysis.page_count
            
            # Skip tiny segments
            if end_page - start_page + 1 < self.min_chapter_pages:
                logger.debug(f"Skipping small segment: {chapter_entry.get('title')} ({end_page - start_page + 1} pages)")
                continue
            
            # Find child sections within this chapter
            child_sections = [
                entry for entry in sorted_entries 
                if (entry.get('page_number', 0) >= start_page and 
                    entry.get('page_number', 0) <= end_page and 
                    entry.get('level', 1) > 1)
            ]
            
            # Create rich segment with hierarchical context
            segment = self._create_rich_document_segment(
                pdf_path=pdf_path,
                toc_entry=chapter_entry,
                start_page=start_page,
                end_page=end_page,
                child_sections=child_sections,
                analysis=analysis
            )
            
            segments.append(segment)
        
        return segments
    
    def _create_rich_document_segment(
        self, 
        pdf_path: Path, 
        toc_entry: Dict, 
        start_page: int, 
        end_page: int,
        child_sections: List[Dict],
        analysis: DocumentAnalysis
    ) -> DocumentSegment:
        """Create a DocumentSegment with rich hierarchical metadata."""
        
        title = toc_entry.get('title', f'Untitled Section')
        section_type = toc_entry.get('section_type', 'chapter')
        level = toc_entry.get('level', 1)
        section_id = toc_entry.get('id', 'unknown')
        
        # Build comprehensive metadata
        metadata = {
            **analysis.metadata,
            'original_toc_entry': toc_entry,
            'hierarchical_path': toc_entry.get('hierarchical_path', title),
            'section_type': section_type,
            'child_sections_count': len(child_sections),
            'child_sections': [
                {
                    'title': child.get('title'),
                    'page': child.get('page_number'),
                    'level': child.get('level'),
                    'type': child.get('section_type')
                } for child in child_sections
            ],
            'page_count': end_page - start_page + 1,
            'chapter_number': self._extract_chapter_number(title),
            'processing_context': {
                'source_document': pdf_path.name,
                'total_document_pages': analysis.page_count,
                'segment_position': f"{start_page}-{end_page} of {analysis.page_count}"
            }
        }
        
        return DocumentSegment(
            source_path=pdf_path,
            start_page=start_page,
            end_page=end_page,
            title=title,
            segment_type=section_type,
            metadata=metadata,
            level=level,
            section_id=section_id,
            parent_id=toc_entry.get('parent_id'),
            hierarchical_path=toc_entry.get('hierarchical_path'),
            chapter_context={
                'chapter_title': title if section_type == 'chapter' else None,
                'chapter_number': self._extract_chapter_number(title),
                'has_subsections': len(child_sections) > 0
            }
        )
    
    def _create_fallback_segment(self, pdf_path: Path, analysis: DocumentAnalysis) -> DocumentSegment:
        """Create a fallback segment when no TOC is available."""
        return DocumentSegment(
            source_path=pdf_path,
            start_page=1,
            end_page=analysis.page_count,
            title="Complete Municipal Code",
            segment_type="complete_code",
            metadata=analysis.metadata,
            level=1,
            section_id="complete",
            hierarchical_path="Complete Municipal Code"
        )
    
    def _identify_chapter_entries(self, toc_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify which TOC entries represent chapters.
        
        Args:
            toc_entries: List of TOC entries from PDF
            
        Returns:
            List of entries that represent chapters
        """
        chapter_entries = []
        
        for entry in toc_entries:
            title = entry.get('title', '').strip()
            level = entry.get('level', 1)
            
            # Look for chapter indicators
            if self._is_chapter_entry(title, level):
                chapter_entries.append(entry)
        
        return chapter_entries
    
    def _is_chapter_entry(self, title: str, level: int) -> bool:
        """Determine if a TOC entry represents a chapter.
        
        Args:
            title: Title of the TOC entry
            level: Hierarchical level in TOC
            
        Returns:
            True if this entry represents a chapter
        """
        title_lower = title.lower()
        
        # Common chapter patterns in municipal codes
        chapter_patterns = [
            r'^chapter\s+\d+',
            r'^ch\.\s*\d+',
            r'^§\s*\d+',
            r'^\d+\.',
            r'^article\s+[ivx]+',
            r'^part\s+[ivx]+',
        ]
        
        # Check if title matches chapter patterns
        for pattern in chapter_patterns:
            if re.match(pattern, title_lower):
                return True
        
        # If at level 1 or 2, likely a major section
        if level <= 2 and len(title) > 5:
            return True
        
        # Skip common non-chapter entries
        skip_patterns = [
            'table of contents',
            'index',
            'appendix',
            'definitions',
            'preamble',
            'introduction'
        ]
        
        for skip in skip_patterns:
            if skip in title_lower:
                return False
        
        return False
    
    def _extract_chapter_number(self, title: str) -> Optional[str]:
        """Extract chapter number from title.
        
        Args:
            title: Chapter title
            
        Returns:
            Chapter number if found
        """
        # Try different patterns for chapter numbers
        patterns = [
            r'chapter\s+(\d+)',
            r'ch\.\s*(\d+)',
            r'^(\d+)\.',
            r'§\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title.lower())
            if match:
                return match.group(1)
        
        return None
    
    def _create_safe_filename(self, title: str, chapter_number: Optional[str] = None) -> str:
        """Create a filesystem-safe filename from chapter title.
        
        Args:
            title: Chapter title
            chapter_number: Chapter number if available
            
        Returns:
            Safe filename
        """
        # Start with chapter number if available
        if chapter_number:
            safe_name = f"chapter-{chapter_number:0>3s}"
        else:
            safe_name = "chapter"
        
        # Clean up title for filename
        clean_title = re.sub(r'[^\w\s-]', '', title)
        clean_title = re.sub(r'\s+', '-', clean_title.strip())
        clean_title = clean_title.lower()[:50]  # Limit length
        
        if clean_title and clean_title != f"chapter-{chapter_number or ''}":
            safe_name += f"-{clean_title}"
        
        return safe_name
    
    def _enhance_legal_formatting_with_hierarchy(self, document: ProcessedDocument, segment: DocumentSegment) -> ProcessedDocument:
        """Enhance markdown with hierarchical legal document formatting.
        
        Args:
            document: Processed document
            segment: Original segment with hierarchical context
            
        Returns:
            Enhanced document with hierarchical legal formatting
        """
        child_sections = segment.metadata.get('child_sections', [])
        
        header = f"""# {segment.title}

## Document Context
- **Hierarchical Path**: {segment.hierarchical_path or segment.title}
- **Level**: {segment.level} ({segment.segment_type.title()})
- **Section ID**: {segment.section_id or 'N/A'}
- **Source Pages**: {segment.start_page}-{segment.end_page} ({segment.end_page - segment.start_page + 1} pages)
- **Document Position**: Pages {segment.start_page}-{segment.end_page} of {segment.metadata.get('processing_context', {}).get('total_document_pages', 'unknown')}

## Section Structure
- **Chapter Number**: {segment.metadata.get('chapter_number') or 'N/A'}
- **Contains Subsections**: {'Yes' if child_sections else 'No'} ({len(child_sections)} subsections)
- **Document Type**: Municipal Code {segment.segment_type.title()}

"""
        
        # Add subsection overview if they exist
        if child_sections:
            header += """
## Contained Subsections

| Title | Page | Level | Type |
|-------|------|--------|------|
"""
            for child in child_sections:
                header += f"| {child.get('title', 'Untitled')} | {child.get('page', 'N/A')} | {child.get('level', 'N/A')} | {child.get('type', 'section')} |\n"
        
        # Add navigation context
        header += f"""
## Navigation Context
- **Source Document**: {segment.source_path.name}
- **Total Document Pages**: {segment.metadata.get('processing_context', {}).get('total_document_pages', 'unknown')}
- **Processing Context**: Extracted from larger municipal code using Table of Contents

---

"""
        
        enhanced_content = header + document.content
        
        return ProcessedDocument(
            content=enhanced_content,
            metadata={
                **document.metadata,
                'hierarchical_context': {
                    'path': segment.hierarchical_path,
                    'level': segment.level,
                    'section_id': segment.section_id,
                    'parent_id': segment.parent_id,
                    'has_children': len(child_sections) > 0,
                    'child_count': len(child_sections)
                }
            },
            cross_references=document.cross_references,
            output_path=document.output_path
        )
    
    def _extract_legal_definitions(self, document: ProcessedDocument) -> ProcessedDocument:
        """Extract legal definitions from chapter content.
        
        Args:
            document: Processed document
            
        Returns:
            Document with extracted definitions in metadata
        """
        # TODO: Implement definition extraction
        # For now, just return the document unchanged
        return document
    
    def _generate_cross_references(self, chapters: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Generate cross-references between chapters.
        
        Args:
            chapters: List of processed chapters
            
        Returns:
            Cross-reference mapping
        """
        # TODO: Implement cross-reference detection using AI
        cross_refs = {}
        
        for chapter in chapters:
            if chapter.get('filename'):
                cross_refs[chapter['filename']] = []
        
        return cross_refs
    
    def process_segment_with_pdf_save(self, segment: DocumentSegment, pdf_segments_dir: Path) -> 'ProcessedDocument':
        """Process segment and save the PDF fragment for traceability."""
        logger.info(f"Processing segment with PDF save: {segment.title}")
        
        # Override the _process_with_docling method to pass the PDF directory
        if not hasattr(self, 'docling_converter') or not self.docling_converter:
            logger.warning("Docling not available, using placeholder content")
            return self._create_placeholder_processed_document(segment)
        
        try:
            # Process with permanent PDF saving
            if segment.start_page != 1 or segment.end_page < self._get_page_count(segment.source_path):
                # Create segment PDF and process
                markdown_content = self._process_pdf_segment_with_docling(segment, pdf_segments_dir)
            else:
                # Full document - still save as permanent segment
                markdown_content = self._process_full_document_with_docling_save(segment, pdf_segments_dir)
            
            from .document_processor import ProcessedDocument
            return ProcessedDocument(
                content=markdown_content,
                metadata=segment.metadata,
                cross_references=self._extract_references(markdown_content)
            )
            
        except Exception as e:
            logger.error(f"Error processing segment with Docling: {e}")
            return self._create_placeholder_processed_document(segment)
    
    def _process_full_document_with_docling_save(self, segment: DocumentSegment, pdf_segments_dir: Path) -> str:
        """Process full document and save as permanent segment."""
        # For full document, copy it to the segments directory
        import shutil
        segment_filename = f"{segment.get_safe_filename()}.pdf"
        segment_pdf_path = pdf_segments_dir / segment_filename
        
        # Copy the original file
        shutil.copy2(segment.source_path, segment_pdf_path)
        logger.info(f"Saved full document as segment: {segment_filename}")
        
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
- **Processing**: IBM Docling (Full Document Copy)

---

"""
        
        return header + markdown_content
    
    def _create_placeholder_processed_document(self, segment: DocumentSegment) -> 'ProcessedDocument':
        """Create a placeholder ProcessedDocument when processing fails."""
        from .document_processor import ProcessedDocument
        
        markdown_content = f"""# {segment.title}

**Document Segment Information:**
- Source: {segment.source_path.name}
- Pages: {segment.start_page}-{segment.end_page}
- Type: {segment.segment_type}

*Note: This is a placeholder. Processing failed or Docling not available.*

## Processing Status
- ❌ Processing failed
- 🔄 Placeholder content generated

## Next Steps
1. Check Docling installation and configuration
2. Verify PDF segment creation
3. Review error logs for details
"""
        
        return ProcessedDocument(
            content=markdown_content,
            metadata=segment.metadata,
            cross_references=[]
        )
    
    def _build_search_index(self, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build search index for municipal code.
        
        Args:
            chapters: List of processed chapters
            
        Returns:
            Search index structure
        """
        search_index = {
            'chapters': [],
            'keywords': {},
            'definitions': {}
        }
        
        for chapter in chapters:
            if chapter.get('filename'):
                search_index['chapters'].append({
                    'title': chapter['title'],
                    'filename': chapter['filename'],
                    'chapter_number': chapter.get('chapter_number'),
                    'page_range': chapter.get('page_range')
                })
        
        return search_index
    
    def _create_master_index(self, chapters: List[Dict[str, Any]], index_file: Path, analysis: DocumentAnalysis):
        """Create master index markdown file.
        
        Args:
            chapters: List of processed chapters
            index_file: Output path for index
            analysis: Document analysis results
        """
        content = f"""# North Castle Municipal Code

## Table of Contents

Generated from: {analysis.metadata.get('source_file', 'Unknown')}  
Total Pages: {analysis.page_count}  
Processing Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

### Chapters

"""
        
        # Group and sort chapters hierarchically
        successful_chapters = [c for c in chapters if c.get('filename')]
        
        # Sort by level and then by section_id or chapter_number
        successful_chapters.sort(key=lambda x: (
            x.get('level', 1),
            x.get('section_id', ''),
            x.get('chapter_number', 'zzz')
        ))
        
        for chapter in successful_chapters:
            level = chapter.get('level', 1)
            indent = "  " * (level - 1)  # Indent based on level
            
            chapter_num = chapter.get('chapter_number', 'N/A')
            title = chapter['title']
            filename = chapter['filename']
            page_range = chapter.get('page_range', 'N/A')
            page_count = chapter.get('page_count', 'N/A')
            child_count = chapter.get('child_sections_count', 0)
            hierarchical_path = chapter.get('hierarchical_path', title)
            
            # Create entry with hierarchical context
            level_indicator = f"L{level}" if level > 1 else "📖"
            subsection_info = f" ({child_count} subsections)" if child_count > 0 else ""
            
            content += f"{indent}- **{level_indicator} {hierarchical_path}**: [{title}](chapters/{filename})\n"
            content += f"{indent}  - Pages: {page_range} ({page_count} pages){subsection_info}\n"
        
        content += f"""

## Processing Information

- **Total Chapters**: {len([c for c in chapters if c.get('filename')])}
- **Failed Chapters**: {len([c for c in chapters if not c.get('filename')])}
- **Segmentation Strategy**: {analysis.segmentation_strategy.value}
- **Document Type**: {analysis.document_type.value}

## Usage

Each chapter is processed as a separate markdown file in the `chapters/` directory. 
Use the search index (`search-index.json`) for keyword-based lookups.

## Cross-References

Cross-references between chapters and sections are automatically detected and 
available in the individual chapter files.
"""
        
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Created master index: {index_file}")