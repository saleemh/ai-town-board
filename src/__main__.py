"""AI Town Board Prep System CLI

Command-line interface for processing meeting documents with AI analysis.
"""

import logging
import sys
from pathlib import Path

import click
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from processors.document_processor import DocumentProcessor


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
@click.option('--date', required=True, help='Meeting date in YYYY-MM-DD format')
@click.option('--force', is_flag=True, help='Reprocess existing markdown files')
@click.pass_context
def process(ctx, date, force):
    """Process meeting documents to markdown format using Docling."""
    config = ctx.obj['config']
    
    click.echo(f"Processing documents for meeting date: {date}")
    
    # Check if meeting directory exists
    data_dir = Path(config['storage']['data_directory'])
    meeting_dir = data_dir / 'meetings' / f"{date}-regular"
    
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
        processor = DocumentProcessor(config)
        results = processor.process_meeting_documents(meeting_dir, force=force)
        
        click.echo(f"✅ Successfully processed {len(results)} documents")
        for result in results:
            click.echo(f"  ✅ {result['filename']} → {result['markdown_file']}")
            
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
        
    # Find all meeting directories
    meeting_dirs = [d for d in meetings_path.iterdir() if d.is_dir() and '-' in d.name]
    
    if not meeting_dirs:
        click.echo(f"❌ No meeting directories found in: {meetings_path}")
        click.echo("Expected format: YYYY-MM-DD-regular/")
        sys.exit(1)
        
    click.echo(f"Found {len(meeting_dirs)} meeting directories:")
    for meeting_dir in sorted(meeting_dirs):
        click.echo(f"  📁 {meeting_dir.name}")
        
    try:
        processor = DocumentProcessor(config)
        total_processed = 0
        
        for meeting_dir in sorted(meeting_dirs):
            originals_dir = meeting_dir / 'originals'
            if originals_dir.exists() and any(originals_dir.glob('*.pdf')):
                click.echo(f"\n📋 Processing {meeting_dir.name}...")
                results = processor.process_meeting_documents(meeting_dir, force=force)
                total_processed += len(results)
                
                for result in results:
                    click.echo(f"  ✅ {result['filename']} → {result['markdown_file']}")
            else:
                click.echo(f"  ⏭️  Skipping {meeting_dir.name} (no PDFs found)")
                
        click.echo(f"\n✅ Successfully processed {total_processed} documents total")
        
    except Exception as e:
        click.echo(f"❌ Processing failed: {e}")
        sys.exit(1)


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
    else:
        click.echo("  📁 Data directory will be created on first use")


if __name__ == '__main__':
    cli()
