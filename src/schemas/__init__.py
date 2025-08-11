"""Schema definitions for the AI Town Board agent system."""

from .agent_schemas import (
    AgentQuery,
    AgentResponse,
    Evidence,
    Citation,
    MeetingContext,
    AgendaItem,
    DocumentChunk,
    SearchResult,
    AnalysisSection,
    ItemAnalysis,
    MeetingAnalysis,
    AnalysisQuery
)

__all__ = [
    'AgentQuery',
    'AgentResponse', 
    'Evidence',
    'Citation',
    'MeetingContext',
    'AgendaItem',
    'DocumentChunk',
    'SearchResult',
    'AnalysisSection',
    'ItemAnalysis',
    'MeetingAnalysis',
    'AnalysisQuery'
]