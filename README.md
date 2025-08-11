# AI Town Board Prep System

AI-powered municipal document processing system with intelligent PDF-to-Markdown conversion and AI agent framework for automated meeting analysis.

## 🎯 Current Status 

**✅ What This System Does:**
- 📝 **Intelligent PDF Processing** - Uses IBM Docling with OCR, table extraction, and hierarchical structure preservation
- 🏛️ **Municipal Code Processing** - Automatically segments large municipal codes using PDF Table of Contents
- 🤖 **AI Agent Framework** - Multi-provider LLM support (OpenAI GPT-5, Anthropic Claude) for automated document analysis
- 📋 **Meeting Analysis** - Comprehensive 4-section analysis format with real-time processing and incremental file saving
- 🔗 **Obsidian Integration** - Full clickable internal linking for seamless navigation between documents and PDF segments
- 📄 **PDF Fragment Traceability** - Preserves original PDF segments alongside generated markdown for complete transparency
- 🔄 **Hierarchical Document Structure** - Maintains legal document hierarchy with proper cross-referencing
- 🖥️ **Comprehensive CLI** - Rich command set for processing, querying, and analyzing municipal documents

**📋 How It Works:**
1. **Place PDFs** in the appropriate directory structure
2. **System analyzes** document type and extracts Table of Contents structure
3. **Intelligent segmentation** breaks large documents into manageable chapter/agenda-based segments
4. **IBM Docling processes** each segment with advanced OCR and structure detection
5. **Markdown generation** with preserved hierarchy, tables, Obsidian links, and cross-references
6. **PDF fragment preservation** ensures complete traceability back to source material
7. **AI agents analyze** content using GPT-5 or Claude for comprehensive summaries and insights

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up API keys (for AI processing):**
   ```bash
   # Create .env file in project root
   echo "OPENAI_API_KEY=your-openai-api-key" > .env
   echo "ANTHROPIC_API_KEY=your-anthropic-api-key" >> .env
   
   # Or set environment variables
   export OPENAI_API_KEY="your-openai-api-key"       # For GPT-5 analysis
   export ANTHROPIC_API_KEY="your-anthropic-api-key" # For Claude analysis
   ```

3. **Process Municipal Code:**
   ```bash
   # Place your municipal code PDF in: data/town-code/originals/
   cp "Town of North Castle, NY.pdf" data/town-code/originals/
   
   # Process the entire municipal code automatically
   python -m src ingest-town-code
   ```

4. **Reprocess with new PDFs:**
   ```bash
   # Add new/updated PDFs to data/town-code/originals/
   # Then reprocess everything:
   python -m src ingest-town-code --force
   ```

## 📋 Available Commands

### 📄 Document Processing
| Command | Description | Status |
|---------|-------------|---------|
| `python -m src status` | Show system configuration and processing status | ✅ Ready |
| `python -m src ingest-town-code` | Process municipal code PDFs with intelligent TOC-driven segmentation | ✅ **COMPLETE** |
| `python -m src ingest-town-code --force` | Reprocess all municipal code PDFs (use when adding new PDFs) | ✅ **COMPLETE** |
| `python -m src process --folder FOLDER` | Process meeting documents with agenda-based segmentation | ✅ **COMPLETE** |
| `python -m src process-all` | Process all meetings in data directory | ✅ **COMPLETE** |

### 🤖 AI Agent Framework
| Command | Description | Status |
|---------|-------------|---------|
| `python -m src list-agents` | List available AI agents and their capabilities | ✅ **COMPLETE** |
| `python -m src query QUESTION` | Query AI agents about meeting content with evidence | ✅ **COMPLETE** |
| `python -m src analyze --meeting-dir PATH` | Run comprehensive 4-section analysis on meeting documents | ✅ **COMPLETE** |
| `python -m src interactive` | Start interactive Q&A session with meeting expert agent | ✅ **COMPLETE** |
| `python -m src index-meeting --meeting-dir PATH` | Index meeting documents for faster agent querying | ✅ **COMPLETE** |

## 📁 Directory Structure

### 🏛️ Municipal Code Processing (IMPLEMENTED)

```
data/town-code/
├── originals/                          # 📄 Input: Your municipal code PDFs
│   └── Town of North Castle, NY.pdf    # Place your PDF here
├── markdown/                           # 📝 Output: Generated markdown & fragments
│   ├── chapters/                       # Individual chapter markdown files
│   │   ├── L01-3-general-provisions.md
│   │   ├── L01-13-boards-bureaus-and-committees.md
│   │   ├── L01-18-ethics-code-of.md
│   │   └── ... (42 total chapters)
│   ├── pdf-segments/                   # PDF fragments for traceability
│   │   ├── L01-3-general-provisions.pdf     # Pages 3-7 (5 pages)
│   │   ├── L01-13-boards-bureaus-and-committees.pdf  # Pages 10-26 (17 pages)
│   │   └── ... (42 corresponding PDF segments)
│   ├── index.md                        # Master table of contents with hierarchy
│   ├── metadata.json                   # Complete processing metadata
│   └── search-index.json              # Search index for content lookup
```

