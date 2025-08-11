"""Meeting Expert Agent for comprehensive Town Board meeting analysis."""

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from agents.base_agent import BaseAgent
from knowledge.meeting_corpus import MeetingCorpus
from schemas import AgentQuery, AgentResponse, Evidence, Citation

logger = logging.getLogger(__name__)


class MeetingExpertAgent(BaseAgent):
    """Expert agent for Town Board meeting analysis and Q&A.
    
    This agent specializes in understanding meeting structure, agenda items,
    and providing detailed answers about meeting content using the processed
    markdown documents and metadata.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize the Meeting Expert Agent.
        
        Args:
            name: Agent identifier ('meeting_expert')
            config: System configuration
        """
        super().__init__(name, config)
        self.llm_client = self._get_llm_provider()
        
        # Query intent patterns
        self.intent_patterns = {
            'agenda_overview': [
                r"what'?s?\s+on\s+(the\s+)?agenda",
                r"agenda\s+(overview|summary|items)",
                r"what\s+(is\s+)?being\s+discussed",
                r"meeting\s+(agenda|overview|summary)"
            ],
            'specific_item': [
                r"agenda\s+item\s+\d+[a-z]?",
                r"item\s+\d+[a-z]?",
                r"section\s+\d+[a-z]?",
                r"tell\s+me\s+about.*item"
            ],
            'document_search': [
                r"what\s+documents?",
                r"find.*document",
                r"search.*for",
                r"related\s+to.*document"
            ],
            'participant_info': [
                r"who\s+(is\s+|needs?\s+to\s+)?speak",
                r"applicant",
                r"presenter",
                r"who\s+(is\s+)?involved"
            ],
            'procedural': [
                r"when\s+(is\s+|does)",
                r"what\s+time",
                r"deadline",
                r"process\s+for"
            ]
        }
    
    def _init_knowledge_provider(self) -> MeetingCorpus:
        """Initialize meeting corpus knowledge provider.
        
        Returns:
            MeetingCorpus: Configured meeting corpus
        """
        # This will be set when processing queries with meeting_dir
        return None
    
    def _get_supported_query_types(self) -> list[str]:
        """Return supported query types for this agent.
        
        Returns:
            List of supported query types
        """
        return [
            'agenda_overview',
            'specific_item',
            'document_search',
            'participant_info',
            'procedural'
        ]
    
    def query(self, query: AgentQuery) -> AgentResponse:
        """Process a meeting-related query and return comprehensive response.
        
        Args:
            query: User query with meeting context
            
        Returns:
            AgentResponse: Structured response with evidence and citations
        """
        start_time = time.time()
        
        try:
            # Validate query
            if not self._validate_query(query):
                return self._create_error_response("Invalid query provided")
            
            if not query.meeting_dir:
                return self._create_error_response("Meeting directory not specified")
            
            # Initialize meeting corpus for this query
            meeting_corpus = MeetingCorpus(query.meeting_dir, self.config)
            
            # Index meeting if not already done
            if not meeting_corpus.is_indexed():
                logger.info("Indexing meeting corpus for first-time use")
                if not meeting_corpus.index_corpus():
                    return self._create_error_response("Failed to index meeting documents")
            
            # Analyze query intent
            intent = self._analyze_query_intent(query.question)
            query.query_type = intent['type']
            
            # Retrieve relevant evidence
            evidence = self._retrieve_evidence(query, intent, meeting_corpus)
            
            # Generate response using LLM
            response_content = self._generate_response(query, evidence, intent, meeting_corpus)
            
            # Create citations from evidence
            citations = self._create_citations(evidence)
            
            # Calculate confidence based on evidence quality
            confidence = self._calculate_confidence(evidence, intent)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return AgentResponse(
                answer=response_content,
                confidence=confidence,
                evidence=evidence,
                citations=citations,
                reasoning=f"Analyzed {len(evidence)} pieces of evidence for {intent['type']} query",
                query_type=intent['type'],
                processing_time_ms=processing_time,
                metadata={
                    'meeting_dir': query.meeting_dir,
                    'intent': intent,
                    'model_used': self.llm_config.get('model', 'unknown')
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return self._create_error_response(f"Error processing query: {str(e)}")
    
    def _analyze_query_intent(self, question: str) -> Dict[str, Any]:
        """Analyze user query to determine intent and extract entities.
        
        Args:
            question: User's question
            
        Returns:
            Dict with intent analysis results
        """
        question_lower = question.lower()
        intent = {
            'type': 'general',
            'confidence': 0.0,
            'entities': {},
            'search_terms': []
        }
        
        # Check for specific intent patterns
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, question_lower):
                    intent['type'] = intent_type
                    intent['confidence'] = 0.8
                    break
            
            if intent['confidence'] > 0:
                break
        
        # Extract specific entities based on intent
        if intent['type'] == 'specific_item':
            # Extract agenda item number
            item_match = re.search(r'item\s+(\d+[a-z]?)', question_lower)
            if item_match:
                intent['entities']['item_id'] = item_match.group(1).upper()
        
        # Extract search terms for any query
        # Remove common question words and extract meaningful terms
        search_terms = re.findall(r'\b[a-zA-Z]{3,}\b', question)
        stop_words = {'what', 'who', 'when', 'where', 'why', 'how', 'the', 'and', 'for', 'about', 'tell', 'me'}
        intent['search_terms'] = [term for term in search_terms if term.lower() not in stop_words]
        
        return intent
    
    def _retrieve_evidence(self, query: AgentQuery, intent: Dict[str, Any], meeting_corpus: MeetingCorpus) -> List[Evidence]:
        """Retrieve relevant evidence based on query intent.
        
        Args:
            query: User query
            intent: Analyzed intent
            meeting_corpus: Meeting knowledge corpus
            
        Returns:
            List of relevant evidence
        """
        evidence = []
        
        if intent['type'] == 'agenda_overview':
            # For agenda overview, prioritize index document
            overview_evidence = meeting_corpus.search(
                query.question, 
                filters={'document_type': 'index'}, 
                top_k=3
            )
            evidence.extend(overview_evidence)
            
            # Also get some agenda items for comprehensive overview
            agenda_evidence = meeting_corpus.search(
                "agenda items meeting summary",
                filters={'document_type': 'agenda_item'},
                top_k=5
            )
            evidence.extend(agenda_evidence)
            
        elif intent['type'] == 'specific_item':
            # For specific item queries, search for the item
            item_id = intent.get('entities', {}).get('item_id')
            if item_id:
                # Search by item ID first
                item_evidence = meeting_corpus.search(
                    f"item {item_id}",
                    top_k=5
                )
                evidence.extend(item_evidence)
            
            # Also do general search
            general_evidence = meeting_corpus.search(query.question, top_k=5)
            evidence.extend(general_evidence)
            
        else:
            # General search for other query types
            evidence = meeting_corpus.search(query.question, top_k=10)
        
        # Remove duplicates based on chunk_id
        seen_chunks = set()
        unique_evidence = []
        for ev in evidence:
            if ev.chunk_id not in seen_chunks:
                unique_evidence.append(ev)
                seen_chunks.add(ev.chunk_id)
        
        # Sort by relevance score
        unique_evidence.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return unique_evidence[:8]  # Limit to top 8 pieces of evidence
    
    def _generate_response(self, query: AgentQuery, evidence: List[Evidence], intent: Dict[str, Any], meeting_corpus: MeetingCorpus) -> str:
        """Generate response using LLM with evidence grounding.
        
        Args:
            query: User query
            evidence: Retrieved evidence
            intent: Query intent analysis
            meeting_corpus: Meeting corpus for additional context
            
        Returns:
            Generated response text
        """
        if not evidence:
            return self._generate_no_evidence_response(query, intent)
        
        # Build context for LLM
        context_parts = []
        
        # Add meeting context
        meeting_context = meeting_corpus.get_meeting_context()
        if meeting_context:
            context_parts.append(f"Meeting: {Path(meeting_context.meeting_dir).name}")
            context_parts.append(f"Total documents: {meeting_context.total_documents}")
            context_parts.append(f"Total agenda items: {len(meeting_context.agenda_items)}")
        
        # Add evidence
        context_parts.append("\n## Relevant Evidence:\n")
        for i, ev in enumerate(evidence, 1):
            context_parts.append(f"### Evidence {i} (Relevance: {ev.relevance_score:.2f})")
            context_parts.append(f"Source: {ev.file_path}")
            context_parts.append(f"Type: {ev.source_type}")
            context_parts.append(f"Content: {ev.content[:500]}...")
            context_parts.append("")
        
        context = "\n".join(context_parts)
        
        # Create system prompt based on intent
        system_prompt = self._create_system_prompt(intent['type'])
        
        # Create user prompt
        user_prompt = f"""Question: {query.question}

Context Information:
{context}

Please provide a comprehensive answer based on the evidence provided. Include specific details and cite the sources appropriately. Format your response in markdown."""
        
        try:
            # Call LLM
            if self.llm_config.get('llm_provider') == 'openai':
                response = self.llm_client.chat.completions.create(
                    model=self.llm_config.get('model', 'gpt-5'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.llm_config.get('temperature', 0.2),
                    max_tokens=self.llm_config.get('max_tokens', 3000)
                )
                return response.choices[0].message.content
            
            else:
                # Fallback response if LLM not available
                return self._generate_fallback_response(query, evidence, intent)
                
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return self._generate_fallback_response(query, evidence, intent)
    
    def _create_system_prompt(self, intent_type: str) -> str:
        """Create system prompt based on query intent.
        
        Args:
            intent_type: Type of query intent
            
        Returns:
            System prompt for LLM
        """
        base_prompt = """You are a Meeting Expert AI assistant specializing in Town Board meetings. You help users understand meeting agendas, agenda items, and related documents.

Guidelines:
- Provide comprehensive, factual answers based on the evidence provided
- Always cite your sources using the evidence provided
- Use clear, professional language appropriate for municipal government
- Structure your response with headers and bullet points when appropriate
- If asked about specific agenda items, provide detailed information including page numbers and document references
- If evidence is insufficient, clearly state the limitations"""
        
        if intent_type == 'agenda_overview':
            return base_prompt + "\n\nFor agenda overview questions, provide a comprehensive summary of all meeting items, organized by section when possible."
        
        elif intent_type == 'specific_item':
            return base_prompt + "\n\nFor specific agenda item questions, provide detailed information about that item including its purpose, requirements, and any relevant background information."
        
        else:
            return base_prompt + "\n\nProvide relevant information based on the available meeting documents."
    
    def _generate_no_evidence_response(self, query: AgentQuery, intent: Dict[str, Any]) -> str:
        """Generate response when no evidence is found.
        
        Args:
            query: User query
            intent: Query intent
            
        Returns:
            Response indicating no information found
        """
        return f"""I couldn't find specific information to answer "{query.question}" in the available meeting documents.

This could mean:
- The information might be in documents that haven't been processed yet
- The question might refer to a different meeting or agenda item
- The information might be discussed verbally during the meeting rather than in written materials

Please try rephrasing your question or asking about specific agenda items or documents that are available."""
    
    def _generate_fallback_response(self, query: AgentQuery, evidence: List[Evidence], intent: Dict[str, Any]) -> str:
        """Generate fallback response when LLM is not available.
        
        Args:
            query: User query
            evidence: Available evidence
            intent: Query intent
            
        Returns:
            Fallback response based on evidence
        """
        if not evidence:
            return self._generate_no_evidence_response(query, intent)
        
        response_parts = [f"# Response to: {query.question}\n"]
        
        if intent['type'] == 'agenda_overview':
            response_parts.append("## Meeting Overview\n")
            response_parts.append("Based on the available documents, here are the key agenda items:\n")
        
        response_parts.append("## Relevant Information\n")
        
        for i, ev in enumerate(evidence[:5], 1):  # Limit to top 5 for fallback
            response_parts.append(f"### {i}. From {ev.file_path}\n")
            response_parts.append(f"{ev.content[:300]}...\n")
        
        response_parts.append("\n## Sources\n")
        for i, ev in enumerate(evidence[:5], 1):
            response_parts.append(f"{i}. **{ev.file_path}** (Type: {ev.source_type})")
        
        return "\n".join(response_parts)
    
    def _create_citations(self, evidence: List[Evidence]) -> List[Citation]:
        """Create structured citations from evidence.
        
        Args:
            evidence: Evidence to cite
            
        Returns:
            List of Citation objects
        """
        citations = []
        
        for ev in evidence:
            citation = Citation(
                source="meeting",
                file_path=ev.file_path,
                text=ev.content[:200] + "..." if len(ev.content) > 200 else ev.content,
                chunk_id=ev.chunk_id,
                confidence=ev.relevance_score,
                anchor=ev.anchor,
                start_char=ev.start_char,
                end_char=ev.end_char
            )
            citations.append(citation)
        
        return citations
    
    def _calculate_confidence(self, evidence: List[Evidence], intent: Dict[str, Any]) -> float:
        """Calculate confidence score for the response.
        
        Args:
            evidence: Retrieved evidence
            intent: Query intent analysis
            
        Returns:
            Confidence score between 0 and 1
        """
        if not evidence:
            return 0.0
        
        # Base confidence on evidence quality
        avg_relevance = sum(ev.relevance_score for ev in evidence) / len(evidence)
        
        # Boost confidence for specific intents with good evidence
        if intent['type'] in ['agenda_overview', 'specific_item'] and avg_relevance > 2.0:
            confidence = min(0.9, avg_relevance / 5.0)
        else:
            confidence = min(0.8, avg_relevance / 4.0)
        
        # Reduce confidence if evidence is limited
        if len(evidence) < 3:
            confidence *= 0.8
        
        return round(confidence, 2)
    
    def _create_error_response(self, error_message: str) -> AgentResponse:
        """Create error response.
        
        Args:
            error_message: Error description
            
        Returns:
            AgentResponse with error information
        """
        return AgentResponse(
            answer=f"Error: {error_message}",
            confidence=0.0,
            evidence=[],
            citations=[],
            reasoning=f"Error occurred: {error_message}",
            metadata={'error': True}
        )