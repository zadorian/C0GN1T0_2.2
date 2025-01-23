from datetime import datetime
from typing import Dict, Optional, List
import asyncio
from urllib.parse import urlparse
import traceback
from pathlib import Path
import sys
import json
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import from scraping directory structure
from scrapers.common_crawl import get_historic_content
from scrapers.wayback import WaybackKeywordScanner
from caching.scrape_caching import content_cache
from caching.cache_checker import cache_checker
from indexing.scraping_indexing.scraping_indexer import scraping_indexer

# Use the correct cache directory
CACHE_DIR = project_root / "cache"

class ArchivedContent:
    def __init__(self):
        self.wayback = WaybackKeywordScanner()
    
    async def get_content(self, url: str, year: Optional[str] = None, is_domain_wide: bool = False) -> Optional[Dict]:
        """Get content from archive sources"""
        try:
            url = url.strip('?')
            print(f"\nFetching archived content...")
            
            # Check cache first
            cached_content = cache_checker.check_existing_content(
                url=url,
                is_historic=True,
                year=year,
                is_single_page=not is_domain_wide
            )
            
            if cached_content:
                print("Using cached content")
                return cached_content
            
            if is_domain_wide:
                print("Performing domain-wide search...")
                
                # Get Common Crawl content first
                cc_content = await get_historic_content(url, year, is_domain_wide=True)
                if cc_content and 'pages' in cc_content:
                    print(f"Found {len(cc_content['pages'])} CommonCrawl pages...")
                    scraping_indexer.index_content(cc_content)
                
                # Get Wayback content
                wb_snapshots = await self.wayback.get_domain_snapshots(url, year)
                if wb_snapshots:
                    print(f"Found {len(wb_snapshots)} Wayback snapshots...")
                    for date_content in wb_snapshots:
                        content_cache.save_content(
                            url=url,
                            content=date_content,
                            date=date_content['metadata']['date']
                        )
                        scraping_indexer.index_content(date_content)
                
                # Return summary
                total_cc = len(cc_content['pages']) if cc_content and 'pages' in cc_content else 0
                total_wb = sum(len(snapshot['urls']) for snapshot in wb_snapshots) if wb_snapshots else 0
                
                return {
                    'summary': {
                        'common_crawl_pages': total_cc,
                        'wayback_pages': total_wb,
                        'total_pages': total_cc + total_wb
                    }
                }
                
            else:
                # For single page searches
                all_urls = []
                
                # Get Common Crawl content
                try:
                    cc_content = await get_historic_content(url, year, is_domain_wide=False)
                    if cc_content and 'pages' in cc_content:
                        print(f"Found {len(cc_content['pages'])} CommonCrawl pages...")
                        scraping_indexer.index_content(cc_content)
                        for page in cc_content['pages']:
                            page['source'] = 'commoncrawl'
                            all_urls.append(page)
                except Exception as e:
                    print(f"CommonCrawl error: {str(e)}")
                
                # Get Wayback content
                try:
                    print(f"\nSearching Wayback Machine for year: {year}")
                    wb_content = await self.wayback.get_url_snapshots(url, year)
                    if wb_content:
                        print(f"Found {len(wb_content)} Wayback snapshots...")
                        for snapshot in wb_content:
                            scraping_indexer.index_content(snapshot)
                            for url_data in snapshot.get('urls', []):
                                url_data['content'] = url_data.get('text', '')
                                url_data['source'] = 'wayback'
                                all_urls.append(url_data)
                except Exception as e:
                    print(f"Wayback error: {str(e)}")

                if all_urls:
                    for page in all_urls:
                        timestamp = page.get('timestamp', '')
                        if timestamp and len(timestamp) >= 14:
                            date = f"{timestamp[6:8]}{timestamp[4:6]}{timestamp[2:4]}"  # DDMMYY
                            content = {
                                'urls': [{
                                    'url': page['url'],
                                    'text': page.get('text', ''),
                                    'content': page.get('content', ''),
                                    'timestamp': timestamp
                                }],
                                'metadata': {
                                    'domain': urlparse(url).netloc,
                                    'date': date,
                                    'source': page['source'],
                                    'is_domain_wide': is_domain_wide
                                }
                            }
                            content_cache.save_content(url=page['url'], content=content, date=date)
                            scraping_indexer.index_content(content)
                    
                    return {
                        'summary': {
                            'total_pages': len(all_urls),
                            'dates': sorted(set(f"{p['timestamp'][6:8]}{p['timestamp'][4:6]}{p['timestamp'][2:4]}" for p in all_urls if p.get('timestamp')))
                        }
                    }

                return None

        except Exception as e:
            print(f"Error getting archived content: {str(e)}")
            traceback.print_exc()
            return None

    async def get_sitemap_urls(self, url: str) -> List[Dict]:
        """Get additional URLs from sitemap and robots.txt"""
        try:
            from urllib.robotparser import RobotFileParser
            import requests
            from bs4 import BeautifulSoup
            import xml.etree.ElementTree as ET
            
            domain = urlparse(url).netloc
            additional_urls = []
            
            # Try robots.txt first
            robots_url = f"{url}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                sitemaps = rp.site_maps()
                if sitemaps:
                    for sitemap in sitemaps:
                        resp = requests.get(sitemap)
                        if resp.ok:
                            # Parse XML sitemap
                            root = ET.fromstring(resp.content)
                            for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                                additional_urls.append({
                                    'url': url.text,
                                    'timestamp': datetime.now().strftime('%Y%m%d'),
                                    'content': ''  # Content will be fetched later
                                })
            except Exception as e:
                print(f"Error parsing robots.txt: {str(e)}")
            
            return additional_urls
            
        except Exception as e:
            print(f"Error getting sitemap URLs: {str(e)}")
            return []

