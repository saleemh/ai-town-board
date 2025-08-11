"""Knowledge provider framework for AI agents."""

from .base_knowledge_provider import KnowledgeProvider
from .meeting_corpus import MeetingCorpus

__all__ = [
    'KnowledgeProvider',
    'MeetingCorpus'
]