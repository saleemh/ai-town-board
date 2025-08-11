# AI Town Board Prep System - Technical Specification

## Project Overview

The AI Town Board Prep System is a focused solution for intelligent processing and analysis of town board meeting documents. The system processes user-provided PDFs using advanced AI to generate insights and analysis from specialized AI agents.

### Key Objectives
1. **Document Processing**: Convert user-provided PDFs to searchable markdown using IBM Docling
2. **AI Analysis**: Deploy specialized AI agents to analyze meeting content with domain expertise
3. **Extensible Architecture**: Support addition of new agent types with minimal code changes
4. **Data Organization**: Maintain well-structured data storage for historical reference and analysis
5. **Intelligent Q&A**: Enable natural language queries about meeting content and town code

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Engine                             │
├─────────────────────────────────────────────────────────────────┤
│  Universal PDF Processor │         Agent Framework              │
│                          │                                      │
│  • IBM Docling           │  • Meeting Expert Agent             │
│  • Smart Segmentation    │  • Town Attorney Agent              │
│  • TOC-Driven Splitting  │  • Plugin System                     │
│  • Cross-Reference Gen   │  • Analysis Generation               │
├─────────────────────────────────────────────────────────────────┤
│                    Knowledge Layer                              │
│  • Meeting Data RAG   │  • Town Code RAG      │  • Agent Mgmt  │
│  • Vector Search      │  • Citation System    │  • Orchestration│
└─────────────────────────────────────────────────────────────────┘
```

### Knowledge Provider Architecture

The system uses a pluggable knowledge architecture that supports multiple corpora and retrieval strategies:

```
KnowledgeProvider (Interface)
├── MeetingCorpus
│   ├── Source: <MEETING_DIR>/markdown/
│   ├── Index: <MEETING_DIR>/.index/
│   └── Strategy: Document-level + semantic search
└── TownCodeCorpus  
    ├── Source: <TOWN_CODE_DIR>/markdown/
    ├── Index: <TOWN_CODE_INDEX_DIR>/
    └── Strategy: Chapter-based + hybrid search
```

## Core Agent Framework

### Agent Interface Specification

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class AgentQuery:
    """User query to an agent"""
    question: str
    context: Optional[Dict[str, Any]] = None
    meeting_dir: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None

@dataclass 
class Evidence:
    """Piece of evidence supporting an answer"""
    chunk_id: str
    file_path: str
    anchor: Optional[str]
    content: str
    relevance_score: float
    source_type: str  # "agenda", "packet", "attachment", "town_code"
    metadata: Dict[str, Any]

@dataclass
class Citation:
    """Structured citation referencing evidence"""
    source: str  # "meeting", "town_code"
    file_path: str
    anchor: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    text: str = ""
    chunk_id: Optional[str] = None

@dataclass
class AgentResponse:
    """Structured response from an agent"""
    answer: str
    confidence: float
    evidence: List[Evidence]
    citations: List[Citation]
    reasoning: str
    metadata: Dict[str, Any]

class BaseAgent(ABC):
    """Base interface for all agents"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.knowledge_provider = self._init_knowledge_provider()
    
    @abstractmethod
    def query(self, query: AgentQuery) -> AgentResponse:
        """Process a user query and return structured response"""
        pass
    
    @abstractmethod
    def _init_knowledge_provider(self) -> 'KnowledgeProvider':
        """Initialize agent-specific knowledge provider"""
        pass
```

### Knowledge Provider Interface

```python
class KnowledgeProvider(ABC):
    """Abstract interface for knowledge retrieval"""
    
    @abstractmethod
    def index_corpus(self, corpus_id: str, source_paths: List[str], config: Dict[str, Any]) -> bool:
        """Index a corpus for retrieval"""
        pass
    
    @abstractmethod
    def search(self, corpus_id: str, query: str, filters: Dict[str, Any], top_k: int) -> List[Evidence]:
        """Search corpus and return ranked evidence"""
        pass
    
    @abstractmethod
    def get_document(self, corpus_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full document by ID"""
        pass
```

## Town Board Meeting Expert Agent

### Agent Overview

The Town Board Meeting Expert is a specialized agent that provides comprehensive Q&A capabilities for meeting documents. It understands meeting structure, agenda items, and can provide detailed answers about meeting content.

### Core Capabilities

1. **Meeting Structure Understanding**
   - Identify agenda documents vs supporting materials
   - Parse agenda item hierarchy and numbering
   - Understand meeting flow and document relationships

