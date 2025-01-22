from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import traceback
from urllib.parse import urlparse
import asyncio
import json
import os
import sys

# Add project root and current directory to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "scraping"))

from config import config
from scrapers.firecrawl import get_content
from caching.scrape_caching import content_cache
from caching.cache_checker import cache_checker
from indexing.scraping_indexing.scraping_indexer import scraping_indexer

CACHE_DIR = project_root / "cache"

class ContentController:
    async def get_content(self, url: str) -> Optional[Dict]:
        """Get CURRENT content for URL, using cache if available and fetching new content"""
        try:
            # Process URL format - ONLY current content
            is_domain_wide = url.endswith('?')
            is_single_page = url.startswith('?')
            clean_url = url
            
            print(f"\nDEBUG: Initial URL format check:")
            print(f"- URL: {url}")
            print(f"- Domain-wide: {is_domain_wide}")
            print(f"- Single page: {is_single_page}")
            
            # Clean up URL for single page requests
            if is_single_page:
                clean_url = clean_url[1:]  # Remove leading ? for single pages
                
            # Check cache - pass None for year since this is current content
            cached_content = cache_checker.check_existing_content(
                url=clean_url,
                year=None,  # Added year parameter as None for current content
                is_historic=False,
                is_single_page=is_single_page
            )
            
            if cached_content:
                print("DEBUG: Using cached content")
                return cached_content
                
            # If not in cache, get from FireCrawl
            print(f"DEBUG: No cache found, fetching fresh content...")
            content = await get_content(clean_url, is_domain_wide=is_domain_wide)
            
            if content:
                # Cache the content
                cache_checker.cache_content(
                    url=clean_url,
                    content=content,
                    is_historic=False  # Never historic in current_scraping
                )
                return content
                
            return None
            
        except Exception as e:
            print(f"Error in ContentController.get_content: {str(e)}")
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
content_controller = ContentController() 

async def main():
    """Interactive CLI for current content scraping"""
    print("\nC0GN1T0 Current Content Scraper")
    print("=" * 50)
    print("\nURL formats:")
    print("- Normal URL:           example.com/page.html")
    print("- Single page:          ?example.com/page.html")
    print("- Full domain:          example.com?")
    
    while True:
        try:
            url = input("\nEnter URL (or 'q' to quit): ").strip()
            
            if url.lower() == 'q':
                break
                
            if not url:
                continue
                
            # Check for historic formats and reject them
            if '<-!' in url or '!' in url:
                print("\nError: This scraper is for current content only.")
                print("For historic content, please use archived_scraping.py")
                continue
                
            print(f"\nProcessing: {url}")
            print("=" * 50)
            
            content = await content_controller.get_content(url)
            
            if content:
                print("\nContent retrieved successfully!")
                print(f"Pages found: {len(content.get('pages', []))}")
                print("\nContent has been cached and indexed.")
            else:
                print("\nNo content retrieved")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {str(e)}")
            traceback.print_exc()
            
    print("\nGoodbye!")

if __name__ == "__main__":
    asyncio.run(main()) 