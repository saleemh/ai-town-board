# AI Town Board Prep System

Automated collection and AI-powered analysis of North Castle town board meeting documents.

## Overview

This system automatically:
- Collects meeting agendas, packets, and attachments from the board portal
- Converts PDFs to searchable markdown using IBM Docling
- Provides AI analysis by specialized agents (starting with Town Attorney perspective)
- Organizes documents for historical reference and analysis

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

3. **Check system status:**
   ```bash
   python -m src status
   ```

4. **Collect meeting documents:**
   ```bash
   python -m src collect --date 2024-08-13
   ```

## Commands

- `python -m src status` - Show system configuration and status
- `python -m src test-auth` - Test board portal authentication
- `python -m src collect --date YYYY-MM-DD` - Collect documents for specific date
- `python -m src collect-range --start DATE --end DATE` - Collect date range

## Architecture

- **Data Collector** - Authenticates and downloads from board portal
- **Document Processor** - Converts PDFs to markdown (IBM Docling integration)
- **Agent Framework** - Extensible AI analysis system
- **Town Attorney Agent** - Legal analysis and town code compliance

## Development Status

**Phase 1 Complete**: Foundation with document collection pipeline  
**Phase 2 Planned**: Town code integration and processing  
**Phase 3 Planned**: Full AI agent framework and analysis

## Data Structure

```
data/
├── meetings/YYYY-MM-DD-regular/
│   ├── originals/          # Downloaded PDFs
│   ├── markdown/           # Processed documents  
│   ├── analysis/           # AI agent assessments
│   └── metadata.json       # Meeting info & agenda items
└── town-code/              # Town code repository (Phase 2)
```