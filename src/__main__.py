"""AI Town Board Prep System CLI

Command-line interface for processing meeting documents with AI analysis.
"""

import logging
import re
import sys
from pathlib import Path

import click
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from processors.document_processor import DocumentProcessor
from processors.town_code_processor import TownCodeProcessor
from processors.meeting_processor import MeetingDocumentProcessor
from agents.meeting_expert_agent import MeetingExpertAgent
from agents.meeting_analysis_agent import MeetingAnalysisAgent
from schemas import AgentQuery, AnalysisQuery


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        click.echo(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        click.echo(f"Error parsing configuration file: {e}")
        sys.exit(1)


@click.group()
@click.option('--config', default='config/config.yaml', help='Configuration file path')
@click.option('--log-level', default='INFO', help='Logging level')
@click.pass_context
def cli(ctx, config, log_level):
    """AI Town Board Prep System - AI-powered analysis of meeting documents."""
    ctx.ensure_object(dict)
    
    # Setup logging
    setup_logging(log_level)
    
    # Load configuration
    ctx.obj['config'] = load_config(config)
    

@cli.command()
@click.option('--folder', required=True, help='Meeting folder name (any name allowed)')
@click.option('--force', is_flag=True, help='Reprocess existing markdown files')
@click.pass_context
def process(ctx, folder, force):
    """Process meeting documents to markdown format using Docling."""
    config = ctx.obj['config']
    
    click.echo(f"Processing documents in folder: {folder}")
    
    # Use the folder name directly - no restrictions on format
    data_dir = Path(config['storage']['data_directory'])
    meeting_dir = data_dir / 'meetings' / folder
    
    if not meeting_dir.exists():
        click.echo(f"❌ Meeting directory not found: {meeting_dir}")
        click.echo("Please ensure documents are placed in the correct directory structure:")
        click.echo(f"  {meeting_dir}/originals/")
        sys.exit(1)
    
    originals_dir = meeting_dir / 'originals'
    if not originals_dir.exists() or not any(originals_dir.iterdir()):
        click.echo(f"❌ No documents found in: {originals_dir}")
        sys.exit(1)
    
    # List available documents
    documents = list(originals_dir.glob('*.pdf'))
    if not documents:
        click.echo(f"❌ No PDF files found in: {originals_dir}")
        sys.exit(1)
    
    click.echo(f"Found {len(documents)} PDF documents:")
    for doc in documents:
        click.echo(f"  📄 {doc.name}")
    
    try:
        processor = MeetingDocumentProcessor(config)
        result = processor.process_meeting_directory(meeting_dir, force=force)
        
        processed_docs = [d for d in result['processed_documents'] if d.get('filename')]
        failed_docs = [d for d in result['processed_documents'] if d.get('error')]
        
        click.echo(f"✅ Successfully processed {len(processed_docs)} documents")
        for doc in processed_docs:
            click.echo(f"  ✅ {doc['source_file']} → {doc['filename']}")
        
        if failed_docs:
            click.echo(f"❌ Failed to process {len(failed_docs)} documents")
            for doc in failed_docs:
                click.echo(f"  ❌ {doc['source_file']}: {doc['error']}")
            
    except Exception as e:
        click.echo(f"❌ Processing failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--path', help='Path to meetings directory (default: ./data/meetings)')
@click.option('--force', is_flag=True, help='Reprocess existing markdown files')
@click.pass_context
def process_all(ctx, path, force):
    """Process all meeting documents to markdown format using Docling."""
    config = ctx.obj['config']
    
    # Use provided path or default from config
    meetings_path = Path(path) if path else Path(config['storage']['data_directory']) / 'meetings'
    
    if not meetings_path.exists():
        click.echo(f"❌ Meetings directory not found: {meetings_path}")
        sys.exit(1)
        
    # Find all meeting directories (look for YYYY-MM-DD pattern)
    meeting_dirs = [d for d in meetings_path.iterdir() 
                   if d.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', d.name)]
    
    if not meeting_dirs:
        click.echo(f"❌ No meeting directories found in: {meetings_path}")
        click.echo("Expected format: YYYY-MM-DD-regular/")
        sys.exit(1)
        
    click.echo(f"Found {len(meeting_dirs)} meeting directories:")
    for meeting_dir in sorted(meeting_dirs):
        click.echo(f"  📁 {meeting_dir.name}")
        
    try:
        processor = MeetingDocumentProcessor(config)
        total_processed = 0
        total_failed = 0
        
        for meeting_dir in sorted(meeting_dirs):
            originals_dir = meeting_dir / 'originals'
            if originals_dir.exists() and any(originals_dir.glob('*.pdf')):
                click.echo(f"\n📋 Processing {meeting_dir.name}...")
                
                try:
                    result = processor.process_meeting_directory(meeting_dir, force=force)
                    
                    processed_docs = [d for d in result['processed_documents'] if d.get('filename')]
                    failed_docs = [d for d in result['processed_documents'] if d.get('error')]
                    
                    total_processed += len(processed_docs)
                    total_failed += len(failed_docs)
                    
                    for doc in processed_docs:
                        click.echo(f"  ✅ {doc['source_file']} → {doc['filename']}")
                    
                    for doc in failed_docs:
                        click.echo(f"  ❌ {doc['source_file']}: {doc['error']}")
                        
                except Exception as e:
                    click.echo(f"  ❌ Failed to process {meeting_dir.name}: {e}")
                    total_failed += 1
            else:
                click.echo(f"  ⏭️  Skipping {meeting_dir.name} (no PDFs found)")
                
        click.echo(f"\n✅ Successfully processed {total_processed} documents total")
        if total_failed > 0:
            click.echo(f"❌ Failed to process {total_failed} documents")
        
    except Exception as e:
        click.echo(f"❌ Processing failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--meeting-dir', required=True, help='Path to meeting directory')
@click.option('--agent', default='meeting_expert', help='Agent to use for query (meeting_expert)')
@click.option('--question', required=True, help='Question to ask the agent')
@click.pass_context
def query(ctx, meeting_dir, agent, question):
    """Query an AI agent about meeting content."""
    config = ctx.obj['config']
    
    # Validate meeting directory
    meeting_path = Path(meeting_dir)
    if not meeting_path.exists():
        click.echo(f"❌ Meeting directory not found: {meeting_dir}")
        sys.exit(1)
    
    # Check for processed markdown
    markdown_dir = meeting_path / 'markdown'
    if not markdown_dir.exists():
        click.echo(f"❌ No processed markdown found in: {markdown_dir}")
        click.echo("Please run document processing first:")
        click.echo(f"  python -m src process --folder {meeting_path.name}")
        sys.exit(1)
    
    # Initialize agent
    if agent == 'meeting_expert':
        agent_instance = MeetingExpertAgent('meeting_expert', config)
    else:
        click.echo(f"❌ Unknown agent: {agent}")
        click.echo("Available agents: meeting_expert")
        sys.exit(1)
    
    click.echo(f"🤖 Querying {agent} agent...")
    click.echo(f"📁 Meeting: {meeting_path.name}")
    click.echo(f"❓ Question: {question}\n")
    
    # Process query
    query_obj = AgentQuery(
        question=question,
        meeting_dir=str(meeting_path)
    )
    
    try:
        response = agent_instance.query(query_obj)
        
        # Display response
        click.echo(f"📋 **Answer** (Confidence: {response.confidence:.2f})\n")
        click.echo(response.answer)
        
        if response.citations:
            click.echo(f"\n\n📚 **Sources** ({len(response.citations)} citations):")
            for i, citation in enumerate(response.citations, 1):
                file_name = Path(citation.file_path).name if citation.file_path else "Unknown"
                click.echo(f"  {i}. {file_name}")
        
        if response.processing_time_ms:
            click.echo(f"\n⏱️  Processing time: {response.processing_time_ms}ms")
                
    except Exception as e:
        click.echo(f"❌ Query failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--meeting-dir', required=True, help='Path to meeting directory')
@click.option('--agent', default='meeting_expert', help='Agent for interactive session')
@click.pass_context
def interactive(ctx, meeting_dir, agent):
    """Start interactive Q&A session with an agent."""
    config = ctx.obj['config']
    
    # Validate meeting directory
    meeting_path = Path(meeting_dir)
    if not meeting_path.exists():
        click.echo(f"❌ Meeting directory not found: {meeting_dir}")
        sys.exit(1)
    
    # Initialize agent
    if agent == 'meeting_expert':
        agent_instance = MeetingExpertAgent('meeting_expert', config)
    else:
        click.echo(f"❌ Unknown agent: {agent}")
        sys.exit(1)
    
    click.echo(f"🤖 Starting interactive session with {agent}")
    click.echo(f"📁 Meeting: {meeting_path.name}")
    click.echo("💡 Type 'exit' to quit, 'help' for suggestions\n")
    
    while True:
        try:
            question = click.prompt("❓ Your question")
        except (EOFError, KeyboardInterrupt):
            click.echo("\n👋 Goodbye!")
            break
        
        if question.lower() in ['exit', 'quit', 'q']:
            click.echo("👋 Goodbye!")
            break
        elif question.lower() == 'help':
            click.echo("""
💡 **Suggested Questions:**
- "What's on the agenda for this meeting?"
- "Tell me about agenda item 5B"
- "What documents are related to permits?"
- "Who needs to speak at this meeting?"
- "What are the key issues being discussed?"
- "What's the administrator update about?"
            """)
            continue
        
        # Process query
        query_obj = AgentQuery(question=question, meeting_dir=str(meeting_path))
        
        try:
            response = agent_instance.query(query_obj)
            click.echo(f"\n🤖 **Answer** (Confidence: {response.confidence:.2f})")
            click.echo(response.answer)
            
            if response.citations:
                click.echo(f"\n📚 **Sources**: {len(response.citations)} citations")
            click.echo()
            
        except Exception as e:
            click.echo(f"❌ Error: {e}\n")


@cli.command()
@click.option('--meeting-dir', required=True, help='Path to meeting directory to index')
@click.option('--force', is_flag=True, help='Force rebuild of existing index')
@click.pass_context
def index_meeting(ctx, meeting_dir, force):
    """Index a meeting directory for faster querying."""
    config = ctx.obj['config']
    
    # Validate meeting directory
    meeting_path = Path(meeting_dir)
    if not meeting_path.exists():
        click.echo(f"❌ Meeting directory not found: {meeting_dir}")
        sys.exit(1)
    
    click.echo(f"📋 Indexing meeting: {meeting_path.name}")
    
    try:
        from knowledge.meeting_corpus import MeetingCorpus
        
        # Create meeting corpus
        corpus = MeetingCorpus(str(meeting_path), config)
        
        # Index the meeting
        success = corpus.index_corpus(force_rebuild=force)
        
        if success:
            stats = corpus.get_corpus_stats()
            click.echo(f"✅ Successfully indexed meeting")
            click.echo(f"   📄 Documents: {stats['document_count']}")
            click.echo(f"   🧩 Chunks: {stats['chunk_count']}")
            click.echo(f"   💾 Index size: {stats['index_size_mb']:.1f} MB")
        else:
            click.echo(f"❌ Failed to index meeting")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Indexing failed: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def list_agents(ctx):
    """List available AI agents and their capabilities."""
    config = ctx.obj['config']
    
    click.echo("🤖 Available AI Agents:\n")
    
    # Meeting Expert Agent
    meeting_config = config.get('agents', {}).get('meeting_expert', {})
    enabled = meeting_config.get('enabled', False)
    model = meeting_config.get('model', 'unknown')
    
    status_icon = "✅" if enabled else "❌"
    click.echo(f"{status_icon} **meeting_expert** - Town Board Meeting Expert")
    click.echo(f"   Model: {model}")
    click.echo(f"   Capabilities:")
    click.echo(f"     • Agenda overviews and summaries")
    click.echo(f"     • Specific agenda item analysis")
    click.echo(f"     • Document search and retrieval")
    click.echo(f"     • Meeting participant information")
    click.echo(f"     • Procedural questions")
    click.echo()
    
    # Town Attorney Agent (future)
    attorney_config = config.get('agents', {}).get('town_attorney', {})
    attorney_enabled = attorney_config.get('enabled', False)
    attorney_status = "✅" if attorney_enabled else "🔄"
    
    click.echo(f"{attorney_status} **town_attorney** - Town Attorney Advisor")
    click.echo(f"   Status: {'Enabled' if attorney_enabled else 'Coming Soon'}")
    click.echo(f"   Capabilities:")
    click.echo(f"     • Legal analysis of agenda items")
    click.echo(f"     • Town code relevance detection")
    click.echo(f"     • Compliance assessment")
    click.echo(f"     • Risk identification")


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status and configuration."""
    config = ctx.obj['config']
    
    click.echo("🏛️  AI Town Board Prep System Status\n")
    
    # Show configuration
    click.echo("📋 Configuration:")
    click.echo(f"  Data Directory: {config['storage']['data_directory']}")
    
    # Check data directory
    data_path = Path(config['storage']['data_directory'])
    if data_path.exists():
        click.echo(f"  ✅ Data directory exists")
        
        # Count existing meetings
        meetings_path = data_path / 'meetings'
        if meetings_path.exists():
            meeting_dirs = [d for d in meetings_path.iterdir() if d.is_dir()]
            click.echo(f"  📁 Existing meetings: {len(meeting_dirs)}")
            
            # Show which meetings have PDFs
            meetings_with_pdfs = 0
            meetings_with_markdown = 0
            
            for meeting_dir in meeting_dirs:
                originals_dir = meeting_dir / 'originals'
                markdown_dir = meeting_dir / 'markdown'
                
                if originals_dir.exists() and any(originals_dir.glob('*.pdf')):
                    meetings_with_pdfs += 1
                    
                if markdown_dir.exists() and any(markdown_dir.glob('*.md')):
                    meetings_with_markdown += 1
                    
            click.echo(f"  📄 Meetings with PDFs: {meetings_with_pdfs}")
            click.echo(f"  📝 Meetings with Markdown: {meetings_with_markdown}")
            
            if meetings_with_pdfs > meetings_with_markdown:
                click.echo(f"  💡 Run 'python -m src process-all' to convert PDFs to Markdown")
    
    # Show agent status
    click.echo("\n🤖 Agent Status:")
    agents_config = config.get('agents', {})
    
    for agent_name, agent_config in agents_config.items():
        enabled = agent_config.get('enabled', False)
        model = agent_config.get('model', 'unknown')
        status_icon = "✅" if enabled else "❌"
        click.echo(f"  {status_icon} {agent_name}: {model}")
    
    if any(agent.get('enabled', False) for agent in agents_config.values()):
        click.echo(f"  💡 Try: 'python -m src query --meeting-dir data/meetings/2025-08-13 --question \"What's on the agenda?\"'")
    else:
        click.echo("  📁 Data directory will be created on first use")


@cli.command()
@click.option('--pdf-path', help='Path to town code PDF (default: data/town-code/originals/)')
@click.option('--force', is_flag=True, help='Reprocess existing files')
@click.pass_context
def ingest_town_code(ctx, pdf_path, force):
    """Process municipal code PDF into chapter-based markdown files."""
    config = ctx.obj['config']
    
    # Determine PDF path
    if pdf_path:
        pdf_file_path = Path(pdf_path)
    else:
        data_dir = Path(config['storage']['data_directory'])
        pdf_dir = data_dir / 'town-code' / 'originals'
        
        if not pdf_dir.exists():
            click.echo(f"❌ Town code directory not found: {pdf_dir}")
            click.echo("Please place the town code PDF in the expected location:")
            click.echo(f"  {pdf_dir}/")
            sys.exit(1)
        
        # Find PDF files in directory
        pdf_files = list(pdf_dir.glob('*.pdf'))
        if not pdf_files:
            click.echo(f"❌ No PDF files found in: {pdf_dir}")
            sys.exit(1)
        elif len(pdf_files) > 1:
            click.echo(f"❌ Multiple PDF files found. Please specify which one to process:")
            for pdf in pdf_files:
                click.echo(f"  📄 {pdf.name}")
            click.echo(f"Use --pdf-path to specify the file")
            sys.exit(1)
        else:
            pdf_file_path = pdf_files[0]
    
    if not pdf_file_path.exists():
        click.echo(f"❌ PDF file not found: {pdf_file_path}")
        sys.exit(1)
    
    # Setup output directory
    data_dir = Path(config['storage']['data_directory'])
    output_dir = data_dir / 'town-code' / 'markdown'
    
    click.echo(f"🏛️  Processing Municipal Code: {pdf_file_path.name}")
    click.echo(f"📂 Output directory: {output_dir}")
    
    # Check if already processed
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        click.echo("⚠️  Town code already processed. Use --force to reprocess.")
        sys.exit(1)
    
    try:
        processor = TownCodeProcessor(config)
        result = processor.process(pdf_file_path, output_dir)
        
        click.echo(f"\n✅ Successfully processed municipal code!")
        click.echo(f"📊 Processing Summary:")
        click.echo(f"  📄 Total pages: {result['analysis'].page_count}")
        click.echo(f"  📚 Total chapters: {result['analysis'].metadata.get('total_chapters', 'N/A')}")
        click.echo(f"  ✅ Successful chapters: {len([c for c in result['processed_chapters'] if c.get('filename')])}")
        click.echo(f"  ❌ Failed chapters: {len([c for c in result['processed_chapters'] if not c.get('filename')])}")
        
        click.echo(f"\n📁 Output files created:")
        click.echo(f"  📄 Index: {result['output_files']['index_file']}")
        click.echo(f"  📊 Metadata: {result['output_files']['metadata_file']}")
        click.echo(f"  🔍 Search Index: {result['output_files']['search_index_file']}")
        click.echo(f"  📚 Chapters: {result['output_files']['chapters_directory']}")
        
        if result['processed_chapters']:
            click.echo(f"\n📚 Processed Chapters:")
            for chapter in result['processed_chapters'][:5]:  # Show first 5
                if chapter.get('filename'):
                    click.echo(f"  ✅ Chapter {chapter.get('chapter_number', 'N/A')}: {chapter['title'][:50]}...")
                else:
                    click.echo(f"  ❌ Failed: {chapter['title'][:50]}...")
            
            if len(result['processed_chapters']) > 5:
                click.echo(f"  ... and {len(result['processed_chapters']) - 5} more chapters")
                
    except Exception as e:
        click.echo(f"❌ Processing failed: {e}")
        import traceback
        click.echo(traceback.format_exc())
        sys.exit(1)


@cli.command()
@click.option('--meeting-dir', required=True, help='Path to meeting directory to analyze')
@click.option('--output-format', default='both', type=click.Choice(['markdown', 'json', 'both']), 
              help='Output format for analysis (default: both)')
@click.option('--force-rebuild', is_flag=True, help='Regenerate analysis even if it exists')
@click.option('--items-only', is_flag=True, help='Analyze individual items only, skip full meeting summary')
@click.pass_context
def analyze(ctx, meeting_dir, output_format, force_rebuild, items_only):
    """Analyze meeting documents and generate comprehensive summaries."""
    config = ctx.obj['config']
    
    # Convert relative path to absolute
    meeting_path = Path(meeting_dir)
    if not meeting_path.is_absolute():
        meeting_path = Path.cwd() / meeting_path
    
    if not meeting_path.exists():
        click.echo(f"❌ Meeting directory not found: {meeting_path}")
        sys.exit(1)
    
    # Check for processed markdown
    markdown_dir = meeting_path / 'markdown'
    if not markdown_dir.exists():
        click.echo(f"❌ No processed markdown found in: {markdown_dir}")
        click.echo("Please run document processing first:")
        click.echo(f"  python -m src process --folder {meeting_path.name}")
        sys.exit(1)
    
    # Create analysis directory
    analysis_dir = meeting_path / 'analysis'
    analysis_dir.mkdir(exist_ok=True)
    
    click.echo(f"🔍 Analyzing meeting: {meeting_path.name}")
    click.echo(f"📁 Analysis directory: {analysis_dir}")
    click.echo(f"📝 Output format: {output_format}\n")
    
    # Initialize analysis agent
    analysis_agent = MeetingAnalysisAgent('meeting_analysis', config)
    
    # Create analysis query
    analysis_query = AnalysisQuery(
        meeting_dir=str(meeting_path),
        output_format=output_format,
        force_rebuild=force_rebuild,
        items_only=items_only,
        analysis_depth='comprehensive'
    )
    
    try:
        # Perform analysis
        meeting_analysis = analysis_agent.analyze_meeting(analysis_query)
        
        # Save results
        _save_analysis_results(meeting_analysis, analysis_dir, output_format)
        
        # Display summary
        click.echo(f"✅ Analysis completed successfully!")
        click.echo(f"📊 Analyzed {meeting_analysis.total_items} agenda items")
        click.echo(f"📁 Results saved to: {analysis_dir}")
        
        if output_format in ['markdown', 'both']:
            click.echo(f"📄 Main summary: {analysis_dir}/meeting_summary.md")
            
        if output_format in ['json', 'both']:
            click.echo(f"📋 Structured data: {analysis_dir}/agenda_analysis.json")
            
        click.echo(f"📂 Individual analyses: {analysis_dir}/agenda_items/")
        
    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}")
        import traceback
        click.echo(traceback.format_exc())
        sys.exit(1)


def _save_analysis_results(meeting_analysis, analysis_dir: Path, output_format: str):
    """Save analysis results to files.
    
    Args:
        meeting_analysis: MeetingAnalysis object with results
        analysis_dir: Directory to save results
        output_format: Format to save ('markdown', 'json', 'both')
    """
    import json
    from datetime import datetime
    
    # Create agenda_items subdirectory
    items_dir = analysis_dir / 'agenda_items'
    items_dir.mkdir(exist_ok=True)
    
    # Save main meeting summary (markdown)
    if output_format in ['markdown', 'both']:
        summary_content = f"""# Meeting Analysis: {meeting_analysis.meeting_date}

*Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}*

## Executive Summary
{meeting_analysis.executive_summary}

## Topics Included
{meeting_analysis.topics_included}

## Decisions
{meeting_analysis.decisions}

## Other Takeaways
{meeting_analysis.other_takeaways}

---

## Meeting Overview
- **Total Agenda Items**: {meeting_analysis.total_items}
- **Processing Date**: {meeting_analysis.processing_date.strftime('%Y-%m-%d %H:%M UTC')}
- **Analysis Directory**: {meeting_analysis.meeting_dir}

## Individual Item Summaries

"""
        
        # Add brief summaries of each item
        for item in meeting_analysis.item_analyses:
            summary_content += f"### {item.item_id}: {item.item_title}\n"
            summary_content += f"**Summary**: {item.executive_summary[:200]}...\n\n"
            summary_content += f"*Full analysis: [agenda_items/item_{item.item_id.lower().replace(' ', '_')}_analysis.md](agenda_items/item_{item.item_id.lower().replace(' ', '_')}_analysis.md)*\n\n"
        
        with open(analysis_dir / 'meeting_summary.md', 'w', encoding='utf-8') as f:
            f.write(summary_content)
    
    # Save structured JSON data
    if output_format in ['json', 'both']:
        json_data = {
            'meeting_date': meeting_analysis.meeting_date,
            'meeting_dir': meeting_analysis.meeting_dir,
            'executive_summary': meeting_analysis.executive_summary,
            'topics_included': meeting_analysis.topics_included,
            'decisions': meeting_analysis.decisions,
            'other_takeaways': meeting_analysis.other_takeaways,
            'total_items': meeting_analysis.total_items,
            'processing_date': meeting_analysis.processing_date.isoformat(),
            'metadata': meeting_analysis.metadata,
            'agenda_items': []
        }
        
        for item in meeting_analysis.item_analyses:
            json_data['agenda_items'].append({
                'item_id': item.item_id,
                'item_title': item.item_title,
                'source_file': item.source_file,
                'executive_summary': item.executive_summary,
                'topics_included': item.topics_included,
                'decisions': item.decisions,
                'other_takeaways': item.other_takeaways,
                'processing_date': item.processing_date.isoformat(),
                'metadata': item.metadata
            })
        
        with open(analysis_dir / 'agenda_analysis.json', 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    # Save individual item analyses
    if output_format in ['markdown', 'both']:
        for item in meeting_analysis.item_analyses:
            item_filename = f"item_{item.item_id.lower().replace(' ', '_')}_analysis.md"
            item_content = f"""# {item.item_id}: {item.item_title}

*Analysis generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}*

**Source File**: `{item.source_file}`

---

## Executive Summary
{item.executive_summary}

## Topics Included  
{item.topics_included}

## Decisions
{item.decisions}

## Other Takeaways
{item.other_takeaways}

---

**Metadata**:
- Item ID: {item.item_id}
- Processing Date: {item.processing_date.strftime('%Y-%m-%d %H:%M UTC')}
- Source: {item.source_file}
"""
            
            with open(items_dir / item_filename, 'w', encoding='utf-8') as f:
                f.write(item_content)


if __name__ == '__main__':
    cli()
