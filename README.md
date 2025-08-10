# AI Town Board Prep System

Automated collection and AI-powered analysis of North Castle town board meeting documents.

## 🎯 Current Status (Phase 1 Complete)

**✅ What Works Now:**
- 🔐 **Board portal authentication** via OAuth2 with CivicPlus
- 📅 **Meeting discovery** - automatically finds available meetings 
- 📄 **Document collection** - downloads agendas, minutes, and attachments
- 📁 **File organization** - creates structured directories with metadata
- 🖥️ **CLI interface** - easy commands for all operations

**🔄 What's Planned:**
- 📝 **Document processing** - IBM Docling integration for PDF → Markdown
- 📚 **Town code collection** - scrape and organize local ordinances  
- 🤖 **AI agent framework** - specialized analysis (Town Attorney, etc.)

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   ```bash
   cp config/board_portal_creds.example.json config/board_portal_creds.json
   # Edit the file with your board portal login credentials
   ```

3. **Test the system:**
   ```bash
   python -m src status           # Check configuration
   python -m src test-auth        # Test portal access
   python -m src list-meetings    # Browse available meetings
   ```

4. **Collect meeting documents:**
   ```bash
   python -m src collect --date 2025-08-04
   ```

## 📋 Available Commands

| Command | Description | Status |
|---------|-------------|---------|
| `python -m src status` | Show system configuration | ✅ Working |
| `python -m src test-auth` | Test board portal authentication | ✅ Working |
| `python -m src list-meetings` | List available meetings from portal | ✅ Working |
| `python -m src collect --date YYYY-MM-DD` | Collect documents for specific date | ✅ Working |
| `python -m src collect-range --start DATE --end DATE` | Collect date range | ✅ Working |

Currently creates this structure when collecting meetings:

```
data/
├── meetings/YYYY-MM-DD-regular/
│   ├── originals/              # ✅ Downloaded PDFs (working)
│   │   ├── agendas.pdf
│   │   ├── minutes.pdf
│   │   └── attachments/
│   ├── markdown/               # ✅ Placeholder files (working)
│   │   ├── agendas.md          # 🔄 Will contain full content when Docling integrated
│   │   ├── minutes.md
│   │   └── attachments/
│   ├── analysis/               # 📁 Empty (Phase 3)
│   └── metadata.json           # ✅ Complete meeting info (working)
└── town-code/                  # 📁 Not yet implemented (Phase 2)
```

## 🚀 Implementation Roadmap

### ✅ Phase 1: Document Collection Pipeline (COMPLETE)
- [x] OAuth2 authentication with CivicPlus board portal
- [x] Meeting discovery using date-based URL patterns  
- [x] Document detection and download (PDFs, attachments)
- [x] File organization with structured directories
- [x] JSON metadata generation for each meeting
- [x] CLI interface with status, auth testing, and collection commands
- [x] Error handling and retry logic
- [x] Session management and persistence

**Result**: Users can now discover and download all meeting documents automatically.

### 🔄 Phase 2: Document Processing & Town Code (PLANNED)
- [ ] IBM Docling integration for PDF → Markdown conversion
- [ ] OCR processing for scanned documents
- [ ] Town code scraping from ecode360.com
- [ ] Code section organization and indexing
- [ ] Enhanced document parsing for agenda items
- [ ] Table and image preservation in markdown

### 🤖 Phase 3: AI Agent Framework (PLANNED)  
- [ ] Agent architecture with plugin system
- [ ] Town Attorney agent for legal analysis
- [ ] Code compliance checking against meeting items
- [ ] Automated summaries and insights
- [ ] Historical trend analysis
- [ ] Alert system for significant items

## 🛠️ Technical Architecture

**Current Implementation:**
- **Authentication**: OAuth2 flow with form-based login completion
- **Meeting Discovery**: Tests date-based URLs (`/Agendas?date=YYYY-MM-DD`)
- **Document Detection**: Parses HTML for PDF links and download URLs  
- **File Management**: Async downloads with retry logic and progress tracking
- **Data Organization**: JSON metadata with full document and meeting information

**Technology Stack:**
- Python 3.8+ with asyncio for concurrent operations
- httpx for HTTP client with session persistence
- BeautifulSoup for HTML parsing  
- Click for CLI interface
- YAML for configuration management

## 📖 Example Usage

**Discover available meetings:**
```bash
$ python -m src list-meetings --limit 5
🔍 Discovering available meetings...

📅 Found 5 meetings:

 1. 📋 August 04, 2025 (regular)
    Agendas - Board Portal
    📋 2025-08-04

 2. 📋 July 21, 2025 (regular)
    Agendas - Board Portal  
    📋 2025-07-21
...
```

**Collect documents for a specific meeting:**
```bash
$ python -m src collect --date 2025-08-04
Collecting documents for meeting date: 2025-08-04
✅ Successfully collected 2 documents
  ✅ agendas.pdf (36,722 bytes)
  ✅ minutes.pdf (30,039 bytes)
```

**Check what was collected:**
```bash
$ ls data/meetings/2025-08-04-regular/
originals/  markdown/  analysis/  metadata.json

$ ls data/meetings/2025-08-04-regular/originals/
agendas.pdf  minutes.pdf  attachments/
```

## 📋 Next Steps

1. **For Users**: The system is ready for document collection. Run `list-meetings` to see available meetings and `collect` to download documents.

2. **For Developers**: 
   - See `AI_TOWN_BOARD_PREP_SPEC.md` for complete technical specification
   - Phase 2 priority: IBM Docling integration for PDF processing
   - Phase 3 priority: AI agent framework development

## 🔗 Additional Documentation

- **[Technical Specification](AI_TOWN_BOARD_PREP_SPEC.md)** - Complete system design and architecture
- **Configuration** - See `config/` directory for settings and credentials setup
- **License** - MIT License (see LICENSE file)