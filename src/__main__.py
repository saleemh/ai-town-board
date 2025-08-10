"""AI Town Board Prep System CLI

Command-line interface for the AI Town Board Prep System.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from collectors.board_portal_collector import BoardPortalCollector


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
    """AI Town Board Prep System - Automated meeting document collection and analysis."""
    ctx.ensure_object(dict)
    
    # Setup logging
    setup_logging(log_level)
    
    # Load configuration
    ctx.obj['config'] = load_config(config)
    

@cli.command()
@click.option('--date', required=True, help='Meeting date in YYYY-MM-DD format')
@click.option('--refresh', is_flag=True, help='Re-download existing documents')
@click.pass_context
def collect(ctx, date, refresh):
    """Collect all documents for a specific meeting date."""
    config = ctx.obj['config']
    
    click.echo(f"Collecting documents for meeting date: {date}")
    if refresh:
        click.echo("Refresh mode: existing documents will be re-downloaded")
    
    async def run_collection():
        async with BoardPortalCollector(config) as collector:
            try:
                result = await collector.collect_meeting_data(date, refresh=refresh)
                
                if result['status'] == 'no_meeting':
                    click.echo(f"No meeting found for date {date}")
                elif result['status'] == 'completed':
                    click.echo(f"✅ Successfully collected {len(result['documents'])} documents")
                    
                    # Show summary of collected documents
                    for doc in result['documents']:
                        status_icon = "✅" if doc.get('download_status') == 'success' else "⚠️"
                        size = doc.get('file_size', 0)
                        size_str = f"({size:,} bytes)" if size else ""
                        click.echo(f"  {status_icon} {doc['filename']} {size_str}")
                        
                    # Show agenda items
                    if result['agenda_items']:
                        click.echo(f"\nFound {len(result['agenda_items'])} agenda items:")
                        for item in result['agenda_items']:
                            click.echo(f"  • {item['title']}")
                else:
                    click.echo(f"Collection completed with status: {result['status']}")
                    
            except Exception as e:
                click.echo(f"❌ Collection failed: {e}")
                sys.exit(1)
    
    # Run the async collection
    asyncio.run(run_collection())


@cli.command()
@click.option('--start', required=True, help='Start date in YYYY-MM-DD format')
@click.option('--end', required=True, help='End date in YYYY-MM-DD format')
@click.option('--refresh', is_flag=True, help='Re-download existing documents')
@click.pass_context
def collect_range(ctx, start, end, refresh):
    """Collect documents for a range of dates."""
    config = ctx.obj['config']
    
    click.echo(f"Collecting documents from {start} to {end}")
    if refresh:
        click.echo("Refresh mode: existing documents will be re-downloaded")
    
    async def run_collection():
        async with BoardPortalCollector(config) as collector:
            try:
                results = await collector.collect_date_range(start, end, refresh=refresh)
                
                # Show summary
                successful = sum(1 for r in results.values() if r.get('status') == 'completed')
                total = len(results)
                
                click.echo(f"\n📊 Collection Summary:")
                click.echo(f"  Total dates processed: {total}")
                click.echo(f"  Successful collections: {successful}")
                click.echo(f"  Failed collections: {total - successful}")
                
                # Show details for each date
                for date, result in results.items():
                    if result.get('status') == 'completed':
                        doc_count = len(result.get('documents', []))
                        click.echo(f"  ✅ {date}: {doc_count} documents")
                    elif result.get('status') == 'no_meeting':
                        click.echo(f"  ➖ {date}: No meeting")
                    else:
                        click.echo(f"  ❌ {date}: {result.get('error', 'Unknown error')}")
                        
            except Exception as e:
                click.echo(f"❌ Collection failed: {e}")
                sys.exit(1)
    
    # Run the async collection
    asyncio.run(run_collection())


@cli.command()
@click.pass_context
def test_auth(ctx):
    """Test authentication with the board portal."""
    config = ctx.obj['config']
    
    click.echo("Testing authentication with board portal...")
    
    async def test_authentication():
        async with BoardPortalCollector(config) as collector:
            try:
                # Try to authenticate
                await collector._ensure_authenticated()
                click.echo("✅ Authentication successful!")
                
                # Try to access a protected page
                response = await collector.client.get(f"{collector.base_url}/Agendas")
                if response.status_code == 200:
                    click.echo("✅ Successfully accessed protected page")
                else:
                    click.echo(f"⚠️  Got status code {response.status_code} when accessing protected page")
                    
            except FileNotFoundError as e:
                click.echo(f"❌ Credentials file not found: {e}")
                click.echo("Please create the credentials file and add your username/password")
            except Exception as e:
                click.echo(f"❌ Authentication failed: {e}")
                sys.exit(1)
    
    # Run the test
    asyncio.run(test_authentication())


@cli.command()
@click.pass_context
def status(ctx):
    """Show system status and configuration."""
    config = ctx.obj['config']
    
    click.echo("🏛️  AI Town Board Prep System Status\n")
    
    # Show configuration
    click.echo("📋 Configuration:")
    click.echo(f"  Board Portal URL: {config['board_portal']['base_url']}")
    click.echo(f"  Data Directory: {config['storage']['data_directory']}")
    click.echo(f"  Credentials File: {config['board_portal']['credentials_file']}")
    
    # Check if credentials file exists
    creds_path = Path(config['board_portal']['credentials_file'])
    if creds_path.exists():
        click.echo("  ✅ Credentials file found")
    else:
        click.echo("  ❌ Credentials file not found")
        
    # Check data directory
    data_path = Path(config['storage']['data_directory'])
    if data_path.exists():
        click.echo(f"  ✅ Data directory exists")
        
        # Count existing meetings
        meetings_path = data_path / 'meetings'
        if meetings_path.exists():
            meeting_dirs = [d for d in meetings_path.iterdir() if d.is_dir()]
            click.echo(f"  📁 Existing meetings: {len(meeting_dirs)}")
    else:
        click.echo("  📁 Data directory will be created on first use")


if __name__ == '__main__':
    cli()