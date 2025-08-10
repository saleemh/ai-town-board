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
@click.option('--limit', default=20, help='Maximum number of meetings to show')
@click.option('--debug', is_flag=True, help='Show debug information about page structure')
@click.pass_context
def list_meetings(ctx, limit, debug):
    """List available meetings from the board portal."""
    config = ctx.obj['config']
    
    click.echo("🔍 Discovering available meetings...")
    
    async def run_discovery():
        async with BoardPortalCollector(config) as collector:
            try:
                if debug:
                    # Debug mode - show page structure
                    await collector._ensure_authenticated()
                    agendas_url = f"{collector.base_url}/Agendas"
                    response = await collector.client.get(agendas_url)
                    
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    click.echo(f"\n🔍 Debug: Page structure analysis")
                    click.echo(f"URL: {agendas_url}")
                    click.echo(f"Status: {response.status_code}")
                    
                    # Show all links on the page
                    links = soup.find_all('a', href=True)
                    click.echo(f"\nFound {len(links)} links on the page:")
                    
                    for i, link in enumerate(links[:50]):  # Show first 50 links
                        href = link.get('href', '')
                        text = link.get_text().strip()[:100]  # Truncate long text
                        if text:  # Only show links with text
                            click.echo(f"  {i+1:2d}. {text}")
                            click.echo(f"      → {href}")
                    
                    if len(links) > 50:
                        click.echo(f"... and {len(links) - 50} more links")
                    
                    # Look for other elements that might contain meeting data
                    click.echo(f"\n🔍 Looking for other content...")
                    
                    # Look for table rows, divs with data, etc.
                    tables = soup.find_all('table')
                    click.echo(f"Tables found: {len(tables)}")
                    
                    divs_with_data = soup.find_all('div', {'data-date': True}) + soup.find_all('div', {'data-meeting': True})
                    click.echo(f"Divs with data attributes: {len(divs_with_data)}")
                    
                    # Look for script tags that might contain meeting data
                    scripts = soup.find_all('script')
                    click.echo(f"Script tags: {len(scripts)}")
                    
                    for script in scripts:
                        if script.string and ('meeting' in script.string.lower() or 'agenda' in script.string.lower()):
                            click.echo(f"  Found script with meeting/agenda content (first 200 chars):")
                            click.echo(f"  {script.string[:200]}...")
                    
                    # Show raw HTML sample
                    click.echo(f"\n🔍 Raw HTML sample (first 1000 chars):")
                    click.echo(response.text[:1000])
                    
                    return
                
                meetings = await collector.discover_available_meetings()
                
                if not meetings:
                    click.echo("No meetings found on the board portal.")
                    click.echo("\n💡 Try running with --debug to see page structure:")
                    click.echo("   python -m src list-meetings --debug")
                    return
                    
                # Limit results
                meetings = meetings[:limit]
                
                click.echo(f"\n📅 Found {len(meetings)} meetings:\n")
                
                for i, meeting in enumerate(meetings, 1):
                    # Format date nicely
                    from datetime import datetime
                    try:
                        date_obj = datetime.strptime(meeting['date'], '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%B %d, %Y')
                    except:
                        formatted_date = meeting['date']
                    
                    # Meeting type badge
                    type_badges = {
                        'regular': '📋',
                        'special': '⚡',
                        'workshop': '🛠️',
                        'public_hearing': '🎤',
                        'budget': '💰'
                    }
                    badge = type_badges.get(meeting['type'], '📋')
                    
                    click.echo(f"{i:2d}. {badge} {formatted_date} ({meeting['type']})")
                    click.echo(f"    {meeting['title']}")
                    click.echo(f"    📋 {meeting['date']}")
                    click.echo("")
                    
                click.echo("💡 To collect documents for a specific meeting, use:")
                click.echo("   python -m src collect --date YYYY-MM-DD")
                    
            except Exception as e:
                click.echo(f"❌ Failed to discover meetings: {e}")
                sys.exit(1)
    
    # Run the async discovery
    asyncio.run(run_discovery())


