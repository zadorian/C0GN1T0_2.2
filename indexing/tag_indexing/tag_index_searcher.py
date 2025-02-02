from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Optional
from whoosh import index
from whoosh.qparser import QueryParser, MultifieldParser
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Memory files
MEMORY_DIR = Path(__file__).parent / 'memory'
TAG_MEMORY_FILE = MEMORY_DIR / 'tag_memory.json'

# Create directories if needed
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# Initialize memory file if it doesn't exist
if not TAG_MEMORY_FILE.exists():
    TAG_MEMORY_FILE.write_text('[]')

def search_tags(query: str, fields: List[str] = None) -> List[Dict]:
    """Search the tag index across specified fields"""
    index_dir = Path(__file__).parent / 'index'
    print(f"Looking for tag index in: {index_dir}")
    
    if not index.exists_in(str(index_dir)):
        print("No tag index found! Please run indexing first.")
        return [] 