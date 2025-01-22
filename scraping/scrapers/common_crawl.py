# =====================================
# COMMON CRAWL Controller 
# =====================================

from datetime import datetime
import requests
import json
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import gzip
from io import BytesIO
from warcio.archiveiterator import ArchiveIterator
from urllib.parse import urlparse, urlunparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import hashlib
import traceback
import sys
from pathlib import Path
import aiohttp
import io
import socket
import dns.resolver
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import directly since we added project root to path
from caching.scrape_caching import content_cache
from caching.cache_checker import cache_checker

# Configure explicit DNS servers
resolver = dns.resolver.Resolver()
resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google's DNS servers

# Add project root to path for cache
CACHE_DIR = project_root / "cache"

async def fetch_and_parse_content(result: Dict, session: aiohttp.ClientSession, year: str) -> Optional[Dict]:
    """Fetch and parse content from Common Crawl archive"""
    try:
        # Get offset and length
        offset = int(result.get('offset', '0'))
        length = int(result.get('length', '0'))
        
        # Construct the URL
        warc_url = f"https://data.commoncrawl.org/{result['filename']}"
        
        # Request only the needed bytes
        headers = {'Range': f'bytes={offset}-{offset+length-1}'}
        
        async with session.get(warc_url, headers=headers) as response:
            if response.status == 206:  # Should be 206 Partial Content
                content = await response.read()
                html = extract_html_from_warc(content)
                
                if html:
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Get domain for caching
                    domain = urlparse(result.get('url')).netloc
                    timestamp = result.get('timestamp', '')
                    
                    # Create content in EXACT FireCrawl format
                    parsed_content = {
                        'urls': [{
                            'url': result.get('url'),
                            'text': soup.get_text(separator=' ', strip=True),
                            'timestamp': result.get('timestamp', '')
                        }],
                        'metadata': {
                            'domain': urlparse(result.get('url')).netloc,
                            'date': result.get('timestamp', '')[6:8] + result.get('timestamp', '')[4:6] + result.get('timestamp', '')[2:4],  # DDMMYY
                            'source': 'commoncrawl',
                            'is_domain_wide': False
                        }
                    }
                    
                    # Use the correct cache_checker with year parameter
                    cache_checker.cache_content(
                        url=result.get('url'),
                        content=parsed_content,
                        is_historic=True,
                        year=year
                    )
                    
                    return parsed_content
            else:
                print(f"Error fetching WARC file: {response.status}")
                
        return None
        
    except Exception as e:
        print(f"Error in fetch_and_parse_content: {str(e)}")
        traceback.print_exc()
        return None

def get_index_list(year: str) -> List[str]:
    """Get list of Common Crawl indexes for a given year"""
    try:
        # Create session with retries
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Fetch index list from Common Crawl
        print("Fetching Common Crawl index list...")
        response = session.get(
            "https://index.commoncrawl.org/collinfo.json",
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"Error fetching index list: {response.status_code}")
            return []
            
        # Parse response
        indexes = response.json()
        
        # Filter indexes for the requested year
        year_indexes = []
        for idx in indexes:
            # Index IDs are in format CC-MAIN-YYYY-WW
            if f"-{year}-" in idx['id']:
                year_indexes.append(idx['id'])
                
        if not year_indexes:
            print(f"No indexes found for year {year}")
        else:
            print(f"Found {len(year_indexes)} indexes for {year}:")
            for idx in year_indexes:
                print(f"- {idx}")
                
        return sorted(year_indexes)
        
    except Exception as e:
        print(f"Error getting index list: {str(e)}")
        traceback.print_exc()
        return []

def get_keyword_context(text: str, keyword: str, context_window: int = 30) -> str:
    """
    Extracts a snippet of text around the keyword for context.
    """
    keyword = keyword.lower()
    text_lower = text.lower()
    start_idx = text_lower.find(keyword)
    
    if start_idx == -1:
        return ""
    
    start_context = max(0, start_idx - context_window)
    end_context = min(len(text), start_idx + len(keyword) + context_window)
    
    return text[start_context:end_context]

