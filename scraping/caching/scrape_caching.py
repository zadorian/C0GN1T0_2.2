# =====================================
# CONTENT CACHE Controller
# =====================================
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import hashlib
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

# Use absolute imports from project root
from config import config
from indexing.scraping_indexing.scraping_indexer import ScrapingIndexer

class ContentCache:
    def __init__(self):
        # IMPORTANT: Always use project root for cache directory
        self.cache_dir = project_root / "cache"
        self.SITE_INDEX_DIR = project_root / "indexing" / "scraping_indexing"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.SITE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        self.analyzer = StandardAnalyzer()

    def _get_cache_key(self, domain: str, year: Optional[str] = None) -> str:
        """Generate a unique cache key for the domain + optional year."""
        key = domain.replace('/', '_').replace(':', '_')
        if year:
            key = f"{year}_{key}"
        return hashlib.md5(key.encode()).hexdigest()

    async def get_content(self, target: str, is_historic: bool = False, is_domain_level: bool = False) -> Optional[Dict]:
        """
        Attempts to retrieve content for `target` from the cache. 
        If not found, fetches it via FireCrawl or CommonCrawl, then caches.
        """
        try:
            # If is_historic, assume format like YEAR:URL
            year = None
            clean_target = target
            if is_historic:
                year, clean_target = target.split(':', 1)

            # Check cache first
            cached_content = self.get_from_cache(clean_target, year)
            if cached_content:
                return cached_content

            # Not in cache, so fetch it:
            if is_historic:
                # Historic => Common Crawl
                from ..scrapers.common_crawl import fetch_cc_content
                content = await fetch_cc_content(clean_target, year)
            else:
                # Current => FireCrawl
                from ..scrapers.firecrawl import fetch_content
                content = await fetch_content(clean_target, is_domain_level)

            # If we got any content, store it + index
            if content:
                # Here, `date` can be the final 6 digits of the year if we want,
                # but we can also just pass the current date if that suits.
                # We'll pass year if we have it; otherwise today's date.
                date_str = datetime.now().strftime('%d%m%y')
                if year and len(year) >= 6:  
                    date_str = year[-6:]

                self.save_content(clean_target, content, date_str)
                indexer = ScrapingIndexer(str(self.SITE_INDEX_DIR))
                indexer.index_content(content, clean_target)
                return content

            return None

        except Exception as e:
            print(f"Error in get_content: {str(e)}")
            traceback.print_exc()
            return None

    def save_content(self, url: str, content: Dict, date: str) -> None:
        """
        Saves content to a single domain_date_source file 
        (unless source is 'commoncrawl' or 'archived', in which case 
         individual timestamp-based files might be created via cache_content()).
        """
        try:
            domain = self._extract_domain(url)
            source = content.get('metadata', {}).get('source', '').lower()
            # Map recognized sources to a short ID
            source_id = {
                'wayback': 'w',
                'commoncrawl': 'c',
                'firecrawl': 'f'
            }.get(source, 'x')  # fallback 'x'

            # We do a quick merge with existing if file is found
            cache_file = self.cache_dir / f"{domain}_{date}_{source_id}.json"

            if cache_file.exists():
                try:
                    existing_content = json.loads(cache_file.read_text())
                    if 'pages' in content and 'pages' in existing_content:
                        existing_urls = {p.get('url', '') for p in existing_content['pages']}
                        for p in content['pages']:
                            if p.get('url', '') not in existing_urls:
                                existing_content['pages'].append(p)
                                existing_urls.add(p['url'])
                        content = existing_content
                except json.JSONDecodeError:
                    print(f"Warning: could not read existing file {cache_file}, overwriting...")

            # Reorder so metadata is always last
            ordered_content = {}
            for key in content:
                if key != 'metadata':
                    ordered_content[key] = content[key]
            if 'metadata' in content:
                ordered_content['metadata'] = content['metadata']

            # Save
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(ordered_content, f, ensure_ascii=False, indent=4)

            print(f"Cached content for {domain} [{date}] ({source_id})")

        except Exception as e:
            print(f"Error saving to cache: {str(e)}")
            traceback.print_exc()

    def cache_content(self, domain: str, content: Dict, source: str, year: Optional[str] = None, filename: Optional[str] = None) -> None:
        """
        Main entry point for explicitly caching content. 
        - If `source` is 'commoncrawl' or 'archived', we group pages by each record's timestamp date.
        - Otherwise, we put them in a single file.
        """
        try:
            # Ensure we're using the correct cache directory
            if not self.cache_dir.exists():
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                print(f"Created cache directory at: {self.cache_dir}")

            domain = domain.strip('?').strip().lower()

            if source.lower() in ['commoncrawl', 'archived'] and 'pages' in content:
                # Group by each page's 'timestamp' => domain_DDMMYY_c.json
                pages_by_date = {}
                for page in content['pages']:
                    ts = page.get('timestamp', '')
                    if len(ts) >= 8:  
                        # typical CommonCrawl format: YYYYMMDDHHMMSS
                        # we only need DDMMYY
                        dd = ts[6:8]
                        mm = ts[4:6]
                        yy = ts[2:4]
                        archive_date = f"{dd}{mm}{yy}"
                    else:
                        # fallback to today's date if none
                        archive_date = datetime.now().strftime('%d%m%y')

                    if archive_date not in pages_by_date:
                        pages_by_date[archive_date] = []
                    pages_by_date[archive_date].append(page)

                # Write each date's pages to a separate file
                for arch_date, pages_list in pages_by_date.items():
                    cfile = self.cache_dir / f"{domain}_{arch_date}_c.json"
                    merged_content = {'pages': pages_list}

                    if cfile.exists():
                        try:
                            existing_data = json.loads(cfile.read_text())
                            if 'pages' in existing_data:
                                existing_urls = {pg.get('url', '') for pg in existing_data['pages']}
                                for pg in pages_list:
                                    if pg.get('url', '') not in existing_urls:
                                        existing_data['pages'].append(pg)
                                        existing_urls.add(pg['url'])
                            merged_content = existing_data
                        except json.JSONDecodeError:
                            print(f"Warning: could not parse {cfile}, overwriting...")

                    # Add/update metadata
                    if 'metadata' not in merged_content:
                        merged_content['metadata'] = {}
                    merged_content['metadata']['domain'] = domain
                    merged_content['metadata']['date'] = arch_date
                    merged_content['metadata']['source'] = source
                    merged_content['metadata']['total_pages'] = len(merged_content.get('pages', []))

                    # Save
                    with open(cfile, 'w') as out_f:
                        json.dump(merged_content, out_f, indent=2)
                    
                    print(f"Cached {len(pages_list)} pages for {domain} [{arch_date}] (c)")

            else:
                # Single-file approach for firecrawl, wayback, or unknown
                if not filename:
                    date = datetime.now().strftime('%d%m%y')
                    source_id = {
                        'firecrawl': 'f',
                        'wayback': 'w',
                        'commoncrawl': 'c'
                    }.get(source.lower(), 'x')
                    filename = f"{domain}_{date}_{source_id}.json"

                cfile = self.cache_dir / filename

                # Attempt to merge with existing
                if cfile.exists():
                    try:
                        existing_data = json.loads(cfile.read_text())
                        # Merge URLs if present
                        if 'urls' in content and 'urls' in existing_data:
                            existing_urls = {u.get('url', '') for u in existing_data['urls']}
                            for u in content['urls']:
                                if u.get('url', '') not in existing_urls:
                                    existing_data['urls'].append(u)
                                    existing_urls.add(u['url'])
                        # Merge pages if present
                        if 'pages' in content and 'pages' in existing_data:
                            existing_pages = {p.get('url', '') for p in existing_data['pages']}
                            for p in content['pages']:
                                if p.get('url', '') not in existing_pages:
                                    existing_data['pages'].append(p)
                                    existing_pages.add(p['url'])
                        # Combine everything except metadata
                        for key in content:
                            if key not in ['metadata', 'urls', 'pages']:
                                existing_data[key] = content[key]
                        content = existing_data

                    except json.JSONDecodeError:
                        print(f"Warning: reading existing file {filename} failed, overwriting...")

                # Ensure metadata
                if 'metadata' not in content:
                    content['metadata'] = {
                        'domain': domain,
                        'date': datetime.now().strftime('%d%m%y'),
                        'source': source,
                        'is_historic': source in ['commoncrawl', 'wayback'],
                        'is_domain_wide': False
                    }
                    if year:
                        content['metadata']['year'] = year

                with open(cfile, 'w') as out_f:
                    json.dump(content, out_f, indent=2)
                print(f"Cached content to {filename}")

        except Exception as e:
            print(f"Error caching content: {str(e)}")
            traceback.print_exc()

    def get_cached_content(self, domain: str, year: Optional[str] = None) -> Optional[Dict]:
        """Get content from cache if it exists."""
        try:
            print(f"\nDEBUG: Looking for cached content:")
            print(f"- Domain: {domain}")
            print(f"- Year: {year}")
            print(f"- Cache directory: {self.cache_dir}")
            print(f"- Cache directory exists: {self.cache_dir.exists()}")
            
            if self.cache_dir.exists():
                print("\nFiles in cache directory:")
                for f in self.cache_dir.glob('*.json'):
                    print(f"  - {f.name}")
            
            # Try to find exact file first
            if year:
                pattern = f"{domain}_{year}_*.json"
            else:
                pattern = f"{domain}_*.json"
            
            print(f"\nSearching for pattern: {pattern}")
            matches = list(self.cache_dir.glob(pattern))
            print(f"Found {len(matches)} matching files:")
            for m in matches:
                print(f"  - {m.name}")
            
            if matches:
                # Try each matching file
                for match in matches:
                    try:
                        with open(match, 'r') as f:
                            content = json.load(f)
                        # Normalize any 'pages' if needed
                        if 'pages' in content:
                            for page in content['pages']:
                                if 'url' in page:
                                    page['url'] = self._normalize_url(page['url'])
                        return content
                    except json.JSONDecodeError:
                        continue
            else:
                # No matches found with pattern, try fallback with today's date
                date_str = datetime.now().strftime('%d%m%y')
                fallback_file = self.cache_dir / f"{domain}_{date_str}.json"
                print(f"\nTrying fallback file: {fallback_file}")
                
                if fallback_file.exists():
                    try:
                        with open(fallback_file, 'r') as f:
                            content = json.load(f)
                        # Normalize any 'pages' if needed
                        if 'pages' in content:
                            for page in content['pages']:
                                if 'url' in page:
                                    page['url'] = self._normalize_url(page['url'])
                        return content
                    except json.JSONDecodeError:
                        print("Error reading fallback file")

            print("No valid cache files found")
            return None
            
        except Exception as e:
            print(f"Error getting cache: {str(e)}")
            traceback.print_exc()
            return None

    def clear_cache(self, url: Optional[str] = None) -> None:
        """
        Clears all .json cache files, or just the single file for `url` if specified.
        """
        try:
            if url:
                # Attempt domain-based match
                domain = self._extract_domain(url)
                for cf in self.cache_dir.glob(f"{domain}_*.json"):
                    cf.unlink()
                print(f"Cleared cache for domain: {domain}")
            else:
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                print("Cleared all cache")
        except Exception as e:
            print(f"Error clearing cache: {str(e)}")
            traceback.print_exc()

    def _format_whoosh_results(self, results) -> Dict:
        """
        Format Whoosh search results into a standard structure:
          { 
            "urls": [...], 
            "entities": {...}, 
            "links": {...} 
          }
        """
        content_out = {
            'urls': [],
            'entities': {
                'person': set(),
                'company': set(),
                'email': set(),
                'phone': set(),
                'location': set()
            },
            'links': {
                'outlinks': set(),
                'backlinks': set()
            }
        }

        for hit in results:
            # Add URL
            content_out['urls'].append({
                'url': hit['url'],
                'raw_text': hit.get('raw_text', ''),
                'timestamp': hit.get('timestamp', '')
            })
            # Merge any known entity fields
            for etype in ['person', 'company', 'email', 'phone', 'location']:
                field = f'entities_{etype}'
                if field in hit and hit[field]:
                    content_out['entities'][etype].update(hit[field].split(','))
            # Merge link sets
            if 'outlinks' in hit and hit['outlinks']:
                content_out['links']['outlinks'].update(hit['outlinks'].split(','))
            if 'backlinks' in hit and hit['backlinks']:
                content_out['links']['backlinks'].update(hit['backlinks'].split(','))

        # Convert sets to lists
        for etype in content_out['entities']:
            content_out['entities'][etype] = list(content_out['entities'][etype])
        content_out['links']['outlinks'] = list(content_out['links']['outlinks'])
        content_out['links']['backlinks'] = list(content_out['links']['backlinks'])
        return content_out

    def index_cached_content(self, content: Dict) -> bool:
        """Index cached content in Whoosh for search."""
        try:
            if not content or not content.get('urls'):
                return False

            # Build the schema if it doesn't exist
            if not index.exists_in(str(self.SITE_INDEX_DIR)):
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
                index.create_in(str(self.SITE_INDEX_DIR), schema)

            ix = index.open_dir(str(self.SITE_INDEX_DIR))
            writer = AsyncWriter(ix)

            for u in content['urls']:
                ts = u.get('timestamp', datetime.now().isoformat())
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                # Domain
                domain = urlparse(u['url']).netloc if 'url' in u else ''
                # Entities
                e = u.get('entities', content.get('entities', {}))
                # Links
                links = u.get('links', content.get('links', {}))

                writer.add_document(
                    url=u['url'],
                    domain=domain,
                    content=u.get('content', ''),
                    raw_text=u.get('raw_text', ''),
                    timestamp=ts,
                    title=u.get('title', ''),
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
            print(f"Successfully indexed {len(content['urls'])} pages")
            return True

        except Exception as e:
            print(f"Error indexing cached content: {str(e)}")
            traceback.print_exc()
            return False

    def _normalize_url(self, url: str) -> str:
        """Remove http://, https://, and www. from URLs and lowercase them."""
        url = url.lower()
        url = url.replace('https://', '').replace('http://', '').replace('www.', '')
        return url

    def _extract_domain(self, url: str) -> str:
        """Extract base domain from a URL or domain string."""
        if '://' in url:
            url = url.split('://', 1)[1]
        domain = url.split('/', 1)[0]
        if ':' in domain:
            domain = domain.split(':', 1)[0]
        return domain

    def _get_cache_path(self, url: str) -> Path:
        """Utility if you want a direct path for a domain_date.json file (not always used)."""
        domain = self._extract_domain(url)
        date_str = datetime.now().strftime('%d%m%y')
        return self.cache_dir / f"{domain}_{date_str}.json"

    def _list_cached_sites(self):
        """List all .json files in the cache directory (debug/inspection)."""
        print("\nCurrently cached sites:")
        all_files = list(self.cache_dir.glob("*.json"))
        if all_files:
            for f in all_files:
                print(f"- {f.name}")
        else:
            print("No cached sites found.")
        print()

# Single global instance:
content_cache = ContentCache()