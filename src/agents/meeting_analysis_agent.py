"""Meeting Analysis Agent for automated comprehensive meeting analysis."""

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
from schemas import (
    AnalysisQuery, ItemAnalysis, MeetingAnalysis, 
    AnalysisSection, AgentQuery, AgentResponse
)

logger = logging.getLogger(__name__)


class MeetingAnalysisAgent(BaseAgent):
    """Agent for comprehensive automated meeting analysis.
    
    This agent processes all agenda items in a meeting and generates
    structured analysis with executive summaries, topic breakdowns,
    decisions, and key takeaways following a consistent format.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize the Meeting Analysis Agent.
        
        Args:
            name: Agent identifier ('meeting_analysis')
            config: System configuration
        """
        super().__init__(name, config)
        self.llm_client = self._get_llm_provider()
        
        # Analysis templates
        self.analysis_template = self._create_analysis_template()
    
    def _init_knowledge_provider(self) -> MeetingCorpus:
        """Initialize meeting corpus knowledge provider."""
        return None  # Will be set per query
    
    def _get_supported_query_types(self) -> List[str]:
        """Return supported query types for this agent."""
        return ['meeting_analysis', 'item_analysis', 'batch_analysis']
    
    def query(self, query: AgentQuery) -> AgentResponse:
        """Process a query (not used for analysis agent, use analyze_meeting instead).
        
        Args:
            query: Agent query (not used for this agent)
            
        Returns:
            AgentResponse: Basic response indicating to use analyze_meeting method
        """
        return AgentResponse(
            answer="Meeting Analysis Agent uses analyze_meeting() method instead of query().",
            confidence=1.0,
            evidence=[],
            citations=[],
            reasoning="This agent is designed for batch analysis, not individual queries.",
            metadata={'agent_type': 'analysis', 'use_method': 'analyze_meeting'}
        )
    
    def analyze_meeting(self, query: AnalysisQuery) -> MeetingAnalysis:
        """Analyze an entire meeting and generate comprehensive analysis.
        
        Args:
            query: Analysis query with meeting directory and options
            
        Returns:
            MeetingAnalysis: Complete structured analysis of the meeting
        """
        start_time = time.time()
        
        try:
            meeting_path = Path(query.meeting_dir)
            if not meeting_path.exists():
                raise ValueError(f"Meeting directory not found: {query.meeting_dir}")
            
            # Initialize meeting corpus
            meeting_corpus = MeetingCorpus(query.meeting_dir, self.config)
            if not meeting_corpus.is_indexed():
                logger.info("Indexing meeting corpus for analysis")
                if not meeting_corpus.index_corpus():
                    raise RuntimeError("Failed to index meeting documents")
            
            # Get meeting context
            meeting_context = meeting_corpus.get_meeting_context()
            if not meeting_context:
                raise RuntimeError("Could not load meeting context")
            
            # Get agenda items
            agenda_items = meeting_corpus.get_agenda_items()
            logger.info(f"Found {len(agenda_items)} agenda items to analyze")
            
            # Analyze each agenda item
            item_analyses = []
            for agenda_item in agenda_items:
                try:
                    item_analysis = self._analyze_agenda_item(agenda_item, meeting_corpus)
                    if item_analysis:
                        item_analyses.append(item_analysis)
                        logger.info(f"Analyzed item {agenda_item.item_number}: {agenda_item.title[:50]}...")
                except Exception as e:
                    logger.error(f"Failed to analyze item {agenda_item.item_number}: {e}")
                    continue
            
            # Generate overall meeting analysis
            meeting_analysis = self._generate_meeting_analysis(
                meeting_context, item_analyses, query
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(f"Meeting analysis completed in {processing_time}ms")
            
            return meeting_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing meeting: {e}")
            raise
    
    def _analyze_agenda_item(self, agenda_item, meeting_corpus: MeetingCorpus) -> Optional[ItemAnalysis]:
        """Analyze a single agenda item.
        
        Args:
            agenda_item: AgendaItem to analyze
            meeting_corpus: Meeting corpus for document access
            
        Returns:
            ItemAnalysis: Structured analysis of the agenda item
        """
        try:
            # Get document content
            doc_data = meeting_corpus.get_document(agenda_item.markdown_file)
            if not doc_data:
                logger.warning(f"No document found for item {agenda_item.item_number}")
                return None
            
            content = doc_data['content']
            if not content.strip():
                logger.warning(f"Empty content for item {agenda_item.item_number}")
                return None
            
            # Generate structured analysis using LLM
            analysis_sections = self._generate_item_analysis(agenda_item, content)
            
            # Create ItemAnalysis object
            item_analysis = ItemAnalysis(
                item_id=agenda_item.item_number,
                item_title=agenda_item.title,
                source_file=agenda_item.markdown_file,
                executive_summary=analysis_sections['executive_summary'],
                topics_included=analysis_sections['topics_included'],
                decisions=analysis_sections['decisions'],
                other_takeaways=analysis_sections['other_takeaways'],
                metadata={
                    'page_range': agenda_item.page_range,
                    'page_count': agenda_item.page_count,
                    'section': agenda_item.section,
                    'keywords': agenda_item.keywords
                }
            )
            
            return item_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing agenda item {agenda_item.item_number}: {e}")
            return None
    
    def _generate_item_analysis(self, agenda_item, content: str) -> Dict[str, str]:
        """Generate structured analysis for a single agenda item.
        
        Args:
            agenda_item: AgendaItem to analyze
            content: Full markdown content of the item
            
        Returns:
            Dict with the four analysis sections
        """
        # Create analysis prompt
        system_prompt = self._create_item_analysis_prompt()
        
        user_prompt = f"""Please analyze the following Town Board agenda item and provide a structured analysis.

**Agenda Item**: {agenda_item.item_number} - {agenda_item.title}

**Content to Analyze**:
{content}

Please provide your analysis in the exact format specified in the system prompt, with each section clearly separated."""

        try:
            # Use LLM if available, otherwise fallback
            if self.llm_client and self.llm_config.get('llm_provider') != 'fallback':
                # Get all parameters from config with sensible defaults
                model = self.llm_config.get('model', 'gpt-4')
                temperature = self.llm_config.get('temperature', 0.1)
                max_tokens = self.llm_config.get('max_tokens', 2000)
                
                logger.debug(f"Making LLM request with model={model}, temp={temperature}, max_tokens={max_tokens}")
                
                response = self.llm_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                analysis_text = response.choices[0].message.content
            else:
                # Fallback analysis - returns dict directly
                return self._generate_fallback_analysis(agenda_item, content)
            
            # Parse the structured response
            return self._parse_analysis_response(analysis_text)
            
        except Exception as e:
            logger.error(f"Error generating analysis for item {agenda_item.item_number}: {e}")
            return self._generate_fallback_analysis(agenda_item, content)
    
    def _create_item_analysis_prompt(self) -> str:
        """Create system prompt for agenda item analysis from external file."""
        try:
            # Get prompt file path from config
            prompt_file = self.llm_config.get('prompt_file', 'prompts/agents/meeting_analysis.md')
            
            # Convert to absolute path
            if not Path(prompt_file).is_absolute():
                prompt_file = Path.cwd() / prompt_file
            else:
                prompt_file = Path(prompt_file)
            
            # Load prompt from file
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_content = f.read()
                logger.debug(f"Loaded analysis prompt from {prompt_file}")
                return prompt_content
            else:
                logger.warning(f"Prompt file not found: {prompt_file}, using fallback prompt")
                return self._get_fallback_prompt()
                
        except Exception as e:
            logger.error(f"Error loading prompt file: {e}, using fallback prompt")
            return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if external file cannot be loaded."""
        return """You are a Town Board meeting analysis expert. Your task is to analyze agenda items and provide structured analysis in exactly four sections.

For each agenda item, provide analysis in this EXACT format:

## Executive Summary
[Provide a summary under 250 words that must be able to stand alone. Someone should be able to read only this section and understand the essential purpose, context, and significance of this agenda item.]

## Topics Included
[Provide a summary of the topics included in the document, preserving their order. Condense into essential points. Include any observations about what is included in the content.]

## Decisions
[Record any explicit asks, decisions, votes, or formal actions. If arguments are stated for or against any position, state that. Include any resolutions, requirements, or pending decisions.]

## Other Takeaways
[Catalog all key takeaways that were not already included above. This includes stakeholder information, deadlines, financial impacts, legal references, procedural notes, background context, and any other significant information.]

Guidelines:
- Each section must be present and clearly labeled
- Be comprehensive but concise
- Focus on factual information from the documents
- Preserve important details while summarizing effectively
- Use bullet points within sections when appropriate for clarity"""
    
    def _parse_analysis_response(self, analysis_text: str) -> Dict[str, str]:
        """Parse structured analysis response into sections.
        
        Args:
            analysis_text: Raw analysis text from LLM
            
        Returns:
            Dict with the four required sections
        """
        sections = {
            'executive_summary': '',
            'topics_included': '',
            'decisions': '',
            'other_takeaways': ''
        }
        
        try:
            # Split by markdown headers
            parts = re.split(r'##\s+', analysis_text)
            
            for part in parts[1:]:  # Skip first empty part
                if part.strip():
                    lines = part.strip().split('\n', 1)
                    if len(lines) >= 2:
                        section_title = lines[0].strip().lower()
                        section_content = lines[1].strip()
                        
                        if 'executive summary' in section_title:
                            sections['executive_summary'] = section_content
                        elif 'topics included' in section_title:
                            sections['topics_included'] = section_content
                        elif 'decisions' in section_title:
                            sections['decisions'] = section_content
                        elif 'other takeaways' in section_title or 'takeaways' in section_title:
                            sections['other_takeaways'] = section_content
            
            # Ensure all sections have content
            for key, value in sections.items():
                if not value.strip():
                    sections[key] = "No specific information available in this section."
            
            return sections
            
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return self._create_fallback_sections()
    
    def _generate_fallback_analysis(self, agenda_item, content: str) -> Dict[str, str]:
        """Generate basic fallback analysis when LLM is not available."""
        # Extract first few paragraphs for summary
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and not p.startswith('#')]
        clean_paragraphs = []
        
        for para in paragraphs:
            # Skip metadata and headers
            if any(skip in para.lower() for skip in ['document type', 'source file', 'page range', 'processing']):
                continue
            if para.startswith('- **') or para.startswith('**'):
                continue
            clean_paragraphs.append(para)
        
        summary_text = ' '.join(clean_paragraphs[:3])[:240] + "..." if clean_paragraphs else "No content available."
        
        return {
            'executive_summary': f"Agenda item {agenda_item.item_number}: {agenda_item.title}. {summary_text}",
            'topics_included': f"This agenda item covers: {agenda_item.title}. " + (clean_paragraphs[0][:200] + "..." if clean_paragraphs else "No detailed topics available."),
            'decisions': "No specific decisions or votes identified in fallback analysis mode.",
            'other_takeaways': f"Item appears on pages {agenda_item.page_range or 'unknown'}. Additional analysis requires LLM processing."
        }
    
    def _create_fallback_sections(self) -> Dict[str, str]:
        """Create minimal fallback sections when parsing fails."""
        return {
            'executive_summary': "Analysis parsing failed - executive summary not available.",
            'topics_included': "Analysis parsing failed - topics summary not available.", 
            'decisions': "Analysis parsing failed - decisions summary not available.",
            'other_takeaways': "Analysis parsing failed - additional takeaways not available."
        }
    
    def _generate_meeting_analysis(self, meeting_context, item_analyses: List[ItemAnalysis], query: AnalysisQuery) -> MeetingAnalysis:
        """Generate overall meeting analysis from individual item analyses.
        
        Args:
            meeting_context: Meeting context information
            item_analyses: List of individual item analyses
            query: Original analysis query
            
        Returns:
            MeetingAnalysis: Complete meeting analysis
        """
        # Aggregate information from all items
        all_summaries = [item.executive_summary for item in item_analyses]
        all_topics = [item.topics_included for item in item_analyses] 
        all_decisions = [item.decisions for item in item_analyses if item.decisions and "no specific" not in item.decisions.lower()]
        all_takeaways = [item.other_takeaways for item in item_analyses]
        
        # Create comprehensive meeting summary
        executive_summary = self._create_meeting_executive_summary(meeting_context, item_analyses)
        topics_included = self._aggregate_topics(all_topics)
        decisions = self._aggregate_decisions(all_decisions) if all_decisions else "No specific decisions identified across agenda items."
        other_takeaways = self._aggregate_takeaways(all_takeaways)
        
        return MeetingAnalysis(
            meeting_date=Path(query.meeting_dir).name,
            meeting_dir=query.meeting_dir,
            executive_summary=executive_summary,
            total_items=len(item_analyses),
            item_analyses=item_analyses,
            topics_included=topics_included,
            decisions=decisions,
            other_takeaways=other_takeaways,
            metadata={
                'processing_mode': query.analysis_depth,
                'output_format': query.output_format,
                'total_documents': meeting_context.total_documents if meeting_context else 0,
                'total_pages': meeting_context.total_pages if meeting_context else 0
            }
        )
    
    def _create_meeting_executive_summary(self, meeting_context, item_analyses: List[ItemAnalysis]) -> str:
        """Create executive summary for the entire meeting."""
        meeting_date = Path(meeting_context.meeting_dir).name if meeting_context else "Unknown"
        total_items = len(item_analyses)
        
        # Categorize items by type
        item_types = {}
        for item in item_analyses:
            item_type = self._categorize_item(item.item_title)
            item_types[item_type] = item_types.get(item_type, 0) + 1
        
        summary_parts = [
            f"Town Board Meeting {meeting_date} included {total_items} agenda items covering various municipal matters."
        ]
        
        if item_types:
            type_summary = ", ".join([f"{count} {item_type}" for item_type, count in item_types.items()])
            summary_parts.append(f"Items included: {type_summary}.")
        
        # Add key themes
        if total_items > 0:
            summary_parts.append("Key areas of focus included municipal operations, regulatory compliance, and administrative approvals.")
        
        return " ".join(summary_parts)
    
    def _categorize_item(self, title: str) -> str:
        """Categorize an agenda item by its title."""
        title_lower = title.lower()
        
        if 'approval' in title_lower or 'consider approval' in title_lower:
            return 'approvals'
        elif 'receipt' in title_lower:
            return 'receipts/reports'
        elif 'minutes' in title_lower:
            return 'minutes'
        elif 'local law' in title_lower or 'ordinance' in title_lower:
            return 'legislation'
        elif 'permit' in title_lower or 'application' in title_lower:
            return 'permits/applications'
        elif 'authorization' in title_lower:
            return 'authorizations'
        else:
            return 'other business'
    
    def _aggregate_topics(self, all_topics: List[str]) -> str:
        """Aggregate topics from all agenda items."""
        if not all_topics:
            return "No topics summary available."
        
        # Extract key themes
        unique_topics = set()
        for topic_section in all_topics:
            # Simple extraction - can be enhanced
            if topic_section and "not available" not in topic_section.lower():
                unique_topics.add(topic_section[:100] + "..." if len(topic_section) > 100 else topic_section)
        
        if unique_topics:
            return "Meeting covered: " + "; ".join(list(unique_topics)[:5])
        return "Topic aggregation not available in current processing mode."
    
    def _aggregate_decisions(self, all_decisions: List[str]) -> str:
        """Aggregate decisions from all agenda items."""
        if not all_decisions:
            return "No specific decisions identified."
        
        decision_summary = []
        for decisions in all_decisions:
            if decisions and len(decisions) > 20:  # Has substantial content
                decision_summary.append(decisions[:150] + "...")
        
        if decision_summary:
            return "Key decisions across items: " + " | ".join(decision_summary[:3])
        return "Decision details available in individual item analyses."
    
    def _aggregate_takeaways(self, all_takeaways: List[str]) -> str:
        """Aggregate other takeaways from all agenda items."""
        if not all_takeaways:
            return "No additional takeaways available."
        
        # Extract common themes
        takeaway_themes = []
        for takeaway in all_takeaways:
            if takeaway and len(takeaway) > 30 and "not available" not in takeaway.lower():
                takeaway_themes.append(takeaway[:100] + "..." if len(takeaway) > 100 else takeaway)
        
        if takeaway_themes:
            return "Additional insights: " + " | ".join(takeaway_themes[:4])
        return "Additional takeaway details available in individual item analyses."
    
    def _create_analysis_template(self) -> str:
        """Create the analysis output template."""
        return """# Meeting Analysis: {meeting_date}

## Executive Summary
{executive_summary}

## Topics Included
{topics_included}

## Decisions
{decisions}

## Other Takeaways
{other_takeaways}

---

## Individual Item Analyses

{item_analyses}
"""