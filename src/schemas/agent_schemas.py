"""Core data schemas for the AI agent framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


@dataclass
class AgentQuery:
    """User query to an agent with context and constraints."""
    question: str
    context: Optional[Dict[str, Any]] = None
    meeting_dir: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    query_type: Optional[str] = None  # "agenda_overview", "specific_item", etc.


@dataclass
class Evidence:
    """Piece of evidence supporting an answer with scoring."""
    chunk_id: str
    file_path: str
    content: str
    relevance_score: float
    source_type: str  # "agenda", "packet", "attachment", "index"
    metadata: Dict[str, Any] = field(default_factory=dict)
    anchor: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None


@dataclass
class Citation:
    """Structured citation referencing evidence."""
    source: str  # "meeting", "town_code"
    file_path: str
    text: str
    anchor: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    chunk_id: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class AgentResponse:
    """Structured response from an agent with evidence and citations."""
    answer: str
    confidence: float
    evidence: List[Evidence]
    citations: List[Citation]
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    query_type: Optional[str] = None
    processing_time_ms: Optional[int] = None


@dataclass
class AgendaItem:
    """Normalized agenda item with all associated metadata."""
    id: str
    section: str  # "PUBLIC HEARINGS", "NEW BUSINESS", etc.
    item_number: str  # "5B", "7A", etc.
    title: str
    description: Optional[str] = None
    markdown_file: Optional[str] = None  # path to segment markdown
    pdf_segment: Optional[str] = None   # path to PDF fragment
    page_range: Optional[str] = None    # "22-27"
    page_count: Optional[int] = None
    attachments: List[str] = field(default_factory=list)  # related document paths
    metadata: Dict[str, Any] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    action_required: bool = False


@dataclass
class MeetingContext:
    """Complete context for a meeting directory with all processed data."""
    meeting_dir: str
    metadata: Dict[str, Any]  # from metadata.json
    documents: List[Dict[str, Any]]  # processed document info
    agenda_items: List[AgendaItem]  # extracted agenda items
    index_data: Optional[Dict[str, Any]] = None  # from index.md processing
    processing_date: Optional[datetime] = None
    total_documents: int = 0
    total_pages: int = 0


@dataclass
class DocumentChunk:
    """A searchable chunk of a document with embeddings."""
    chunk_id: str
    file_path: str
    content: str
    start_char: int
    end_char: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    keywords: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result from knowledge provider search."""
    chunks: List[DocumentChunk]
    total_results: int
    search_time_ms: int
    query_embedding: Optional[List[float]] = None
    reranked: bool = False


# Analysis-specific schemas

@dataclass
class AnalysisSection:
    """A structured section of meeting analysis."""
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ItemAnalysis:
    """Complete analysis of a single agenda item."""
    item_id: str
    item_title: str
    source_file: str
    executive_summary: str  # <250 words, must stand alone
    topics_included: str    # Summary of topics in order, essential points
    decisions: str          # Explicit asks, decisions, votes, arguments
    other_takeaways: str    # Key takeaways not covered above
    processing_date: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MeetingAnalysis:
    """Complete analysis of an entire meeting."""
    meeting_date: str
    meeting_dir: str
    executive_summary: str
    total_items: int
    item_analyses: List[ItemAnalysis]
    topics_included: str
    decisions: str
    other_takeaways: str
    processing_date: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisQuery:
    """Query for meeting analysis operations."""
    meeting_dir: str
    output_format: str = "both"  # "markdown", "json", "both"
    force_rebuild: bool = False
    items_only: bool = False
    analysis_depth: str = "comprehensive"  # "summary", "detailed", "comprehensive"