### 📋 Meeting Documents (IMPLEMENTED)

```
data/meetings/2025-08-13/
├── originals/              # 📄 Input: Your PDF documents
│   └── 2025-08-13 Town Board Meeting Agenda Packet - BOARD.pdf
├── markdown/               # 📝 Output: AI-processed Markdown with Obsidian links
│   ├── 2025-08-13-Town-Board-Meeting--01-B-Administrator-Update.md
│   ├── 2025-08-13-Town-Board-Meeting--02-A-Consider-the-following-Re-request-from.md
│   ├── ... (18 total agenda items)
│   ├── pdf-segments/       # 📄 PDF fragments for traceability
│   │   ├── L02-1-b-administrator-update.pdf
│   │   ├── L02-0-a-consider-the-following-re-request-from-mianus-ri.pdf
│   │   └── ... (18 corresponding PDF segments)
│   ├── index.md           # Master meeting navigation with Obsidian links
│   └── metadata.json      # Complete processing metadata
├── analysis/              # 🤖 AI agent analysis results (real-time generation)
│   ├── agenda_items/      # Individual item analyses (4-section format)
│   │   ├── 2025-08-13-Town-Board-Meeting--01-B-Administrator-Update_analysis.md
│   │   ├── 2025-08-13-Town-Board-Meeting--02-A-Consider-the-following-Re-request-from_analysis.md
│   │   └── ... (18 analysis files)
│   ├── meeting_summary.md # Comprehensive meeting overview with Obsidian links
│   └── agenda_analysis.json # Structured analysis data for programmatic access
└── metadata.json          # 📊 Processing metadata and status
```

## 🚀 Implementation Status

### ✅ Phase 1: Municipal Code Processing - **COMPLETE**
- [x] **Universal PDF Processing System** - Handles any PDF type with intelligent detection
- [x] **IBM Docling Integration** - Advanced PDF → Markdown conversion with OCR
- [x] **TOC-Driven Segmentation** - Automatically segments large PDFs using built-in Table of Contents
- [x] **Hierarchical Structure Preservation** - Maintains legal document hierarchy and cross-references
- [x] **PDF Fragment Traceability** - Saves PDF segments alongside markdown for complete transparency
- [x] **Smart Document Type Detection** - Automatically identifies municipal code vs. other document types
- [x] **Progress Tracking & Logging** - Comprehensive processing status and time estimation
- [x] **Master Index Generation** - Creates searchable index with hierarchical navigation
- [x] **Metadata & Search Index** - Complete processing metadata and content search capabilities
- [x] **Obsidian Integration** - Full clickable internal linking for seamless navigation

### ✅ Phase 2: Meeting Document Processing - **COMPLETE**
- [x] **Meeting agenda intelligent parsing** - Agenda-based segmentation using PDF Table of Contents
- [x] **Multi-document packet handling** - Processes complex meeting packets with multiple agenda items
- [x] **Cross-document reference extraction** - Maintains connections between related agenda items
- [x] **Obsidian-compatible markdown** - Full internal linking for navigation between documents
- [x] **PDF fragment preservation** - Each agenda item preserved as individual PDF segment

### ✅ Phase 3: AI Agent Framework - **COMPLETE**  
- [x] **Multi-provider LLM support** - OpenAI (GPT-5) and Anthropic (Claude Sonnet 4) integration
- [x] **Meeting Expert Agent** - Natural language querying with evidence and citations
- [x] **Meeting Analysis Agent** - Automated 4-section comprehensive analysis format
- [x] **External prompt system** - Configurable prompts via external .md files
- [x] **Real-time processing** - Incremental file saving with progress tracking
- [x] **Interactive CLI mode** - Live Q&A sessions with meeting content
- [x] **Knowledge indexing** - Fast document search and retrieval system

### 🏛️ **Current Capabilities:**

**Municipal Code:**
- **790-page PDF** → **42 chapter-based markdown files**
- **1,739 TOC entries** parsed into hierarchical structure  
- **Complete PDF fragment preservation** for each chapter
- **Processing time**: ~0.4 minutes per chapter segment

**Meeting Documents:**
- **111-page meeting packet** → **18 agenda-based markdown files**
- **Agenda-item segmentation** with individual PDF fragments
- **Real-time AI analysis** generating comprehensive summaries
- **Obsidian integration** with clickable navigation throughout

