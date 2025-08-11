"""Abstract base class for knowledge providers."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from schemas import Evidence, SearchResult, DocumentChunk

logger = logging.getLogger(__name__)


class KnowledgeProvider(ABC):
    """Abstract interface for knowledge retrieval and indexing.
    
    Different agents may use different knowledge sources (meeting documents,
    town code, etc.) with different retrieval strategies. This interface
    provides a consistent way to index corpora and search for relevant evidence.
    """
    
    def __init__(self, corpus_id: str, config: Dict[str, Any]):
        """Initialize knowledge provider.
        
        Args:
            corpus_id: Unique identifier for this knowledge corpus
            config: Configuration dictionary for this provider
        """
        self.corpus_id = corpus_id
        self.config = config
        self.indexed = False
        
        logger.info(f"Initializing knowledge provider for corpus: {corpus_id}")
    
    @abstractmethod
    def index_corpus(self, source_paths: List[Path], force_rebuild: bool = False) -> bool:
        """Index a corpus of documents for retrieval.
        
        Args:
            source_paths: List of paths to documents to index
            force_rebuild: If True, rebuild index even if it exists
            
        Returns:
            bool: True if indexing succeeded
        """
        pass
    
    @abstractmethod
    def search(self, query: str, filters: Dict[str, Any] = None, top_k: int = 10) -> List[Evidence]:
        """Search the corpus and return ranked evidence.
        
        Args:
            query: Search query string
            filters: Optional filters to apply (e.g., document type, date range)
            top_k: Maximum number of results to return
            
        Returns:
            List of Evidence objects ranked by relevance
        """
        pass
    
    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full document by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document data if found, None otherwise
        """
        pass
    
    def is_indexed(self) -> bool:
        """Check if the corpus has been indexed.
        
        Returns:
            bool: True if corpus is indexed and ready for search
        """
        return self.indexed
    
    def get_corpus_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed corpus.
        
        Returns:
            Dictionary with corpus statistics
        """
        return {
            'corpus_id': self.corpus_id,
            'indexed': self.indexed,
            'document_count': self._get_document_count(),
            'chunk_count': self._get_chunk_count(),
            'index_size_mb': self._get_index_size_mb()
        }
    
    @abstractmethod
    def _get_document_count(self) -> int:
        """Get total number of indexed documents."""
        pass
    
    @abstractmethod
    def _get_chunk_count(self) -> int:
        """Get total number of indexed chunks."""
        pass
    
    @abstractmethod
    def _get_index_size_mb(self) -> float:
        """Get approximate index size in megabytes."""
        pass
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks for indexing.
        
        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at word boundary near the target end
            if end < len(text):
                # Look backward for a space or punctuation
                for i in range(min(100, chunk_size // 4)):  # Look back up to 25% of chunk size
                    if end - i <= start:
                        break
                    if text[end - i] in ' \n\t.!?;':
                        end = end - i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start forward, accounting for overlap
            start = max(start + 1, end - overlap)
        
        return chunks
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text for search indexing.
        
        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List of keywords
        """
        import re
        
        # Simple keyword extraction - can be enhanced with NLP libraries
        # Remove markdown formatting and extract meaningful words
        clean_text = re.sub(r'[#*`\[\]()]', '', text.lower())
        words = re.findall(r'\b[a-zA-Z]{3,}\b', clean_text)
        
        # Remove common stop words
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'this', 'that', 'these', 'those', 'a', 'an', 'is', 'are', 'was',
            'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'shall'
        }
        
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        # Count frequency and return most common
        word_counts = {}
        for word in keywords:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:max_keywords]]