2. **Natural Language Queries**
   - "What's on the agenda for this meeting?"
   - "Tell me about agenda item 5B"
   - "What documents are related to the Mianus River request?"
   - "Who needs to speak at this meeting about permits?"

3. **Context-Aware Responses**
   - Provide relevant excerpts from agenda, packets, and attachments
   - Reference page numbers and PDF segments for traceability
   - Identify speakers, deadlines, and action items

### Implementation Workflow

```
User Query → Query Analysis → Document Retrieval → Content Synthesis → Response Generation
     ↓              ↓               ↓                    ↓                  ↓
"What's on     Parse intent    Find agenda.md      Extract items      Format with
 agenda?"      + entities      + index.md         + descriptions      citations
```

#### Detailed Agent Workflow

```python
class MeetingExpertAgent(BaseAgent):
    """Expert agent for Town Board meeting analysis"""
    
    def query(self, query: AgentQuery) -> AgentResponse:
        """Process meeting-related query"""
        
        # 1. Load meeting context
        meeting_context = self._load_meeting_context(query.meeting_dir)
        
        # 2. Analyze query intent
        intent = self._analyze_query_intent(query.question)
        
        # 3. Retrieve relevant documents
        evidence = self._retrieve_evidence(query, intent, meeting_context)
        
        # 4. Generate grounded response
        response = self._generate_response(query, evidence, intent)
        
        return response
    
    def _analyze_query_intent(self, question: str) -> Dict[str, Any]:
        """Classify query type and extract entities"""
        intents = {
            'agenda_overview': ['agenda', 'what\'s on', 'overview'],
            'specific_item': ['item', 'agenda item', 'section'],
            'document_search': ['document', 'attachment', 'file'],
            'participant_info': ['who', 'speaker', 'applicant'],
            'procedural': ['when', 'time', 'deadline', 'process']
        }
        
        # Use LLM to classify intent and extract entities
        # Return structured intent analysis
    
    def _retrieve_evidence(self, query: AgentQuery, intent: Dict, context: Dict) -> List[Evidence]:
        """Retrieve relevant meeting documents"""
        
        evidence = []
        
        if intent['type'] == 'agenda_overview':
            # Find primary agenda document
            agenda_doc = self._find_agenda_document(context)
            evidence.append(self._extract_agenda_items(agenda_doc))
            
        elif intent['type'] == 'specific_item':
            # Find specific agenda item by number/title
            item_id = intent.get('item_identifier')
            item_docs = self._find_agenda_item_documents(context, item_id)
            evidence.extend(item_docs)
            
        elif intent['type'] == 'document_search':
            # Search across all meeting documents
            search_terms = intent.get('search_terms', [])
            evidence = self.knowledge_provider.search('meeting', query.question, {}, top_k=10)
        
        return evidence
```

### Meeting Context Structure

The agent works with a structured meeting context loaded from the processed markdown:

```python
@dataclass
class MeetingContext:
    """Complete context for a meeting directory"""
    meeting_dir: str
    metadata: Dict[str, Any]  # from metadata.json
    documents: List[Dict[str, Any]]  # processed document info
    agenda_items: List[AgendaItem]  # extracted agenda items
    index: Dict[str, Any]  # from index.md processing

@dataclass  
class AgendaItem:
    """Normalized agenda item"""
    id: str
    section: str  # "PUBLIC HEARINGS", "NEW BUSINESS", etc.
    item_number: str  # "5B", "7A", etc.
    title: str
    description: Optional[str]
    markdown_file: str  # path to segment markdown
    pdf_segment: str   # path to PDF fragment
    page_range: str    # "22-27"
    attachments: List[str]  # related document paths
    metadata: Dict[str, Any]
```

### Query Examples and Responses

#### Example 1: Agenda Overview
**Query**: "What's on the agenda for this meeting?"

**Processing**:
1. Intent: `agenda_overview`
2. Find agenda document or index
3. Extract agenda item list
4. Format comprehensive response

**Response**:
```markdown
# Meeting Agenda Overview

This meeting has 18 agenda items organized into the following sections:

## Administrator Updates (Items 1)
- **Item 1B**: Administrator Update (Pages 1-3)

## Public Hearings (Items 2-4) 
- **Item 2A**: Request from Mianus River Gorge (Pages 4-11)
- **Item 3A**: Approval of Town Board Minutes: July 23, 2025 (Pages 12-15)
- **Item 4A**: Application from United Hardware (Pages 16-21)

## New Business (Items 5-18)
- **Item 5B**: Local Law to amend Town Code (Pages 22-27)
- **Item 6C**: Letter from Board of Fire Commissioners (Page 28)
[... continues for all items ...]

**Source**: [Meeting Index](index.md) | **PDF Segments**: Available for each item
```