**AI Analysis:**
- **GPT-5 and Claude support** with provider-specific optimizations
- **4-section analysis format**: Executive Summary, Topics Included, Decisions, Other Takeaways
- **Evidence-based responses** with citations and confidence scoring
- **Interactive querying** with natural language understanding

## 🛠️ Technical Architecture

**Current Implementation:**
- **Document Processing**: IBM Docling for PDF → Markdown conversion with OCR and structure detection
- **AI Integration**: Multi-provider LLM support (OpenAI GPT-5, Anthropic Claude Sonnet 4)
- **Agent Framework**: Plugin-based architecture with BaseAgent interface and specialized implementations
- **Knowledge Management**: Vector-based search with MeetingCorpus and evidence extraction
- **File Management**: Structured directory processing with incremental saving and metadata tracking
- **Configuration**: YAML-based configuration with external prompt system and .env support
- **Integration**: Full Obsidian compatibility with clickable internal linking

**Technology Stack:**
- **Python 3.8+** for core processing
- **IBM Docling** for advanced PDF processing and AI extraction
- **OpenAI/Anthropic APIs** for language model integration with provider-specific optimizations
- **Click** for comprehensive CLI interface
- **YAML** for configuration management
- **python-dotenv** for environment variable loading
- **Obsidian** for knowledge graph navigation and document linking

## 📖 Example Usage

### 📄 Document Processing

**Check system status:**
```bash
$ python -m src status
🏛️  AI Town Board Prep System Status

📋 Configuration:
  Data Directory: ./data
  ✅ Data directory exists
  📁 Existing meetings: 1
  📄 Meetings with PDFs: 1
  📝 Meetings with Markdown: 1
  🤖 AI Agents: 2 configured (Meeting Expert, Meeting Analysis)
  💡 Ready for AI-powered analysis!
```

**Process a specific meeting:**
```bash
$ python -m src process --folder 2025-08-13
Processing documents in folder: 2025-08-13
Found 1 PDF documents:
  📄 2025-08-13 Town Board Meeting Agenda Packet - BOARD.pdf
✅ Successfully processed 18 documents
  ✅ 2025-08-13 Town Board Meeting Agenda Packet - BOARD.pdf → 2025-08-13-Town-Board-Meeting--01-B-Administrator-Update.md
  ✅ 2025-08-13 Town Board Meeting Agenda Packet - BOARD.pdf → 2025-08-13-Town-Board-Meeting--02-A-Consider-the-following-Re-request-from.md
  ...
  ✅ 2025-08-13 Town Board Meeting Agenda Packet - BOARD.pdf → 2025-08-13-Town-Board-Meeting--18-D-Release-of-Highway-Bonds.md
```

### 🤖 AI Agent Usage

**Query meeting content:**
```bash
$ python -m src query "What's on the agenda for tonight's meeting?"
🤖 Meeting Expert Agent Response:

Tonight's August 13, 2025 Town Board meeting agenda includes several key items:

**Public Hearings:**
- Mianus River Gorge Special Use Permit for Scientific Research Center

**Key Business Items:**
- Approval of July 23rd meeting minutes
- Short-term rental regulation Local Law consideration
- Sexual Harassment and Workplace Violence policy adoptions
- Highway equipment purchases ($1.4M total)
- Trust for Public Land conservation assistance agreement

**Evidence Sources:**
- 2025-08-13-Town-Board-Meeting--01-B-Administrator-Update.md (Confidence: 0.95)
- 2025-08-13-Town-Board-Meeting--02-A-Consider-the-following-Re-request-from.md (Confidence: 0.92)
```

**Generate comprehensive analysis:**
```bash
$ python -m src analyze --meeting-dir data/meetings/2025-08-13
🤖 Analyzing meeting documents with Claude Sonnet 4...

📋 Processing 18 agenda items...
Analyzed item 01B: B. Administrator Update
Analyzed item 02A: A. Consider the following Re request from Mianus River Gorge
Analyzed item 03A: A. Approval of Town Board Minutes: July 23, 2025
...
Analyzed item 18D: D. Release of Highway Bonds

✅ Analysis completed successfully!
📊 Generated 18 individual analyses + comprehensive meeting summary
📁 Results saved to: data/meetings/2025-08-13/analysis/
```