def create_session() -> requests.Session:
    """Create a requests session with retries"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def normalize_url(url: str) -> str:
    """Normalize URL by removing any existing protocol and returning clean domain/path"""
    # Remove any existing protocol
    url = url.replace('http://', '').replace('https://', '')
    return url.strip()

async def get_historic_content(url: str, year: str, is_domain_wide: bool = False) -> Optional[Dict]:
    """Get historic content from Common Crawl"""
    try:
        print(f"\nSearching Common Crawl archives for: {url}")
        print(f"Year: {year}")
        print(f"Domain-wide search: {'Yes' if is_domain_wide else 'No'}")
        
        # Get available indexes for the year
        indexes = get_available_indexes(year)
        if not indexes:
            print("No indexes found")
            return None
            
        all_pages = []
        async with aiohttp.ClientSession() as session:
            for index in indexes:
                print(f"Searching index: {index}")
                try:
                    # For domain-wide search, use domain pattern
                    search_url = url
                    if is_domain_wide:
                        if not search_url.startswith(('http://', 'https://')):
                            search_url = f"http://{url}/*"
                        else:
                            parsed = urlparse(url)
                            search_url = f"{parsed.scheme}://{parsed.netloc}/*"
                    
                    results = await search_cc_index(index, search_url)
                    if results:
                        for result in results:
                            # Pass year parameter to fetch_and_parse_content
                            content = await fetch_and_parse_content(result, session, year)
                            if content:
                                # Extract timestamp from result
                                timestamp = result.get('timestamp', '')
                                
                                # Add page data
                                all_pages.append({
                                    'url': result.get('url'),
                                    'timestamp': timestamp,
                                    'content': content.get('urls', [{}])[0].get('text', '') if content.get('urls') else '',
                                    'snapshot_url': f"https://web.archive.org/web/{timestamp}/{result.get('url')}"
                                })
                                
                        print(f"Found {len(results)} pages in index {index}")
                        
                        # For specific page search, we can break after finding content
                        if not is_domain_wide and all_pages:
                            break
                            
                except Exception as e:
                    print(f"Error querying index {index}: {str(e)}")
                    continue
        
        if all_pages:
            # Group pages by date for caching
            pages_by_date = {}
            for page in all_pages:
                timestamp = page['timestamp']
                date = f"{timestamp[6:8]}{timestamp[4:6]}{timestamp[2:4]}"  # DDMMYY
                if date not in pages_by_date:
                    pages_by_date[date] = []
                pages_by_date[date].append(page)
            
            # Cache each date's content
            for date, pages in pages_by_date.items():
                content = {
                    'pages': pages,
                    'metadata': {
                        'domain': urlparse(url).netloc,
                        'date': date,
                        'source': 'commoncrawl',
                        'is_domain_wide': is_domain_wide,
                        'total_pages': len(pages)
                    }
                }
                content_cache.save_content(url=url, content=content, date=date)
                print(f"Cached {len(pages)} pages for {url} [{date}] (c)")
            
            # Return final content object
            return {
                'pages': all_pages,
                'metadata': {
                    'url': url,
                    'year': year,
                    'source': 'commoncrawl',
                    'is_domain_wide': is_domain_wide,
                    'total_pages': len(all_pages),
                    'query_time': datetime.now().isoformat()
                }
            }
            
        return None
            
    except Exception as e:
        print(f"Error in Common Crawl search: {str(e)}")
        traceback.print_exc()
        return None

def format_date(timestamp: str) -> str:
    """Format YYYYMMDDHHMMSS to DD.MM.YYYY"""
    dt = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    return dt.strftime("%d.%m.%Y")

async def get_cc_indexes(year: Optional[str] = None) -> List[str]:
    """Get list of Common Crawl indexes, optionally filtered by year"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://index.commoncrawl.org/collinfo.json') as response:
                if response.status != 200:
                    print("Error fetching Common Crawl index list")
                    return []
                    
                indexes = await response.json()
        
        # Filter indexes for the requested year
        if year:
            year_indexes = [
                idx['id'] for idx in indexes
                if year in idx['id']
            ]
        else:
            year_indexes = [idx['id'] for idx in indexes]
        
        if year_indexes:
            print(f"Found {len(year_indexes)} indexes for {year}")
            for idx in year_indexes:
                print(f"- {idx}")
                
        return year_indexes
        
    except Exception as e:
        print(f"Error getting indexes: {e}")
        traceback.print_exc()
        return []

