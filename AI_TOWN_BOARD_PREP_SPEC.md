# AI Town Board Prep System - Technical Specification

## Project Overview

The AI Town Board Prep System is a focused solution for intelligent processing and analysis of town board meeting documents. The system processes user-provided PDFs using advanced AI to generate insights and analysis from specialized AI agents.

### Key Objectives
1. **Document Processing**: Convert user-provided PDFs to searchable markdown using IBM Docling
2. **AI Analysis**: Deploy specialized AI agents to analyze meeting content with domain expertise
3. **Extensible Architecture**: Support addition of new agent types with minimal code changes
4. **Data Organization**: Maintain well-structured data storage for historical reference and analysis
5. **Simplified Workflow**: Focus on processing and analysis rather than document collection

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Engine                             │
├─────────────────────────────────────────────────────────────────┤
│  Universal PDF Processor │         Agent Framework              │
│                          │                                      │
│  • IBM Docling           │  • Town Attorney                     │
│  • Smart Segmentation    │  • Future Agents                     │
│  • TOC-Driven Splitting  │  • Plugin System                     │
│  • Cross-Reference Gen   │  • Analysis Generation               │
├─────────────────────────────────────────────────────────────────┤
│                    Data Storage Layer                           │
│  • Meeting Data   │  • Town Code Data     │  • Agent Analysis  │
│  • File Management • Metadata Store      │  • Historical Data  │
└─────────────────────────────────────────────────────────────────┘
```

### Universal PDF Processing Architecture

The system uses a generalized PDF processing pipeline that works for any structured document:

```
PDF Input → TOC Analysis → Intelligent Segmentation → Markdown Generation
    ↓             ↓                    ↓                      ↓
Any PDF    Chapter/Section      Document Splitting      Structured Output
           Detection            Based on Content         With Metadata
```

**Document Types Supported:**
- **Meeting Documents**: Agendas, minutes, attachments (typically 10-50 pages)
- **Municipal Code**: Complete legal code (500-1000+ pages) 
- **Report Documents**: Environmental studies, planning reports (50-200 pages)
- **Legal Documents**: Ordinances, resolutions, contracts (variable length)

## Universal PDF Processing Implementation

### Core Processing Pipeline

#### 1. Document Analysis Phase
```python
class DocumentProcessor:
    def analyze_document(self, pdf_path: Path) -> DocumentAnalysis:
        """Analyze PDF structure and determine processing strategy"""
        doc = docling.load_document(pdf_path)
        
        analysis = DocumentAnalysis()
        analysis.page_count = doc.page_count
        analysis.toc = doc.extract_table_of_contents()
        analysis.structure = self._detect_structure_type(doc)
        analysis.segmentation_strategy = self._determine_segmentation(analysis)
        
        return analysis

    def _detect_structure_type(self, doc) -> DocumentType:
        """Detect if document is meeting agenda, municipal code, report, etc."""
        # AI-powered structure detection based on content patterns
        pass
