#!/usr/bin/env python3
"""
Simple runner script for the AI Town Board Prep System.
Usage: python run.py [command] [options]
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

if __name__ == '__main__':
    # Import and run the CLI
    from src.__main__ import cli
    cli()