**Interactive Q&A session:**
```bash
$ python -m src interactive
🤖 Starting Interactive Session with Meeting Expert Agent
💡 Ask me anything about your meeting documents!

You: Tell me about the Mianus River Gorge item
Agent: The Mianus River Gorge, Inc. is requesting a Special Use Permit for a Scientific Research Center to formalize operations at 167 Mianus River Road. This 960-acre preserve has been operating since 1953 and seeks to legitimize their research and education activities under current zoning requirements.

You: What's the financial impact of tonight's meeting?
Agent: The meeting includes several significant financial items totaling approximately $1.5M:
- Highway Department equipment purchases: $1,442,580.37
- Dog park expenses: ~$50,000 from fund balance
- Tax refund to Stonewall LLC: $7,477.07
- Various bonds and assessments being released

You: exit
Goodbye! 👋
```

**Process municipal code:**
```bash
$ python -m src ingest-town-code
🏛️  Processing Municipal Code: Town of North Castle, NY.pdf
📂 Output directory: data/town-code/markdown

📚 PROCESSING PLAN:
   Total segments: 42
   Total pages: 790
   Estimated processing time: 84-210 minutes
   Each segment will be processed individually with Docling

🔄 PROCESSING SEGMENT 1 of 42
   Section: chapter 1: General Provisions
   Pages: 3-7 (5 pages)
   Progress: 0/42 completed (0.0%)
   🔄 Starting Docling processing for segment...
   ✅ Created permanent PDF segment: L01-3-general-provisions.pdf
   ✅ SEGMENT 1 COMPLETED in 0.4 minutes

✅ Successfully processed municipal code!
📊 Processing Summary:
  📄 Total pages: 790
  📚 Total chapters: 42
  ✅ Successful chapters: 42
  ❌ Failed chapters: 0
  🕐 Total processing time: 16.8 minutes

📁 Output files created:
  📄 Index: data/town-code/markdown/index.md
  📊 Metadata: data/town-code/markdown/metadata.json
  🔍 Search Index: data/town-code/markdown/search-index.json
  📚 Chapters: data/town-code/markdown/chapters/ (42 files)
  📄 PDF Segments: data/town-code/markdown/pdf-segments/ (42 files)
```

## 🔧 Adding Your Documents

### 🏛️ Municipal Code PDFs

Simply place your municipal code PDF in the input directory:

```bash
# Create directory if it doesn't exist
mkdir -p data/town-code/originals

# Add your municipal code PDF
cp "Your Town Code.pdf" data/town-code/originals/

# Process automatically
python -m src ingest-town-code
```

### 📋 Meeting Documents

Add meeting documents to any folder structure you prefer:

```bash
# Create meeting folder (use ANY name you want)
mkdir -p data/meetings/your-folder-name/originals

# Add your meeting PDFs
cp "Meeting Agenda.pdf" data/meetings/your-folder-name/originals/
cp "Meeting Packet.pdf" data/meetings/your-folder-name/originals/

# Process with agenda item segmentation
python -m src process --folder your-folder-name

# Or process all meeting folders at once
python -m src process-all
```

**📄 System automatically handles:**
- Document type detection (Municipal Code vs. Meeting Documents)
- TOC extraction from PDF bookmarks/outline
- Intelligent segmentation (chapters for codes, agenda items for meetings)
- Hierarchical structure preservation
- PDF fragment creation for traceability
- Flexible folder naming for meetings

**💡 Document Sources:**
- Municipal website code repositories
- Legal document archives
- Official town/city government portals
- Legislative document databases

## 📋 Next Steps

### For Users:

**Municipal Code:**
1. **Add your municipal code PDF** to `data/town-code/originals/`
2. **Run the processor**: `python -m src ingest-town-code`  
3. **Explore results** in `data/town-code/markdown/`
   - Browse individual chapters in `chapters/`
   - Check original PDF segments in `pdf-segments/`
   - Use `index.md` for hierarchical navigation

**Meeting Documents:**
1. **Create meeting folder** with any name: `data/meetings/your-folder-name/originals/`
2. **Add meeting PDFs** to the originals folder
3. **Process documents**: `python -m src process --folder your-folder-name`
4. **Explore results** in `data/meetings/your-folder-name/markdown/`
   - Individual agenda item segments with full OCR processing
   - PDF fragments in `pdf-segments/` for traceability
   - Use `index.md` for navigation

**For updates**: Use `--force` flag to reprocess and cleanup previous files

### For Developers:
- **See `AI_TOWN_BOARD_PREP_SPEC.md`** for complete technical specification
- **Current system** is production-ready for municipal code processing, meeting document processing, and AI agent analysis
- **All major phases completed**: Document processing, AI agent framework, and Obsidian integration
- **Extension points**: Easy to add new agent types, document processors, and analysis formats

## 🔗 Additional Documentation

- **[Technical Specification](AI_TOWN_BOARD_PREP_SPEC.md)** - Complete system design and architecture
- **Configuration** - See `config/` directory for processing settings
- **License** - MIT License (see LICENSE file)