#### Example 2: Specific Item Query
**Query**: "Tell me about agenda item 5B"

**Processing**:
1. Intent: `specific_item`, entity: "5B"
2. Find matching agenda item in metadata
3. Load corresponding markdown and PDF segment
4. Extract relevant content and context

**Response**:
```markdown
# Agenda Item 5B: Local Law Amendment

## Summary
This item concerns considering receipt of a Local Law to amend Town Code.

## Details
- **Location**: Pages 22-27 (6 pages)
- **Document**: [Town Code Amendment Details](2025-08-13-Town-Board-Meeting--05-B-Consider-receipt-of-a-Local-Law-to-ame.md)
- **PDF Segment**: [L02-2-b-consider-receipt-of-a-local-law-to-amend-town-co.pdf](pdf-segments/L02-2-b-consider-receipt-of-a-local-law-to-amend-town-co.pdf)

## Key Content
[Extracted relevant content from the markdown file with proper citations]

**Citations**: 
- Source: Meeting Packet, Pages 22-27
- Processed: 2025-08-13-Town-Board-Meeting--05-B-Consider-receipt-of-a-Local-Law-to-ame.md
```

### Meeting Corpus Implementation

```python
class MeetingCorpus:
    """Meeting-specific knowledge corpus"""
    
    def __init__(self, meeting_dir: str, config: Dict[str, Any]):
        self.meeting_dir = Path(meeting_dir)
        self.config = config
        self.markdown_dir = self.meeting_dir / "markdown"
        self.index_dir = self.meeting_dir / ".index"
        
    def index_meeting(self) -> bool:
        """Index all meeting documents for retrieval"""
        
        # 1. Load meeting metadata
        metadata = self._load_metadata()
        
        # 2. Process each markdown document
        documents = []
        for doc_info in metadata.get('documents', []):
            doc_path = self.markdown_dir / doc_info['filename']
            doc_content = self._process_document(doc_path, doc_info)
            documents.append(doc_content)
        
        # 3. Create searchable index
        self._create_search_index(documents)
        
        # 4. Build agenda item lookup
        self._build_agenda_index(metadata)
        
        return True
    
    def search_meeting(self, query: str, filters: Dict[str, Any] = None, top_k: int = 5) -> List[Evidence]:
        """Search meeting documents"""
        
        # Implement semantic + keyword search
        # Return ranked evidence with proper citations
        pass
```

## Agent CLI Interface

### New CLI Commands

```bash
# Query meeting expert agent
python -m src query --meeting-dir <MEETING_DIR> --agent meeting_expert --question "What's on the agenda?"

# Interactive mode
python -m src interactive --meeting-dir <MEETING_DIR> --agent meeting_expert

# Index meeting for faster querying
python -m src index_meeting --meeting-dir <MEETING_DIR>

# List available agents
python -m src list_agents
```

### CLI Implementation

