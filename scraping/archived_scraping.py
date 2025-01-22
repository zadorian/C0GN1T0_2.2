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
                
                # Get Common Crawl content first - it handles its own caching
                cc_content = await get_historic_content(url, year, is_domain_wide=True)
                
                # Get Wayback content (now grouped by date)
                wb_snapshots = await self.wayback.get_domain_snapshots(url, year)
                
                # Let caching.py handle the caching for each date's snapshots
                if wb_snapshots:
                    for date_content in wb_snapshots:
                        content_cache.save_content(
                            url=url,
                            content=date_content,
                            date=date_content['metadata']['date']
                        )
                
                # Return summary of what was found
                total_cc = len(cc_content['pages']) if cc_content and 'pages' in cc_content else 0
                total_wb = sum(len(snapshot['urls']) for snapshot in wb_snapshots) if wb_snapshots else 0
                
                print(f"\nFound {total_cc} pages from Common Crawl")
                print(f"Found {total_wb} pages from Wayback Machine")
                
                return {
                    'summary': {
                        'common_crawl_pages': total_cc,
                        'wayback_pages': total_wb,
                        'total_pages': total_cc + total_wb
                    }
                }
                
            else:
                # For single page searches, combine Common Crawl and Wayback
                all_urls = []
                current_year = datetime.now().year
                
                # Handle backwards search for single pages
                if year and '<-!' in year:
                    start_year = int(year.replace('<-!', '')) if year.replace('<-!', '').strip() else 2000
                    print(f"DEBUG: Backwards search from {current_year} to {start_year}")
                    
                    for y in range(current_year, start_year - 1, -1):
                        print(f"\nChecking year: {y}")
                        
                        try:
                            cc_content = await get_historic_content(url, str(y), is_domain_wide=False)
                            if cc_content and 'pages' in cc_content:
                                for page in cc_content['pages']:
                                    page['source'] = 'commoncrawl'
                                    all_urls.append(page)
                        except Exception as e:
                            print(f"CommonCrawl error for {y}: {str(e)}")
                        
                        try:
                            wb_content = await self.wayback.get_url_snapshots(url, str(y))
                            if wb_content:
                                for snapshot in wb_content:
                                    snapshot['source'] = 'wayback'
                                    all_urls.append(snapshot)
                        except Exception as e:
                            print(f"Wayback error for {y}: {str(e)}")
                        
                else:
                    # Regular single year search
                    try:
                        cc_content = await get_historic_content(url, year, is_domain_wide=False)
                        if cc_content and 'pages' in cc_content:
                            for page in cc_content['pages']:
                                page['source'] = 'commoncrawl'
                                all_urls.append(page)
                    except Exception as e:
                        print(f"CommonCrawl error: {str(e)}")
                        
                    try:
                        wb_content = await self.wayback.get_url_snapshots(url, year)
                        if wb_content:
                            for snapshot in wb_content:
                                snapshot['source'] = 'wayback'
                                all_urls.append(snapshot)
                    except Exception as e:
                        print(f"Wayback error: {str(e)}")

                if all_urls:
                    # Let caching.py handle all caching
                    for page in all_urls:
                        timestamp = page.get('timestamp', '')
                        if timestamp and len(timestamp) >= 14:
                            date = f"{timestamp[6:8]}{timestamp[4:6]}{timestamp[2:4]}"  # DDMMYY
                            content = {
                                'urls': [{
                                    'url': page['url'],
                                    'text': page.get('content', ''),
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
        # Parse command
        if '<-!' in command:
            parts = command.split('<-!')
            year = parts[0].strip() if len(parts) == 2 and parts[0].strip() else None
            url = parts[1].strip()
            year = f"{year}<-" if year else "<-"
        elif '!' in command:
            parts = command.split('!')
            if len(parts) != 2:
                return "Invalid command format. Use: YYYY! domain.com? or YYYY! ?webpage.com/path.html"
            year = parts[0].strip()
            url = parts[1].strip()
        else:
            return "Invalid command format. Use: YYYY! domain.com? or YYYY! ?webpage.com/path.html"

        # Determine if domain-wide search
        is_domain_wide = url.endswith('?')
        url = url.strip('?')
        
        # Get content using the main get_content method which handles both sources
        content = await archiver.get_content(
            url=url,
            year=year,
            is_domain_wide=is_domain_wide
        )
        
        if not content:
            return f"No content found for {url}"
            
        return f"Retrieved content for {url}"
        
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