from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
import json
import traceback
import glob
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Use absolute imports
from config import config
from indexing.scraping_indexing.scraping_indexer import ScrapingIndexer

class CacheChecker:
    def __init__(self):
        # IMPORTANT: Always use project root for cache directory
        self.cache_dir = project_root / "cache"  # This ensures cache is always in root/cache
        self.SITE_INDEX_DIR = project_root / "indexing" / "scraping_indexing"
        
        # Create directories if they don't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.SITE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Cache checker initialized at: {self.cache_dir}")

    def _normalize_url(self, url: str) -> str:
        """Remove protocol, www., trailing '?' and lowercase the URL."""
        normalized = url.lower()
        normalized = normalized.replace('https://', '').replace('http://', '')
        normalized = normalized.replace('www.', '')
        normalized = normalized.rstrip('?')
        return normalized

    def check_existing_content(self, url: str, year: Optional[str] = None, is_historic: bool = False, is_single_page: bool = False) -> Optional[Dict]:
        """Check if content exists in cache. For current content, year should be None."""
        try:
            # For current content, we don't need year
            if not is_historic:
                year = None
                
            clean_url = self._normalize_url(url)
            domain = clean_url.split('/')[0]

            if is_historic and year:
                # Look for domain_*_[cw].json (typical for archived files)
                pattern = str(self.cache_dir / f"{domain}_*_[cw].json")
                matching_files = glob.glob(pattern)

                for cache_file in matching_files:
                    cached_content = json.loads(Path(cache_file).read_text())

                    # Check both 'urls' and 'pages' for a matching year
                    # (Some sources store data in 'urls', others in 'pages'.)
                    for key in ['urls', 'pages']:
                        if key not in cached_content:
                            continue

                        for page in cached_content[key]:
                            ts = page.get('timestamp', '')
                            if ts.startswith(year):  # e.g. "2022..."
                                if is_single_page:
                                    # For single page, compare exact URL
                                    if self._normalize_url(page.get('url', '')) == clean_url:
                                        return cached_content
                                else:
                                    # For domain-wide, any page from that year is enough
                                    return cached_content

            else:
                # Current (non-historic) => check domain_{today's date}_f.json
                date_str = datetime.now().strftime('%d%m%y')
                cache_file = self.cache_dir / f"{domain}_{date_str}_f.json"
                if cache_file.exists():
                    cached_content = json.loads(cache_file.read_text())

                    if not is_single_page:
                        # Domain-wide: any match is good
                        return cached_content
                    else:
                        # Single page: ensure the exact URL is cached
                        urls_found = []
                        for key in ['urls', 'pages']:
                            if key in cached_content:
                                urls_found.extend(self._normalize_url(p.get('url', '')) 
                                                  for p in cached_content[key])

                        if clean_url in urls_found:
                            return cached_content

            return None

        except Exception as e:
            print(f"Error checking cache: {str(e)}")
            traceback.print_exc()
            return None

    def cache_content(self, url: str, content: Dict, is_historic: bool, year: Optional[str] = None) -> None:
        """
        Saves new content into a cache file (domain_date_suffix.json),
        then indexes it.
        - is_historic => suffix='c' or 'archived'.
        - otherwise => suffix='f'.
        """
        try:
            clean_url = self._normalize_url(url)
            domain = clean_url.split('/')[0]

            # Get date from content's metadata if it exists, otherwise use today
            date_str = content.get('metadata', {}).get('date')
            if not date_str:
                date_str = datetime.now().strftime('%d%m%y')

            # Decide suffix based on source
            source = content.get('metadata', {}).get('source', '').lower()
            suffix = 'w' if source == 'wayback' else 'c' if source == 'commoncrawl' else 'f'

            filename = f"{domain}_{date_str}_{suffix}.json"

            # Add minimal metadata if missing
            if 'metadata' not in content:
                content['metadata'] = {
                    'domain': domain,
                    'date': date_str,
                    'source': source,
                    'is_historic': is_historic
                }
                if year:
                    content['metadata']['year'] = year

            # Save to file
            cache_file = self.cache_dir / filename
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2)

            # Index content using ScrapingIndexer instead of WebsiteContentIndexer
            indexer = ScrapingIndexer(str(self.SITE_INDEX_DIR))
            indexer.index_content(content)  # Remove domain parameter

            print(f"Cached and indexed content to {filename}")

        except Exception as e:
            print(f"Error caching content: {str(e)}")
            traceback.print_exc()

# Global instance
cache_checker = CacheChecker()