```python
@cli.command()
@click.option('--meeting-dir', required=True, help='Path to meeting directory')
@click.option('--agent', default='meeting_expert', help='Agent to use for query')
@click.option('--question', required=True, help='Question to ask the agent')
@click.pass_context
def query(ctx, meeting_dir, agent, question):
    """Query an AI agent about meeting content"""
    config = ctx.obj['config']
    
    # Initialize agent
    if agent == 'meeting_expert':
        agent_instance = MeetingExpertAgent('meeting_expert', config)
    else:
        click.echo(f"❌ Unknown agent: {agent}")
        sys.exit(1)
    
    # Process query
    query_obj = AgentQuery(
        question=question,
        meeting_dir=meeting_dir
    )
    
    try:
        response = agent_instance.query(query_obj)
        
        # Display response
        click.echo(f"\n📋 **Answer** (Confidence: {response.confidence:.2f})")
        click.echo(response.answer)
        
        if response.citations:
            click.echo(f"\n📚 **Sources**:")
            for citation in response.citations:
                click.echo(f"  - {citation.file_path} {citation.anchor or ''}")
                
    except Exception as e:
        click.echo(f"❌ Query failed: {e}")
        sys.exit(1)

@cli.command()
@click.option('--meeting-dir', required=True, help='Path to meeting directory')
@click.option('--agent', default='meeting_expert', help='Agent for interactive session')
@click.pass_context
def interactive(ctx, meeting_dir, agent):
    """Start interactive Q&A session with an agent"""
    config = ctx.obj['config']
    
    # Initialize agent
    agent_instance = MeetingExpertAgent('meeting_expert', config)
    
    click.echo(f"🤖 Starting interactive session with {agent}")
    click.echo(f"📁 Meeting: {meeting_dir}")
    click.echo("💡 Type 'exit' to quit, 'help' for suggestions\n")
    
    while True:
        question = click.prompt("❓ Your question")
        
        if question.lower() == 'exit':
            break
        elif question.lower() == 'help':
            click.echo("""
💡 **Suggested Questions:**
- "What's on the agenda for this meeting?"
- "Tell me about agenda item 5B"
- "What documents are related to permits?"
- "Who needs to speak at this meeting?"
- "What are the key issues being discussed?"
            """)
            continue
        
        # Process query
        query_obj = AgentQuery(question=question, meeting_dir=meeting_dir)
        
        try:
            response = agent_instance.query(query_obj)
            click.echo(f"\n🤖 **Answer** (Confidence: {response.confidence:.2f})")
            click.echo(response.answer)
            
            if response.citations:
                click.echo(f"\n📚 **Sources**: {len(response.citations)} citations")
            click.echo()
            
        except Exception as e:
            click.echo(f"❌ Error: {e}\n")
```

## Configuration Updates

### Enhanced config.yaml

```yaml
# Meeting Expert Agent Configuration
agents:
  meeting_expert:
    enabled: true
    llm_provider: "openai"
    model: "gpt-5"                    # Primary model
    temperature: 0.2                  # Low temperature for factual responses
    max_tokens: 3000
    knowledge_sources: ["meeting"]    # Uses meeting corpus
    response_format: "markdown"       # Format responses in markdown
    citation_required: true          # Always include citations
    max_evidence_items: 10           # Max evidence pieces to consider
    confidence_threshold: 0.7        # Minimum confidence to respond
    
  town_attorney:
    enabled: false                   # Disabled until implemented
    llm_provider: "openai"
    model: "gpt-5"
    temperature: 0.1
    max_tokens: 2000
    knowledge_sources: ["town_code", "meeting"]
    require_citations: true
    fail_on_missing_citations: true

# Knowledge Provider Configuration  
knowledge:
  meeting_corpus:
    source_dir_pattern: "<MEETING_DIR>/markdown"     # Configurable path
    index_dir_pattern: "<MEETING_DIR>/.index"        # Configurable index location
    metadata_file: "metadata.json"                   # Metadata filename
    chunk_size: 1000                                # Document chunk size for search
    chunk_overlap: 200                              # Overlap between chunks
    enable_semantic_search: true                    # Use embeddings
    enable_keyword_search: true                     # Use keyword search
    rerank_results: true                           # Rerank combined results
    
  embeddings:
    provider: "openai"                             # or "local"
    model: "text-embedding-3-large"               # Embedding model
    dimension: 3072                               # Embedding dimension
    batch_size: 100                              # Batch size for embedding

# Storage Configuration with Configurable Paths
storage:
  data_directory: "./data"                         # Base data directory
  meetings_root: "data/meetings"                   # Default meetings location
  town_code_dir: "data/town-code/markdown"        # Default town code location
  meeting_locator:
    mode: "explicit"                              # "explicit" | "by_date"  
    date_pattern: "{YYYY-MM-DD}-{type}"          # Used only if mode == "by_date"
    metadata_filename: "metadata.json"           # Meeting metadata file
    
# CLI Configuration
cli:
  default_agent: "meeting_expert"                # Default agent for queries
  interactive_mode: true                         # Enable interactive sessions
  auto_index: true                              # Auto-index meetings on first query
  response_format: "markdown"                   # Default response format
```

## Data Schemas

### Meeting Index Schema