# Create the controller instance
content_controller = ArchivedContent()

async def handle_command(command: str, archiver: ArchivedContent) -> str:
    """Handle archive command"""
    try:
        all_content = []
        url = None
        
        if '<-!' in command:
            # Handle backwards search
            parts = command.split('<-!')
            start_year = parts[0].strip() if len(parts) == 2 and parts[0].strip() else None
            url = parts[1].strip()
            current_year = datetime.now().year
            start_year = int(start_year) if start_year else 2000
            
            print(f"\nSearching years {current_year} back to {start_year}...")
            for year in range(current_year, start_year - 1, -1):
                content = await archiver.get_content(url=url, year=str(year), is_domain_wide=url.endswith('?'))
                if content:
                    all_content.append(content)
                    
        elif '-' in command and '!' in command:
            # Handle year range search
            parts = command.split('!')
            year_range, url = parts[0].strip(), parts[1].strip()
            start_year, end_year = map(int, year_range.split('-'))
            
            print(f"\nSearching years {start_year} through {end_year}...")
            for year in range(start_year, end_year + 1):
                content = await archiver.get_content(url=url, year=str(year), is_domain_wide=url.endswith('?'))
                if content:
                    all_content.append(content)
        else:
            # Single year search
            parts = command.split('!')
            if len(parts) != 2:
                return "Invalid command format. Use: YYYY! domain.com? or YYYY! ?webpage.com/path.html"
            year = parts[0].strip()
            url = parts[1].strip()
            content = await archiver.get_content(url=url, year=year, is_domain_wide=url.endswith('?'))
            if content:
                all_content = [content]

        if all_content:
            total_pages = sum(c.get('summary', {}).get('total_pages', 0) for c in all_content)
            return f"Retrieved {total_pages} pages for {url}"
        
        return f"No content found for {url}"
        
    except Exception as e:
        print(f"Error handling command: {str(e)}")
        traceback.print_exc()
        return f"Error: {str(e)}"

async def main():
    """Main interactive loop"""
    print("\nArchived Content Retrieval System")
    print("=" * 33)
    print("\nCommand formats:")
    print("1. Get content from specific year:")
    print("   2022! domain.com? (full domain)")
    print("   2022! ?example.com/page.html (single page)")
    print("\n2. Get content from year range:")
    print("   2020-2023! domain.com? (full domain)")
    print("   2020-2023! ?example.com/page.html (single page)")
    print("\n3. Search backwards from current year:")
    print("   <-! domain.com? (full domain)")
    print("   2020<-! domain.com? (from 2020 backwards)")
    print("\nType 'quit' to exit\n")
    
    archiver = ArchivedContent()
    
    while True:
        command = input("Enter command: ").strip()
        if command.lower() == 'quit':
            break
            
        result = await handle_command(command, archiver)
        print(f"\n{result}\n")

if __name__ == "__main__":
    asyncio.run(main()) 