async def query_cc_index(index: str, url: str) -> Optional[List[Dict]]:
    """Query a specific Common Crawl index for URL content"""
    try:
        query_url = f"https://index.commoncrawl.org/{index}-index?url={url}&output=json"
        print(f"Querying index {index} for URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(query_url) as response:
                if response.status != 200:
                    print(f"Error querying {index}: {response.status}")
                    return None
                
                results = []
                async for line in response.content:
                    if line:
                        try:
                            result = json.loads(line.decode('utf-8'))
                            results.append(result)
                        except json.JSONDecodeError:
                            continue
                
                if results:
                    print(f"Found {len(results)} results in {index}")
                return results
                
    except Exception as e:
        print(f"Error querying index: {str(e)}")
        traceback.print_exc()
        return None

async def fetch_content(url: str, offset: int, length: int) -> Optional[str]:
    """Fetch content from Common Crawl archive"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'Range': f'bytes={offset}-{offset+length-1}'}
            async with session.get(url, headers=headers) as response:
                if response.status == 206:  # Partial Content
                    content = await response.read()
                    return content.decode('utf-8', errors='ignore')
        return None
    except Exception as e:
        print(f"Error fetching content: {str(e)}")
        return None

async def handle_common_crawl_search(url: str, year: Optional[str] = None) -> Optional[Dict]:
    """Search Common Crawl archives for URL content"""
    try:
        all_results = []
        indexes = get_available_indexes(year or '')
        
        async with aiohttp.ClientSession() as session:
            for index in indexes:
                try:
                    results = await search_cc_index(index, url)
                    if results:
                        for result in results:
                            # Parse content
                            content = await fetch_and_parse_content(result, session, year)
                            if content:
                                # FIXED: Add the entire content to all_results, not just the URL data
                                all_results.append(content)

                except Exception as e:
                    print(f"Error querying {index}: {str(e)}")
                    continue

        if not all_results:
            return None

        # Combine all results into one content object
        combined_urls = []
        for result in all_results:
            combined_urls.extend(result['urls'])

        return {
            'urls': combined_urls,
            'metadata': {
                'domain': urlparse(url).netloc,
                'source': 'commoncrawl',
                'date': datetime.now().strftime('%d%m%y'),
                'is_domain_wide': False
            }
        }

    except Exception as e:
        print(f"Error in Common Crawl search: {str(e)}")
        traceback.print_exc()
        return None

def extract_html_from_warc(content: bytes) -> Optional[str]:
    """Extract HTML content from WARC record"""
    try:
        warc_content = BytesIO(content)
        with gzip.GzipFile(fileobj=warc_content) as stream:
            for record in ArchiveIterator(stream):
                if record.rec_type == 'response':
                    html_content = record.content_stream().read()
                    return html_content.decode('utf-8', errors='ignore')
        return None
    except Exception as e:
        print(f"Error extracting HTML from WARC: {str(e)}")
        return None

def get_available_indexes(year: str) -> List[str]:
    """Get list of available Common Crawl indexes for a given year"""
    try:
        # Get the index list
        response = requests.get('https://index.commoncrawl.org/collinfo.json')
        if response.status_code != 200:
            print("Error fetching Common Crawl index list")
            return []
            
        indexes = response.json()
        
        # Filter indexes for the requested year
        year_indexes = [
            idx['id'] for idx in indexes
            if year in idx['id']
        ]
        
        if year_indexes:
            print(f"Found {len(year_indexes)} indexes for {year}:")
            for idx in year_indexes:
                print(f"- {idx}")
                
        return year_indexes
        
    except Exception as e:
        print(f"Error getting indexes: {e}")
        return []

async def search_cc_index(index: str, search_url: str) -> Optional[List[Dict]]:
    """Search a Common Crawl index for URL content"""
    try:
        results = await query_cc_index(index, search_url)
        if not results:
            return None
            
        return results
        
    except Exception as e:
        print(f"Error searching index: {str(e)}")
        traceback.print_exc()
        return None

async def handle_cli_command(command: str):
    """Handle CLI command in format: YYYY! domain.com? or YYYY! ?webpage.com/path.html"""
    try:
        # Clean up command
        command = command.strip()
        
        # Extract year and URL parts
        parts = command.split('!')
        if len(parts) != 2:
            return "Invalid format. Use: YYYY! domain.com? or YYYY! ?webpage.com/path.html"
            
        year = parts[0].strip()
        url_part = parts[1].strip()
        
        # Validate year
        if not year.isdigit() or len(year) != 4:
            return "Invalid year format. Use 4 digits (e.g., 2022)"
            
        # Determine if domain-wide or specific page
        if url_part.endswith('?'):  # Domain-wide search
            domain = url_part.rstrip('?')
            content = await get_historic_content(domain, year, is_domain_wide=True)
        elif url_part.startswith('?'):  # Specific page
            url = url_part[1:]  # Remove the ? prefix
            content = await get_historic_content(url, year, is_domain_wide=False)
        else:
            return "Invalid URL format. Use domain.com? for domain-wide search or ?webpage.com/path.html for specific page"
            
        if content:
            # Define filename based on year
            filename = f"commoncrawl_{year}.json"
            
            # Load existing data if file exists
            existing_data = {'searches': []}
            if os.path.exists(filename):
                try:
                    with open(filename, 'r') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh
                    existing_data = {'searches': []}
            
            # Add timestamp to content metadata
            content['metadata']['saved_at'] = datetime.now().isoformat()
            
            # Append new content to existing data
            if 'searches' not in existing_data:
                existing_data['searches'] = []
            existing_data['searches'].append(content)
            
            # Save updated data
            with open(filename, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            return f"✓ Appended results to {filename} (total searches: {len(existing_data['searches'])})"
        else:
            return "No content found for the specified URL and year"
            
    except Exception as e:
        return f"Error: {str(e)}"

async def main():
    """Interactive CLI for Common Crawl searches"""
    print("\nCommon Crawl Search CLI")
    print("=" * 50)
    print("Format:")
    print("  YYYY! domain.com? - Search all pages from domain in YYYY")
    print("  YYYY! ?webpage.com/path.html - Search specific page from YYYY")
    print("\nEnter 'quit' to exit")
    print("=" * 50)
    
    while True:
        command = input("\nEnter search command: ").strip()
        if command.lower() == 'quit':
            break
            
        result = await handle_cli_command(command)
        print(f"\n{result}\n")

if __name__ == "__main__":
    asyncio.run(main())