@cli.command()
@click.option('--date', required=True, help='Meeting date in YYYY-MM-DD format')
@click.pass_context
def inspect_meeting(ctx, date):
    """Open meeting page in browser and show manual document collection guide."""
    config = ctx.obj['config']
    
    meeting_url = f"{config['board_portal']['base_url']}/Agendas?date={date}"
    
    click.echo(f"🔍 Manual Document Collection Guide for {date}")
    click.echo(f"════════════════════════════════════════════════")
    click.echo(f"")
    click.echo(f"1. 🌐 Open this URL in your browser:")
    click.echo(f"   {meeting_url}")
    click.echo(f"")
    click.echo(f"2. 📋 You should see buttons like 'Agenda', 'Minutes', 'Packet'")
    click.echo(f"")
    click.echo(f"3. 🔧 For each document button:")
    click.echo(f"   - Right-click the button → 'Inspect Element'")
    click.echo(f"   - Look for href, data-url, or onclick attributes")
    click.echo(f"   - Note the actual download URL")
    click.echo(f"")
    click.echo(f"4. 📝 Create a file: manual_documents_{date}.json with:")
    click.echo(f'   [')
    click.echo(f'     {{')
    click.echo(f'       "filename": "agenda.pdf",')
    click.echo(f'       "download_url": "https://northcastleny.boardportal.civicclerk.com/ACTUAL_AGENDA_URL",')
    click.echo(f'       "document_type": "agenda"')
    click.echo(f'     }},')
    click.echo(f'     {{')
    click.echo(f'       "filename": "minutes.pdf",')
    click.echo(f'       "download_url": "https://northcastleny.boardportal.civicclerk.com/ACTUAL_MINUTES_URL",')
    click.echo(f'       "document_type": "minutes"')
    click.echo(f'     }},')
    click.echo(f'     {{')
    click.echo(f'       "filename": "packet.pdf",')
    click.echo(f'       "download_url": "https://northcastleny.boardportal.civicclerk.com/ACTUAL_PACKET_URL",')
    click.echo(f'       "document_type": "packet"')
    click.echo(f'     }}')
    click.echo(f'   ]')
    click.echo(f"")
    click.echo(f"5. 🚀 Run: python -m src collect-manual --date {date}")
    click.echo(f"")
    click.echo(f"💡 This will help us reverse-engineer the correct URL patterns!")
    
    # Try to open in browser (works on macOS)
    try:
        import subprocess
        subprocess.run(['open', meeting_url], check=False)
        click.echo(f"✅ Opened in browser automatically")
    except:
        click.echo(f"ℹ️  Please manually open the URL above")

@cli.command() 
@click.option('--date', required=True, help='Meeting date in YYYY-MM-DD format')
@click.pass_context
def collect_manual(ctx, date):
    """Collect documents using manually specified URLs."""
    config = ctx.obj['config']
    
    manual_file = f"manual_documents_{date}.json"
    
    if not Path(manual_file).exists():
        click.echo(f"❌ Manual document file not found: {manual_file}")
        click.echo(f"Run: python -m src inspect-meeting --date {date}")
        return
    
    click.echo(f"📄 Collecting documents using manual URLs from {manual_file}")
    
    async def collect_manually():
        async with BoardPortalCollector(config) as collector:
            try:
                # Load manual document URLs
                import json
                with open(manual_file, 'r') as f:
                    documents = json.load(f)
                
                # Ensure authenticated
                await collector._ensure_authenticated()
                
                # Setup directory
                meeting_dir = collector._setup_meeting_directory(date)
                
                # Download each document
                results = []
                for doc in documents:
                    click.echo(f"📥 Downloading {doc['filename']}...")
                    
                    response = await collector.client.get(doc['download_url'])
                    if response.status_code == 200:
                        # Check if it's actually a PDF
                        if response.content.startswith(b'%PDF'):
                            file_path = meeting_dir / 'originals' / doc['filename']
                            with open(file_path, 'wb') as f:
                                f.write(response.content)
                            
                            click.echo(f"  ✅ {doc['filename']} ({len(response.content)} bytes)")
                            doc['download_status'] = 'success'
                            doc['file_path'] = str(file_path)
                            doc['file_size'] = len(response.content)
                        else:
                            click.echo(f"  ❌ {doc['filename']} - Not a valid PDF (got HTML)")
                            doc['download_status'] = 'invalid_content'
                    else:
                        click.echo(f"  ❌ {doc['filename']} - HTTP {response.status_code}")
                        doc['download_status'] = 'http_error'
                        doc['http_status'] = response.status_code
                    
                    results.append(doc)
                
                # Save metadata
                metadata = {
                    'meeting_date': date,
                    'meeting_type': 'regular',
                    'collection_timestamp': datetime.utcnow().isoformat() + 'Z',
                    'board_portal_url': f"{config['board_portal']['base_url']}/Agendas?date={date}",
                    'documents': results,
                    'collection_method': 'manual_urls',
                    'status': 'completed'
                }
                
                metadata_file = meeting_dir / 'metadata.json'
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                successful = sum(1 for d in results if d.get('download_status') == 'success')
                click.echo(f"")
                click.echo(f"✅ Manual collection complete: {successful}/{len(documents)} documents successful")
                
                if successful > 0:
                    click.echo(f"📁 Files saved to: {meeting_dir}")
                    click.echo(f"")
                    click.echo(f"🔧 Next: Share these working URLs so we can fix the automatic detection!")
                
            except Exception as e:
                click.echo(f"❌ Manual collection failed: {e}")
                
    from datetime import datetime
    asyncio.run(collect_manually())


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