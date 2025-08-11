"""Base agent interface for the AI Town Board system."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from schemas import AgentQuery, AgentResponse
from knowledge.base_knowledge_provider import KnowledgeProvider

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all AI agents in the system.
    
    Provides common functionality and enforces interface contracts for
    specialized agents like MeetingExpertAgent and TownAttorneyAgent.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize the agent with configuration.
        
        Args:
            name: Agent identifier (e.g., 'meeting_expert', 'town_attorney')
            config: Agent-specific configuration from config.yaml
        """
        self.name = name
        self.config = config
        self.llm_config = config.get('agents', {}).get(name, {})
        
        # Initialize knowledge provider for this agent
        self.knowledge_provider = self._init_knowledge_provider()
        
        logger.info(f"Initialized {self.name} agent with config: {self.llm_config.keys()}")
    
    @abstractmethod
    def query(self, query: AgentQuery) -> AgentResponse:
        """Process a user query and return structured response.
        
        This is the main entry point for agent interaction. Each agent
        implements its own query processing logic while using the common
        knowledge provider framework.
        
        Args:
            query: Structured user query with context and constraints
            
        Returns:
            AgentResponse: Complete response with evidence and citations
        """
        pass
    
    @abstractmethod
    def _init_knowledge_provider(self) -> KnowledgeProvider:
        """Initialize agent-specific knowledge provider.
        
        Each agent may use different knowledge sources (meeting docs, 
        town code, etc.) and retrieval strategies.
        
        Returns:
            KnowledgeProvider: Configured provider for this agent
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return agent capabilities and supported query types.
        
        Returns:
            Dict describing what this agent can do
        """
        return {
            'name': self.name,
            'enabled': self.llm_config.get('enabled', False),
            'model': self.llm_config.get('model', 'unknown'),
            'knowledge_sources': self.llm_config.get('knowledge_sources', []),
            'supported_queries': self._get_supported_query_types()
        }
    
    @abstractmethod
    def _get_supported_query_types(self) -> list[str]:
        """Return list of query types this agent supports.
        
        Returns:
            List of query type strings (e.g., ['agenda_overview', 'specific_item'])
        """
        pass
    
    def _validate_query(self, query: AgentQuery) -> bool:
        """Validate that the query is appropriate for this agent.
        
        Args:
            query: The query to validate
            
        Returns:
            bool: True if query is valid for this agent
        """
        if not query.question or not query.question.strip():
            return False
            
        # Agent-specific validation can be implemented in subclasses
        return True
    
    def _get_llm_provider(self):
        """Get configured LLM provider for this agent.
        
        Returns:
            Configured LLM provider instance
        """
        provider = self.llm_config.get('llm_provider', 'openai')
        model = self.llm_config.get('model', 'gpt-5')
        
        if provider == 'fallback':
            return None  # Use fallback responses
        elif provider == 'openai':
            return self._init_openai_provider(model)
        elif provider == 'anthropic':
            return self._init_anthropic_provider(model)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def _init_openai_provider(self, model: str):
        """Initialize OpenAI provider with configurable parameters.
        
        Args:
            model: Model name (e.g., 'gpt-5')
        """
        try:
            import openai
            import os
            
            # Get API key from environment
            api_key_env = self.llm_config.get('api_key_env', 'OPENAI_API_KEY')
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ValueError(f"Missing API key environment variable: {api_key_env}")
            
            # Build client parameters from config
            client_params = {'api_key': api_key}
            
            # Add optional parameters from config
            if 'base_url' in self.llm_config and self.llm_config['base_url']:
                client_params['base_url'] = self.llm_config['base_url']
                logger.debug(f"Using custom base_url: {self.llm_config['base_url']}")
            
            if 'organization' in self.llm_config and self.llm_config['organization']:
                client_params['organization'] = self.llm_config['organization']
                
            if 'timeout' in self.llm_config and self.llm_config['timeout']:
                client_params['timeout'] = self.llm_config['timeout']
            
            client = openai.OpenAI(**client_params)
            logger.debug(f"Initialized OpenAI client for model: {model}")
            return client
            
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    def _init_anthropic_provider(self, model: str):
        """Initialize Anthropic provider.
        
        Args:
            model: Model name (e.g., 'claude-3-sonnet-20240229')
        """
        try:
            import anthropic
            
            # Get API key from environment
            import os
            api_key = os.getenv(self.llm_config.get('api_key_env', 'ANTHROPIC_API_KEY'))
            if not api_key:
                raise ValueError(f"Missing API key environment variable: {self.llm_config.get('api_key_env', 'ANTHROPIC_API_KEY')}")
            
            client = anthropic.Anthropic(api_key=api_key)
            return client
            
        except ImportError:
            raise ImportError("Anthropic package not installed. Run: pip install anthropic")
    
    def _format_response_as_markdown(self, content: str, citations: list) -> str:
        """Format agent response as markdown with citations.
        
        Args:
            content: Main response content
            citations: List of citations to append
            
        Returns:
            Formatted markdown string
        """
        formatted = content
        
        if citations:
            formatted += "\n\n## Sources\n\n"
            for i, citation in enumerate(citations, 1):
                file_name = Path(citation.file_path).name if citation.file_path else "Unknown"
                anchor = f" ({citation.anchor})" if citation.anchor else ""
                formatted += f"{i}. **{file_name}**{anchor}\n"
                
                if citation.text and len(citation.text) > 100:
                    formatted += f"   > {citation.text[:100]}...\n\n"
                elif citation.text:
                    formatted += f"   > {citation.text}\n\n"
        
        return formatted