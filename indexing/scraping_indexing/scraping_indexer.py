from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
import json
import traceback
import sys

from whoosh import index
from whoosh.fields import Schema, TEXT, ID, STORED
from whoosh.writing import AsyncWriter
from whoosh.analysis import StandardAnalyzer
from urllib.parse import urlparse

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class ScrapingIndexer:
    def __init__(self, index_dir: Optional[str] = None):
        # Always use the current directory for index storage
        self.index_dir = Path(__file__).parent / 'index'
        self.index_dir.mkdir(exist_ok=True)
        self.analyzer = StandardAnalyzer()
        
        # Initialize or get existing index
        if not index.exists_in(str(self.index_dir)):
            self._create_index()
            
    def _create_index(self):
        """Create the initial index with schema"""
        schema = Schema(
            url=ID(stored=True),
            domain=ID(stored=True),
            content=TEXT(stored=True, analyzer=self.analyzer),
            raw_text=TEXT(stored=True, analyzer=self.analyzer),
            timestamp=ID(stored=True),
            title=TEXT(stored=True),
            metadata=STORED,
            entities_person=TEXT(stored=True),
            entities_company=TEXT(stored=True),
            entities_email=TEXT(stored=True),
            entities_phone=TEXT(stored=True),
            entities_location=TEXT(stored=True),
            outlinks=TEXT(stored=True),
            backlinks=TEXT(stored=True)
        )
        index.create_in(str(self.index_dir), schema)
        
    def index_content(self, content: Dict) -> bool:
        """Index content in Whoosh for search"""
        try:
            if not content:
                return False
                
            # Check for either 'urls' or 'pages' array
            items_to_index = content.get('urls', []) or content.get('pages', [])
            if not items_to_index:
                return False

            ix = index.open_dir(str(self.index_dir))
            writer = AsyncWriter(ix)

            for item in items_to_index:
                ts = item.get('timestamp', datetime.now().isoformat())
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                # Domain
                domain = urlparse(item['url']).netloc if 'url' in item else ''
                # Entities
                e = item.get('entities', content.get('entities', {}))
                # Links
                links = item.get('links', content.get('links', {}))

                writer.add_document(
                    url=item['url'],
                    domain=domain,
                    content=item.get('content', ''),
                    raw_text=item.get('raw_text', ''),
                    timestamp=ts,
                    title=item.get('title', ''),
                    metadata=json.dumps({
                        'timestamp': ts,
                        'source': content.get('source', 'website')
                    }),
                    entities_person=','.join(e.get('person', [])),
                    entities_company=','.join(e.get('company', [])),
                    entities_email=','.join(e.get('email', [])),
                    entities_phone=','.join(e.get('phone', [])),
                    entities_location=','.join(e.get('location', [])),
                    outlinks=','.join(links.get('outlinks', [])),
                    backlinks=','.join(links.get('backlinks', []))
                )

            writer.commit()
            print(f"Successfully indexed {len(items_to_index)} pages")
            return True

        except Exception as e:
            print(f"Error indexing content: {str(e)}")
            traceback.print_exc()
            return False
            
    def reindex_all_cached(self):
        """Reindex all content from the cache directory"""
        try:
            # Get cache directory relative to project root
            project_root = Path(__file__).parent.parent.parent
            cache_dir = project_root / "cache"  # lowercase
            print(f"Looking for cache at: {cache_dir}")  # Debug print
            
            if not cache_dir.exists():
                print("Cache directory not found")
                return False
                
            # Clear existing index
            if index.exists_in(str(self.index_dir)):
                for file in self.index_dir.glob('*'):
                    if file.name != 'scraping_indexer.py':  # Don't delete self
                        file.unlink()
                self._create_index()
                
            # Reindex all cached files
            for cache_file in cache_dir.glob('*.json'):
                try:
                    content = json.loads(cache_file.read_text())
                    self.index_content(content)
                except Exception as e:
                    print(f"Error indexing {cache_file.name}: {str(e)}")
                    continue
                    
            return True
            
        except Exception as e:
            print(f"Error reindexing cache: {str(e)}")
            traceback.print_exc()
            return False

# Global instance
scraping_indexer = ScrapingIndexer()