```json
{
  "meeting_dir": "/path/to/meeting",
  "indexed_at": "2025-01-15T10:30:00Z",
  "documents": [
    {
      "filename": "2025-08-13-Town-Board-Meeting--01-B-Administrator-Update.md",
      "document_type": "agenda_item",
      "item_id": "1B", 
      "section": "ADMINISTRATIVE",
      "title": "Administrator Update",
      "page_range": "1-3",
      "pdf_segment": "pdf-segments/L02-1-b-administrator-update.pdf",
      "chunks": [
        {
          "chunk_id": "meeting_001_chunk_001",
          "start_char": 0,
          "end_char": 500,
          "content": "...",
          "embedding": [0.1, 0.2, ...]
        }
      ]
    }
  ],
  "agenda_items": [
    {
      "id": "1B",
      "item_number": "1B", 
      "section": "ADMINISTRATIVE",
      "title": "Administrator Update",
      "description": "Monthly update from town administrator",
      "markdown_file": "2025-08-13-Town-Board-Meeting--01-B-Administrator-Update.md",
      "pdf_segment": "pdf-segments/L02-1-b-administrator-update.pdf",
      "page_range": "1-3",
      "page_count": 3,
      "attachments": [],
      "keywords": ["administration", "update", "monthly", "report"],
      "participants": ["Town Administrator"],
      "action_required": false
    }
  ],
  "search_index": {
    "keyword_index": {...},
    "semantic_index": {...}
  }
}
```

### Agent Response Schema

```json
{
  "query": "What's on the agenda for this meeting?",
  "agent": "meeting_expert",
  "response": {
    "answer": "This meeting has 18 agenda items...",
    "confidence": 0.95,
    "reasoning": "Found comprehensive agenda information in meeting index...",
    "evidence": [
      {
        "chunk_id": "meeting_001_chunk_idx",
        "file_path": "index.md",
        "content": "Meeting agenda overview content...",
        "relevance_score": 0.98,
        "source_type": "index",
        "metadata": {
          "document_type": "index",
          "section": "overview"
        }
      }
    ],
    "citations": [
      {
        "source": "meeting",
        "file_path": "index.md", 
        "text": "This meeting has 18 agenda items organized into...",
        "chunk_id": "meeting_001_chunk_idx"
      }
    ],
    "metadata": {
      "processing_time_ms": 1250,
      "evidence_count": 3,
      "model_used": "gpt-5"
    }
  }
}
```

## Implementation Priority

### Phase 1: Core Agent Framework (Week 1)
1. **Agent Interface Implementation**
   - `BaseAgent` abstract class
   - `AgentQuery`, `AgentResponse`, `Evidence`, `Citation` data classes
   - `KnowledgeProvider` interface

2. **Meeting Corpus Implementation**  
   - `MeetingCorpus` class
   - Meeting indexing from existing markdown
   - Basic document retrieval

### Phase 2: Meeting Expert Agent (Week 2)
1. **Agent Implementation**
   - `MeetingExpertAgent` class
   - Query intent analysis
   - Evidence retrieval and ranking

2. **Response Generation**
   - LLM integration with GPT-5
   - Grounded response generation with citations
   - Confidence scoring

### Phase 3: CLI Integration (Week 3)
1. **CLI Commands**
   - `query` command for single questions
   - `interactive` command for Q&A sessions
   - `index_meeting` command for pre-indexing

2. **User Experience**
   - Response formatting and display
   - Error handling and user guidance
   - Help system and example queries

### Phase 4: Enhancement & Testing (Week 4)
1. **Quality Improvements**
   - Citation validation
   - Response quality scoring
   - Error handling and fallbacks

2. **Testing & Documentation**
   - Unit tests for agent components
   - Integration tests with real meeting data
   - Usage documentation and examples

## Success Criteria

### Functional Requirements
- ✅ Agent correctly identifies agenda documents and structure
- ✅ Agent provides accurate answers with proper citations  
- ✅ Agent handles various query types (overview, specific items, document search)
- ✅ CLI provides intuitive interface for both single queries and interactive sessions

### Quality Requirements
- **Response Accuracy**: > 90% factually correct responses
- **Citation Coverage**: 100% of claims have supporting citations
- **Response Time**: < 3 seconds for typical queries
- **Confidence Calibration**: Confidence scores correlate with actual accuracy

### Example Success Scenarios

1. **Agenda Overview Query**
   - User: "What's on the agenda?"
   - Response: Complete agenda listing with item numbers, titles, and page references
   - Citations: Links to index.md and relevant agenda documents

2. **Specific Item Query**
   - User: "Tell me about agenda item 5B"
   - Response: Detailed information about the agenda item including content summary
   - Citations: Direct links to markdown file and PDF segment

3. **Document Search Query**
   - User: "What documents mention permits?"
   - Response: List of relevant documents and agenda items with permit-related content
   - Citations: Specific excerpts from relevant documents with page references

This Meeting Expert Agent will provide the foundation for the broader agent framework while delivering immediate value by making meeting content easily queryable and accessible.