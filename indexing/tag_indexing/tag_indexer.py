from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import json
import traceback
import sys
from whoosh import index
from whoosh.fields import Schema, TEXT, ID, STORED, DATETIME
from whoosh.writing import AsyncWriter
from whoosh.analysis import StandardAnalyzer

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class TagIndexer:
    def __init__(self, index_dir: Optional[str] = None):
        if index_dir:
            self.index_dir = Path(index_dir)
        else:
            # Default to the indexing/tag_indexing/index directory in project root
            self.index_dir = project_root / 'indexing' / 'tag_indexing' / 'index'
            
        # Create index directory if it doesn't exist
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.analyzer = StandardAnalyzer()
        
        # Initialize or get existing index
        if not index.exists_in(str(self.index_dir)):
            self._create_index()
            
        print(f"Tag indexer initialized at: {self.index_dir}")
        
    def _create_index(self):
        """Create the initial index with schema"""
        schema = Schema(
            id_=ID(stored=True, unique=True),
            name=TEXT(stored=True),
            class_=TEXT(stored=True),
            type_=TEXT(stored=True),
            variations=TEXT(stored=True),
            notes=TEXT(stored=True),
            track=ID(stored=True),
            edges=STORED,
            metadata=STORED,
            raw_data=STORED
        )
        index.create_in(str(self.index_dir), schema) 