```

#### 2. Intelligent Segmentation Phase
```python
def segment_document(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
    """Split document into logical segments based on structure"""
    
    if analysis.structure == DocumentType.MUNICIPAL_CODE:
        return self._segment_by_chapters(pdf_path, analysis.toc)
    elif analysis.structure == DocumentType.MEETING_AGENDA:
        return self._segment_by_agenda_items(pdf_path, analysis)
    elif analysis.structure == DocumentType.SINGLE_DOCUMENT:
        return [DocumentSegment(pdf_path, 1, analysis.page_count)]
    else:
        return self._segment_by_sections(pdf_path, analysis.toc)

def _segment_by_chapters(self, pdf_path: Path, toc: TableOfContents) -> List[DocumentSegment]:
    """Municipal code: one file per chapter"""
    segments = []
    for chapter in toc.chapters:
        segment = DocumentSegment(
            source_path=pdf_path,
            start_page=chapter.start_page,
            end_page=chapter.end_page,
            title=chapter.title,
            segment_type="chapter",
            metadata={"chapter_number": chapter.number}
        )
        segments.append(segment)
    return segments

def _segment_by_agenda_items(self, pdf_path: Path, analysis: DocumentAnalysis) -> List[DocumentSegment]:
    """Meeting agenda: logical sections (public hearings, new business, etc.)"""
    # AI-powered agenda item detection
    pass
```

#### 3. Markdown Generation Phase
```python
def process_segment(self, segment: DocumentSegment) -> ProcessedDocument:
    """Convert PDF segment to structured markdown"""
    
    # Extract pages for this segment
    segment_pdf = self._extract_pages(segment.source_path, 
                                    segment.start_page, 
                                    segment.end_page)
    
    # Process with docling
    processed = docling.process_document(
        segment_pdf,
        preserve_hierarchy=True,
        extract_tables=True,
        ocr_enabled=True,
        output_format="markdown"
    )
    
    # Post-process for structure and cross-references
    markdown = self._enhance_markdown(processed, segment)
    
    return ProcessedDocument(
        content=markdown,
        metadata=segment.metadata,
        cross_references=self._extract_references(markdown)
    )
```

### Document-Specific Processors

#### Town Code Processor
```python
class TownCodeProcessor(UniversalDocumentProcessor):
    """Specialized processor for municipal code documents"""
    
    def process(self, pdf_path: Path) -> TownCodeResult:
        # Use base class for analysis and segmentation
        analysis = self.analyze_document(pdf_path)
        segments = self.segment_document(pdf_path, analysis)
        
        # Process each chapter
        chapters = []
        for segment in segments:
            chapter = self.process_segment(segment)
            chapter = self._enhance_legal_formatting(chapter)
            chapter = self._extract_definitions(chapter)
            chapters.append(chapter)
        
        # Generate cross-references and search index
        cross_refs = self._generate_cross_references(chapters)
        search_index = self._build_search_index(chapters)
        
        return TownCodeResult(
            chapters=chapters,
            cross_references=cross_refs,
            search_index=search_index,
            metadata=self._create_metadata(analysis)
        )
```

#### Meeting Document Processor  
```python
class MeetingDocumentProcessor(UniversalDocumentProcessor):
    """Specialized processor for meeting documents"""
    
    def process(self, pdf_path: Path) -> MeetingDocumentResult:
        analysis = self.analyze_document(pdf_path)
        
        if analysis.page_count <= 50:  # Typical meeting doc
            # Process as single document with sections
            document = self.process_as_single(pdf_path)
            agenda_items = self._extract_agenda_items(document)
        else:  # Large meeting packet
            # Segment by major sections
            segments = self.segment_document(pdf_path, analysis)
            sections = [self.process_segment(seg) for seg in segments]
            agenda_items = self._extract_agenda_items_from_sections(sections)
        
        return MeetingDocumentResult(
            content=document or sections,
            agenda_items=agenda_items,
            metadata=self._create_metadata(analysis)
        )
```

### Configuration-Driven Processing

```yaml
document_processing:
  docling:
    ocr_enabled: true
    table_extraction: true
    image_processing: true
    output_format: "markdown"
    batch_size: 5
  
  segmentation:
    municipal_code:
      strategy: "chapter_based"
      min_chapter_pages: 3
      preserve_legal_numbering: true
    
    meeting_documents:
      strategy: "content_based" 
      max_single_file_pages: 50
      extract_agenda_items: true
    
    reports:
      strategy: "section_based"
      detect_appendices: true
```

This universal architecture allows the town code processor to be a specialized implementation of the general PDF processing system, while meeting documents and other PDF types can use the same underlying infrastructure with different segmentation strategies.

## Data Architecture

### Directory Structure
```
/data/
├── meetings/                           # Meeting-specific data
│   └── {YYYY-MM-DD}-{meeting-type}/   # Date-based organization
│       ├── originals/                 # Raw downloaded files
│       │   ├── agenda.pdf
│       │   ├── packet.pdf
│       │   └── attachments/
│       ├── markdown/                  # Processed markdown files
│       │   ├── agenda.md
│       │   ├── packet.md
│       │   └── attachments/
│       ├── metadata.json              # Meeting info & agenda items
│       └── analysis/                  # AI agent assessments
│           └── town-attorney/
│               ├── assessment.md
│               └── relevant-codes.json
├── town-code/                         # Town code repository
│   ├── originals/                     # Raw scraped content
│   │   └── ecode360-backup/
│   ├── markdown/                      # Processed code sections
│   │   ├── chapter-001.md
│   │   ├── chapter-002.md
│   │   └── index.md
│   └── metadata.json                  # Structure & update info
└── templates/                         # Agent prompt templates
    ├── town-attorney-prompts.json
    └── agent-configs/
```

### Metadata Schema

#### Meeting Metadata (`metadata.json`)
```json
{
  "meeting_date": "2024-08-13",
  "meeting_type": "regular",
  "collection_timestamp": "2024-08-10T16:30:00Z",
  "board_portal_url": "https://northcastleny.boardportal.civicclerk.com/...",
  "documents": [
    {
      "filename": "agenda.pdf",
      "document_type": "agenda",
      "download_url": "https://...",
      "file_size": 2048576,
      "processed": true,
      "markdown_file": "agenda.md"
    }
  ],
  "agenda_items": [
    {
      "id": "item_001",
      "section": "PUBLIC HEARINGS",
      "title": "Special Use Permit Request - Mianus River Gorge",
      "description": "Consider request for Scientific Research Center...",
      "documents": ["agenda.pdf", "attachments/environmental-report.pdf"],
      "analysis_complete": true
    }
  ]
}
```

#### Town Code Metadata
```json
{
  "last_updated": "2024-08-10T16:30:00Z",
  "source_url": "https://ecode360.com/NO0492",
  "chapters": [
    {
      "number": "1",
      "title": "General Provisions",
      "markdown_file": "chapter-001.md",
      "last_modified": "2024-07-15"
    }
  ],
  "total_sections": 156,
  "processing_complete": true
}
```

## Core Modules

### 1. Data Collector (`src/collectors/`)

#### Board Portal Collector
- **Authentication**: Handle CivicPlus OAuth2 flow
- **Session Management**: Maintain authenticated sessions
- **Meeting Discovery**: Find meetings by date range
- **Document Download**: Collect agendas, packets, attachments
- **Incremental Updates**: Refresh changed documents

**Key Files:**
- `board_portal_collector.py` - Main collector class
- `auth_manager.py` - Authentication handling
- `session_manager.py` - Session persistence
- `document_detector.py` - Find downloadable documents

#### Implementation Approach
```python
class BoardPortalCollector:
    def __init__(self, config):
        self.auth = AuthManager(config)
        self.session = SessionManager()
        
    def collect_meeting_data(self, meeting_date):
        """Collect all documents for a specific meeting date"""
        # 1. Authenticate with board portal
        # 2. Navigate to meeting date
        # 3. Discover available documents
        # 4. Download to organized structure
        # 5. Update metadata
```

### 2. Document Processor (`src/processors/`)

#### Docling Integration
- **PDF Processing**: Convert PDFs to markdown with layout preservation
- **OCR Support**: Handle scanned documents and images
- **Table Extraction**: Preserve table structure in markdown
- **Batch Processing**: Process multiple documents efficiently
- **Quality Validation**: Verify conversion quality

**Key Files:**
- `docling_processor.py` - Main processing engine
- `document_converter.py` - Format-specific converters
- `quality_checker.py` - Validation and QA
- `batch_processor.py` - Concurrent processing

#### Processing Pipeline
```python
class DoclingProcessor:
    def process_document(self, file_path, output_path):
        """Convert document to markdown using docling"""
        # 1. Load document with docling
        # 2. Extract text, tables, images
        # 3. Convert to markdown format
        # 4. Validate output quality
        # 5. Save with metadata
```

### 3. Town Code Manager (`src/tools/town_code/`)

#### Code Collection & Processing
- **Web Scraping**: Navigate ecode360.com structure (handle 403 restrictions)
- **Content Processing**: Convert HTML to markdown
- **Search Indexing**: Build searchable code database
- **Update Monitoring**: Track changes to town code
- **Section Mapping**: Organize by chapters and sections

**Key Files:**
- `code_collector.py` - Scrape ecode360.com
- `code_processor.py` - HTML to markdown conversion
- `code_searcher.py` - Search and retrieval
- `update_monitor.py` - Change detection

#### Challenge: ecode360.com Access
The town code site returned 403 Forbidden, requiring solutions:
1. **User-Agent Rotation**: Mimic legitimate browser requests
2. **Session Handling**: Maintain proper session state
3. **Rate Limiting**: Respectful scraping intervals
4. **Proxy Support**: If IP-based blocking occurs
5. **Manual Fallback**: User-assisted initial collection if needed

### 4. Agent Framework (`src/agents/`)

#### Extensible Agent Architecture
- **Base Agent Class**: Common interface for all agents
- **Plugin System**: Easy addition of new agent types
- **Prompt Management**: Template-based prompting system
- **Analysis Pipeline**: Structured analysis workflow
- **Output Formatting**: Consistent analysis format

**Key Files:**
- `base_agent.py` - Abstract agent interface
- `agent_manager.py` - Agent coordination
- `prompt_templates.py` - Template management
- `analysis_formatter.py` - Output standardization

#### Base Agent Interface
```python
class BaseAgent:
    def __init__(self, name, config):
        self.name = name
        self.config = config
        
    def analyze_agenda_item(self, agenda_item, meeting_context):
        """Analyze single agenda item with agent expertise"""
        # 1. Load relevant knowledge base
        # 2. Apply agent-specific analysis
        # 3. Generate structured output
        # 4. Return formatted assessment
        
    def get_relevant_context(self, agenda_item):
        """Retrieve agent-specific context for analysis"""
        pass  # Implemented by specific agents
```

### 5. Town Attorney Agent (`src/agents/town_attorney/`)

#### Specialized Analysis Capabilities
- **Code Relevance Detection**: Find applicable town code sections
- **Legal Precedent Analysis**: Reference previous similar items
- **Compliance Assessment**: Evaluate regulatory compliance
- **Risk Identification**: Flag potential legal issues
- **Recommendation Generation**: Provide actionable guidance

**Key Files:**
- `town_attorney_agent.py` - Main agent implementation
- `code_matcher.py` - Town code relevance detection
- `legal_analyzer.py` - Legal analysis engine
- `precedent_searcher.py` - Historical case analysis

#### Analysis Output Format
```markdown
# Town Attorney Analysis - [Agenda Item Title]

## Relevant Town Code Sections
- **Chapter 5, Section 5-3**: Special Use Permits
  - Relevance: Direct application to proposed scientific research center
  - Key Requirements: Environmental impact assessment required
  
## Legal Considerations
- Environmental review requirements under SEQRA
- Public hearing notice requirements (10-day minimum)
- Potential appeals process considerations

## Recommendations
1. Ensure all environmental documentation is complete
2. Verify public notice requirements have been met
3. Consider potential traffic impact studies

## Risk Assessment: LOW
- Standard SUP process being followed
- No apparent procedural issues identified
```

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
**Deliverables:**
- Complete project structure setup
- Board portal authentication working
- Basic document collection pipeline
- Docling integration for PDF processing
- Data storage utilities

**Success Criteria:**
- Can authenticate and access board portal
- Can download meeting documents for any date
- Can convert PDFs to markdown with good quality
- Data is properly organized in defined structure

### Phase 2: Town Code Integration (Week 3)
**Deliverables:**
- ecode360.com scraping solution (addressing 403 issue)
- Town code processing and markdown conversion
- Search and retrieval system for code sections
- Automated update checking

**Success Criteria:**
- Complete town code ingested as searchable markdown
- Can find relevant code sections by keyword
- System tracks code updates automatically
- Town code knowledge base ready for AI analysis

### Phase 3: Agent Framework (Weeks 4-5)
**Deliverables:**
- Extensible agent architecture
- Town Attorney agent implementation
- Analysis workflow and output formatting
- Agent coordination system

**Success Criteria:**
- Town Attorney agent provides relevant code analysis
- Analysis output is consistent and actionable
- Framework supports easy addition of new agents
- End-to-end analysis workflow functional

### Phase 4: Integration & Polish (Week 6)
**Deliverables:**
- Full workflow orchestration
- Comprehensive error handling
- Performance optimization
- Documentation and examples

**Success Criteria:**
- System runs end-to-end without manual intervention
- Handles errors gracefully with retry logic
- Processes typical meeting in under 10 minutes
- Clear documentation for usage and extension

## Technical Requirements

### Dependencies
- **Python 3.9+**: Core runtime
- **IBM Docling**: Document processing
- **civic-scraper**: Board portal integration (if suitable)
- **requests/httpx**: HTTP client for custom scraping
- **BeautifulSoup4**: HTML parsing
- **OpenAI/Anthropic APIs**: AI agent backends
- **asyncio**: Concurrent processing
- **pytest**: Testing framework

### Performance Targets
- **Document Processing**: < 30 seconds per PDF
- **Meeting Collection**: < 5 minutes for complete meeting
- **AI Analysis**: < 2 minutes per agenda item
- **Town Code Search**: < 1 second response time
- **System Memory**: < 2GB typical operation

### Security Considerations
- **Credential Storage**: Encrypted configuration files
- **API Key Management**: Environment variable isolation
- **Rate Limiting**: Respectful scraping practices
- **Data Privacy**: No sensitive info in logs
- **Access Control**: Secure handling of board portal credentials

## Configuration

### Main Configuration (`config/config.yaml`)
```yaml
board_portal:
  base_url: "https://northcastleny.boardportal.civicclerk.com"
  login_url: "https://cpauthentication.civicplus.com/..."
  credentials_file: "config/board_portal_creds.json"  # encrypted
  
document_processing:
  docling:
    ocr_enabled: true
    table_extraction: true
    image_processing: true
    output_format: "markdown"
    
agents:
  town_attorney:
    enabled: true
    llm_provider: "openai"  # or "anthropic"
    model: "gpt-4"
    temperature: 0.1
    max_tokens: 2000
    
town_code:
  source_url: "https://ecode360.com/NO0492"
  update_check_interval: "weekly"
  search_index_rebuild: "monthly"
  
storage:
  data_directory: "./data"
  backup_enabled: true
  retention_policy: "2_years"
```

## Usage Examples

### Collecting Meeting Data
```bash
# Collect all documents for specific meeting
python -m ai_town_board collect --date 2024-08-13

# Refresh existing meeting (check for updates)
python -m ai_town_board collect --date 2024-08-13 --refresh

# Collect date range
python -m ai_town_board collect --start 2024-08-01 --end 2024-08-31
```

### Running Analysis
```bash
# Analyze specific meeting with all agents
python -m ai_town_board analyze --date 2024-08-13

# Run only Town Attorney analysis
python -m ai_town_board analyze --date 2024-08-13 --agents town_attorney

# Batch analysis for multiple meetings
python -m ai_town_board analyze --start 2024-08-01 --end 2024-08-31
```

### Town Code Management
```bash
# Update town code
python -m ai_town_board update_code

# Search town code
python -m ai_town_board search_code "special use permit"

# Rebuild search index
python -m ai_town_board rebuild_index
```

## Extension Points

### Adding New Agents
1. **Create Agent Class**: Extend `BaseAgent` with specialized logic
2. **Add Configuration**: Update `config.yaml` with agent settings
3. **Implement Analysis**: Define `analyze_agenda_item()` method
4. **Register Agent**: Add to agent factory in `agent_manager.py`

### Custom Document Processors
1. **Extend Processor**: Create new processor for specific formats
2. **Register Handler**: Add to document type mappings
3. **Configure Pipeline**: Update processing workflow

### Integration APIs
- **REST API**: Expose core functions via HTTP endpoints
- **CLI Interface**: Command-line tools for batch operations
- **Webhook Support**: Trigger processing on new meetings
- **Dashboard**: Web interface for monitoring and results

## Success Metrics

### Operational Metrics
- **Collection Success Rate**: > 99% for available documents
- **Processing Accuracy**: > 95% markdown conversion quality
- **Analysis Completeness**: All agenda items analyzed
- **System Uptime**: > 99.5% availability

### Quality Metrics  
- **Agent Relevance**: Manual review of 10% sample shows > 90% relevant code citations
- **Time Savings**: Reduce prep time from hours to minutes
- **Coverage**: Identify 100% of applicable town code sections

This specification provides the foundation for building a robust, extensible AI Town Board Prep system that will significantly enhance meeting preparation efficiency and thoroughness.