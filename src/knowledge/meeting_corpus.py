"""Meeting document corpus for knowledge retrieval."""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from knowledge.base_knowledge_provider import KnowledgeProvider
from schemas import Evidence, DocumentChunk, MeetingContext, AgendaItem

logger = logging.getLogger(__name__)


class MeetingCorpus(KnowledgeProvider):
    """Knowledge provider for meeting documents.
    
    Indexes meeting documents from processed markdown files and provides
    search capabilities for the meeting expert agent.
    """
    
    def __init__(self, meeting_dir: str, config: Dict[str, Any]):
        """Initialize meeting corpus.
        
        Args:
            meeting_dir: Path to meeting directory with processed markdown
            config: Configuration for corpus indexing and search
        """
        super().__init__(f"meeting_{Path(meeting_dir).name}", config)
        
        self.meeting_dir = Path(meeting_dir)
        self.markdown_dir = self.meeting_dir / "markdown"
        self.index_dir = self.meeting_dir / ".index"
        
        # Ensure directories exist
        self.index_dir.mkdir(exist_ok=True)
        
        # Index file paths
        self.metadata_file = self.index_dir / "meeting_index.json"
        self.chunks_file = self.index_dir / "chunks.jsonl"
        
        # In-memory indices
        self.documents = {}
        self.chunks = {}
        self.agenda_items = []
        self.meeting_context = None
        
        # Load existing index if available
        self._load_existing_index()
    
    def index_corpus(self, source_paths: List[Path] = None, force_rebuild: bool = False) -> bool:
        """Index meeting documents for search.
        
        Args:
            source_paths: Paths to documents (unused - we use meeting structure)
            force_rebuild: If True, rebuild index even if it exists
            
        Returns:
            bool: True if indexing succeeded
        """
        try:
            if self.indexed and not force_rebuild:
                logger.info(f"Meeting corpus already indexed: {self.corpus_id}")
                return True
            
            logger.info(f"Indexing meeting corpus: {self.meeting_dir}")
            
            # Load meeting metadata
            metadata_path = self.markdown_dir / "metadata.json"
            if not metadata_path.exists():
                logger.error(f"Meeting metadata not found: {metadata_path}")
                return False
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                raw_metadata = json.load(f)
            
            # Load and process all documents
            self._process_meeting_documents(raw_metadata)
            
            # Load index document if available
            self._process_index_document()
            
            # Save index to disk
            self._save_index()
            
            self.indexed = True
            logger.info(f"Successfully indexed {len(self.documents)} documents with {len(self.chunks)} chunks")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to index meeting corpus: {e}")
            return False
    
    def search(self, query: str, filters: Dict[str, Any] = None, top_k: int = 10) -> List[Evidence]:
        """Search meeting documents for relevant evidence.
        
        Args:
            query: Search query string
            filters: Optional filters (document_type, agenda_item_id, etc.)
            top_k: Maximum number of results to return
            
        Returns:
            List of Evidence objects ranked by relevance
        """
        if not self.indexed:
            logger.warning("Corpus not indexed, attempting to index now")
            if not self.index_corpus():
                return []
        
        start_time = time.time()
        query_lower = query.lower()
        scored_chunks = []
        
        # Simple keyword-based search with basic scoring
        for chunk_id, chunk in self.chunks.items():
            score = self._calculate_relevance_score(query_lower, chunk)
            
            if score > 0:
                # Apply filters if provided
                if filters and not self._apply_filters(chunk, filters):
                    continue
                
                # Create evidence object
                evidence = Evidence(
                    chunk_id=chunk_id,
                    file_path=chunk.file_path,
                    content=chunk.content,
                    relevance_score=score,
                    source_type=chunk.metadata.get('document_type', 'unknown'),
                    metadata=chunk.metadata,
                    anchor=chunk.metadata.get('anchor'),
                    start_char=chunk.start_char,
                    end_char=chunk.end_char
                )
                
                scored_chunks.append(evidence)
        
        # Sort by relevance score and return top results
        scored_chunks.sort(key=lambda x: x.relevance_score, reverse=True)
        
        search_time = int((time.time() - start_time) * 1000)
        logger.debug(f"Search completed in {search_time}ms, found {len(scored_chunks)} results")
        
        return scored_chunks[:top_k]
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get full document by ID.
        
        Args:
            doc_id: Document identifier (filename)
            
        Returns:
            Document data if found
        """
        return self.documents.get(doc_id)
    
    def get_agenda_items(self) -> List[AgendaItem]:
        """Get all agenda items for this meeting.
        
        Returns:
            List of AgendaItem objects
        """
        return self.agenda_items
    
    def get_agenda_item(self, item_id: str) -> Optional[AgendaItem]:
        """Get specific agenda item by ID.
        
        Args:
            item_id: Agenda item identifier
            
        Returns:
            AgendaItem if found
        """
        for item in self.agenda_items:
            if item.id == item_id or item.item_number == item_id:
                return item
        return None
    
    def get_meeting_context(self) -> Optional[MeetingContext]:
        """Get complete meeting context.
        
        Returns:
            MeetingContext object with all meeting data
        """
        return self.meeting_context
    
    def _process_meeting_documents(self, raw_metadata: Dict[str, Any]):
        """Process all meeting documents and create searchable chunks."""
        self.documents = {}
        self.chunks = {}
        self.agenda_items = []
        
        # Process each document from metadata
        for doc_info in raw_metadata.get('documents', []):
            filename = doc_info['filename']
            file_path = self.markdown_dir / filename
            
            if not file_path.exists():
                logger.warning(f"Document file not found: {file_path}")
                continue
            
            try:
                # Load document content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Create document entry
                doc_data = {
                    'filename': filename,
                    'content': content,
                    'metadata': doc_info,
                    'path': str(file_path)
                }
                self.documents[filename] = doc_data
                
                # Create agenda item if this is an agenda item document
                agenda_item = self._create_agenda_item(doc_info, content)
                if agenda_item:
                    self.agenda_items.append(agenda_item)
                
                # Create searchable chunks
                self._create_document_chunks(filename, content, doc_info)
                
            except Exception as e:
                logger.error(f"Error processing document {filename}: {e}")
        
        # Create meeting context
        self.meeting_context = MeetingContext(
            meeting_dir=str(self.meeting_dir),
            metadata=raw_metadata,
            documents=list(self.documents.values()),
            agenda_items=self.agenda_items,
            processing_date=datetime.utcnow(),
            total_documents=len(self.documents),
            total_pages=sum(doc.get('page_count', 0) for doc in raw_metadata.get('documents', []))
        )
    
    def _create_agenda_item(self, doc_info: Dict[str, Any], content: str) -> Optional[AgendaItem]:
        """Create agenda item from document info."""
        try:
            # Extract item number from segment title or filename
            segment_title = doc_info.get('segment_title', '')
            filename = doc_info.get('filename', '')
            
            # Try to extract item number (e.g., "1B", "5A", etc.)
            item_match = re.search(r'(\d+[A-Z]?)', segment_title)
            if not item_match:
                item_match = re.search(r'--(\d+)-([A-Z])-', filename)
                if item_match:
                    item_number = f"{item_match.group(1)}{item_match.group(2)}"
                else:
                    return None
            else:
                item_number = item_match.group(1)
            
            # Determine section from content or title
            section = "UNKNOWN"
            title = segment_title.strip()
            
            # Try to extract section from title
            if 'administrator' in title.lower():
                section = "ADMINISTRATIVE"
            elif 'public hearing' in title.lower():
                section = "PUBLIC HEARINGS"
            elif any(word in title.lower() for word in ['consider', 'approval', 'receipt']):
                section = "NEW BUSINESS"
            
            # Create corresponding PDF segment path
            pdf_segment = None
            pdf_segments_dir = self.markdown_dir / 'pdf-segments'
            if pdf_segments_dir.exists():
                # Look for matching PDF segment
                for pdf_file in pdf_segments_dir.glob('*.pdf'):
                    if item_number.lower() in pdf_file.name.lower():
                        pdf_segment = str(pdf_file.relative_to(self.meeting_dir))
                        break
            
            return AgendaItem(
                id=item_number,
                section=section,
                item_number=item_number,
                title=title,
                description=self._extract_description(content),
                markdown_file=doc_info.get('filename'),
                pdf_segment=pdf_segment,
                page_range=doc_info.get('page_range'),
                page_count=doc_info.get('page_count'),
                metadata=doc_info,
                keywords=self._extract_keywords(content, max_keywords=10)
            )
            
        except Exception as e:
            logger.error(f"Error creating agenda item: {e}")
            return None
    
    def _extract_description(self, content: str) -> Optional[str]:
        """Extract brief description from document content."""
        # Remove markdown headers and formatting
        clean_content = re.sub(r'#+\s*', '', content)
        clean_content = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_content)
        clean_content = re.sub(r'`([^`]+)`', r'\1', clean_content)
        
        # Get first substantial paragraph
        paragraphs = [p.strip() for p in clean_content.split('\n\n') if p.strip()]
        
        for para in paragraphs:
            # Skip document headers and metadata
            if any(skip in para.lower() for skip in ['document information', 'meeting document context', 'source:', 'pages:']):
                continue
            if len(para) > 50:  # Substantial paragraph
                return para[:200] + '...' if len(para) > 200 else para
        
        return None
    
    def _create_document_chunks(self, filename: str, content: str, doc_info: Dict[str, Any]):
        """Create searchable chunks from document content."""
        chunk_size = self.config.get('knowledge', {}).get('meeting_corpus', {}).get('chunk_size', 1000)
        chunk_overlap = self.config.get('knowledge', {}).get('meeting_corpus', {}).get('chunk_overlap', 200)
        
        # Split content into chunks
        text_chunks = self._chunk_text(content, chunk_size, chunk_overlap)
        
        for i, chunk_text in enumerate(text_chunks):
            chunk_id = f"{filename}_chunk_{i:03d}"
            
            # Calculate character positions
            start_char = i * (chunk_size - chunk_overlap)
            end_char = start_char + len(chunk_text)
            
            # Create chunk metadata
            chunk_metadata = {
                'document_type': self._determine_document_type(filename),
                'filename': filename,
                'chunk_index': i,
                'page_range': doc_info.get('page_range'),
                'segment_title': doc_info.get('segment_title', ''),
                'source_file': doc_info.get('source_file', '')
            }
            
            # Create document chunk
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                file_path=filename,
                content=chunk_text,
                start_char=start_char,
                end_char=end_char,
                metadata=chunk_metadata,
                keywords=self._extract_keywords(chunk_text, max_keywords=5)
            )
            
            self.chunks[chunk_id] = chunk
    
    def _process_index_document(self):
        """Process the meeting index document if available."""
        index_path = self.markdown_dir / "index.md"
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    index_content = f.read()
                
                # Add index as a special document
                self.documents['index.md'] = {
                    'filename': 'index.md',
                    'content': index_content,
                    'metadata': {'document_type': 'index', 'special': True},
                    'path': str(index_path)
                }
                
                # Create chunks for the index
                self._create_document_chunks('index.md', index_content, {'document_type': 'index'})
                
            except Exception as e:
                logger.error(f"Error processing index document: {e}")
    
    def _determine_document_type(self, filename: str) -> str:
        """Determine document type from filename."""
        filename_lower = filename.lower()
        
        if 'index.md' in filename_lower:
            return 'index'
        elif 'administrator' in filename_lower:
            return 'administrative'
        elif 'minutes' in filename_lower:
            return 'minutes'
        elif 'agenda' in filename_lower:
            return 'agenda'
        else:
            return 'agenda_item'
    
    def _calculate_relevance_score(self, query: str, chunk: DocumentChunk) -> float:
        """Calculate relevance score for a chunk given a query."""
        score = 0.0
        content_lower = chunk.content.lower()
        
        # Exact phrase matching (highest weight)
        if query in content_lower:
            score += 3.0
        
        # Individual word matching
        query_words = query.split()
        for word in query_words:
            if len(word) < 3:  # Skip short words
                continue
            
            word_count = content_lower.count(word)
            if word_count > 0:
                # Boost score based on frequency and word importance
                word_score = min(word_count * 0.5, 2.0)  # Cap at 2.0 per word
                score += word_score
        
        # Keyword matching (medium weight)
        for keyword in chunk.keywords:
            for word in query_words:
                if word.lower() in keyword.lower():
                    score += 1.0
        
        # Document type bonuses
        doc_type = chunk.metadata.get('document_type', '')
        if doc_type == 'index' and any(word in query for word in ['agenda', 'what', 'overview']):
            score += 2.0  # Boost index for overview questions
        elif doc_type == 'agenda_item' and any(word in query for word in ['item', 'specific']):
            score += 1.5  # Boost agenda items for specific questions
        
        # Normalize by content length to prevent long chunks from dominating
        if len(chunk.content) > 0:
            score = score / (len(chunk.content) / 1000.0) ** 0.5
        
        return score
    
    def _apply_filters(self, chunk: DocumentChunk, filters: Dict[str, Any]) -> bool:
        """Apply search filters to chunk."""
        for filter_key, filter_value in filters.items():
            chunk_value = chunk.metadata.get(filter_key)
            
            if filter_key == 'document_type' and chunk_value != filter_value:
                return False
            elif filter_key == 'agenda_item_id':
                # Check if chunk is from specific agenda item
                filename = chunk.metadata.get('filename', '')
                if filter_value not in filename:
                    return False
        
        return True
    
    def _load_existing_index(self):
        """Load existing index from disk if available."""
        try:
            if self.metadata_file.exists() and self.chunks_file.exists():
                # Load metadata
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                
                # Load chunks
                chunks = {}
                with open(self.chunks_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        chunk_data = json.loads(line)
                        chunk = DocumentChunk(**chunk_data)
                        chunks[chunk.chunk_id] = chunk
                
                # Check if index is still valid (meeting dir hasn't changed)
                if index_data.get('meeting_dir') == str(self.meeting_dir):
                    self.chunks = chunks
                    self.indexed = True
                    logger.info(f"Loaded existing index with {len(chunks)} chunks")
                    
                    # Load meeting metadata to recreate context
                    metadata_path = self.markdown_dir / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            raw_metadata = json.load(f)
                        self._recreate_meeting_context(raw_metadata)
                    
        except Exception as e:
            logger.warning(f"Could not load existing index: {e}")
    
    def _recreate_meeting_context(self, raw_metadata: Dict[str, Any]):
        """Recreate meeting context from metadata when loading existing index."""
        try:
            # Load documents and agenda items from existing data
            documents = {}
            agenda_items = []
            
            for doc_info in raw_metadata.get('documents', []):
                filename = doc_info['filename']
                file_path = self.markdown_dir / filename
                
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Add to documents dictionary
                    documents[filename] = {
                        'filename': filename,
                        'content': content,
                        'metadata': doc_info,
                        'path': str(file_path)
                    }
                    
                    # Create agenda item if not index
                    if filename != 'index.md':
                        agenda_item = self._create_agenda_item(doc_info, content)
                        if agenda_item:
                            agenda_items.append(agenda_item)
            
            # Update instance variables
            self.documents = documents
            self.agenda_items = agenda_items
            
            # Recreate meeting context
            self.meeting_context = MeetingContext(
                meeting_dir=str(self.meeting_dir),
                metadata=raw_metadata,
                documents=[],  # Not needed for analysis
                agenda_items=agenda_items,
                processing_date=datetime.utcnow(),
                total_documents=len(raw_metadata.get('documents', [])),
                total_pages=sum(doc.get('page_count', 0) for doc in raw_metadata.get('documents', []))
            )
            
            logger.debug(f"Recreated meeting context with {len(agenda_items)} agenda items")
            
        except Exception as e:
            logger.error(f"Error recreating meeting context: {e}")
    
    def _save_index(self):
        """Save index to disk."""
        try:
            # Save metadata
            index_metadata = {
                'corpus_id': self.corpus_id,
                'meeting_dir': str(self.meeting_dir),
                'indexed_at': datetime.utcnow().isoformat(),
                'document_count': len(self.documents),
                'chunk_count': len(self.chunks)
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(index_metadata, f, indent=2)
            
            # Save chunks
            with open(self.chunks_file, 'w', encoding='utf-8') as f:
                for chunk in self.chunks.values():
                    chunk_dict = {
                        'chunk_id': chunk.chunk_id,
                        'file_path': chunk.file_path,
                        'content': chunk.content,
                        'start_char': chunk.start_char,
                        'end_char': chunk.end_char,
                        'metadata': chunk.metadata,
                        'keywords': chunk.keywords
                    }
                    f.write(json.dumps(chunk_dict) + '\n')
            
            logger.info(f"Saved index to {self.index_dir}")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def _get_document_count(self) -> int:
        """Get total number of indexed documents."""
        return len(self.documents)
    
    def _get_chunk_count(self) -> int:
        """Get total number of indexed chunks."""
        return len(self.chunks)
    
    def _get_index_size_mb(self) -> float:
        """Get approximate index size in megabytes."""
        try:
            total_size = 0
            if self.index_dir.exists():
                for file_path in self.index_dir.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
            return total_size / (1024 * 1024)
        except:
            return 0.0