import asyncio
import aiohttp
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse
import re
import json
import os
from typing import List, Dict, Optional
import traceback
from bs4 import BeautifulSoup
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import from caching directory
from caching.scrape_caching import content_cache
from caching.cache_checker import cache_checker

class WaybackKeywordScanner:
    def __init__(self):
        self.base_url = "https://web.archive.org/cdx/search/cdx"
        self.wayback_base = "https://web.archive.org/web"
        # Remove cache_dir since we're using cache_checker
        
    async def get_url_snapshots(self, url: str, year: Optional[str] = None) -> List[Dict]:
        """Get HTML snapshots for a URL, optionally filtered by year"""
        try:
            params = {
                'url': url,
                'output': 'json',
                'fl': 'timestamp,original,mimetype,statuscode,digest',
                'filter': ['statuscode:200', 'mimetype:text/html'],  # Only HTML content
                'collapse': 'digest'  # Remove duplicates
            }
            
            # Add year filter if specified
            if year:
                if year.endswith('<-'):  # Backwards search
                    year = year.rstrip('<-')
                    if year:  # If year specified, search from that year to present
                        params['from'] = f'{year}0101'
                elif '-' in year:  # Year range
                    start_year, end_year = year.split('-')
                    params['from'] = f'{start_year}0101'
                    params['to'] = f'{end_year}1231'
                elif year.startswith('all-'):  # All from specific year
                    year = year.split('-')[1]
                    params['from'] = f'{year}0101'
                else:  # Specific year
                    params['from'] = f'{year}0101'
                    params['to'] = f'{year}1231'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if len(data) > 1:  # Skip header row
                            snapshots = []
                            for row in data[1:]:
                                timestamp, original_url, mimetype, status, digest = row
                                
                                # Get actual content for this snapshot
                                snapshot_url = f"{self.wayback_base}/{timestamp}/{original_url}"
                                async with session.get(snapshot_url) as snapshot_response:
                                    if snapshot_response.status == 200:
                                        html = await snapshot_response.text()
                                        soup = BeautifulSoup(html, 'html.parser')
                                        text = soup.get_text(separator=' ', strip=True)
                                        
                                        # Create content in EXACT FireCrawl format
                                        snapshot_content = {
                                            'urls': [{
                                                'url': original_url,
                                                'text': text,
                                                'timestamp': timestamp
                                            }],
                                            'metadata': {
                                                'domain': urlparse(original_url).netloc,
                                                'date': timestamp[6:8] + timestamp[4:6] + timestamp[2:4],  # DDMMYY
                                                'source': 'wayback',
                                                'is_domain_wide': False
                                            }
                                        }
                                        snapshots.append(snapshot_content)
                        
                            return snapshots
                        
            return []
            
        except Exception as e:
            print(f"Error getting snapshots: {str(e)}")
            traceback.print_exc()
            return []

    async def get_domain_snapshots(self, domain: str, year: str) -> List[Dict]:
        """Get all HTML snapshots for a domain from a specific year"""
        try:
            async with aiohttp.ClientSession() as session:
                cdx_url = 'https://web.archive.org/cdx/search/cdx'
                params = {
                    'url': f"{domain}/*",  # Add wildcard to get all pages
                    'matchType': 'domain',
                    'output': 'json',
                    'fl': 'timestamp,original,mimetype,statuscode,digest',
                    'filter': ['statuscode:200', 'mimetype:text/html'],  # Only HTML content
                    'collapse': 'digest',  # Remove duplicates
                    'from': f'{year}0101',
                    'to': f'{year}1231'
                }
                
                print(f"Fetching Wayback snapshots for {domain} from {year}...")
                
                async with session.get(cdx_url, params=params) as response:
                    if response.status != 200:
                        print(f"Error: CDX API returned status {response.status}")
                        return []
                    
                    data = await response.json()
                    if not data or len(data) < 2:
                        print("No snapshots found")
                        return []
                    
                    print(f"Found {len(data) - 1} snapshots")
                    
                    # Skip header row and group by date
                    snapshots_by_date = {}
                    for row in data[1:]:
                        timestamp, original_url, mimetype, status, digest = row
                        date = f"{timestamp[6:8]}{timestamp[4:6]}{timestamp[2:4]}"  # DDMMYY
                        
                        # Get actual content for this snapshot
                        snapshot_url = f"{self.wayback_base}/{timestamp}/{original_url}"
                        try:
                            async with session.get(snapshot_url) as snapshot_response:
                                if snapshot_response.status == 200:
                                    html = await snapshot_response.text()
                                    soup = BeautifulSoup(html, 'html.parser')
                                    text = soup.get_text(separator=' ', strip=True)
                                    
                                    # Create URL entry in FireCrawl format
                                    url_entry = {
                                        'url': original_url,
                                        'text': text,
                                        'timestamp': timestamp
                                    }
                                    
                                    # Add to date group
                                    if date not in snapshots_by_date:
                                        snapshots_by_date[date] = {
                                            'urls': [],
                                            'metadata': {
                                                'domain': domain,
                                                'date': date,
                                                'source': 'wayback',
                                                'is_domain_wide': True
                                            }
                                        }
                                    snapshots_by_date[date]['urls'].append(url_entry)
                                    print(f"Retrieved content for {original_url}")
                        except Exception as e:
                            print(f"Error fetching {snapshot_url}: {str(e)}")
                            continue
                    
                    # Convert to list of snapshots
                    snapshots = list(snapshots_by_date.values())
                    print(f"Successfully retrieved content for {len(snapshots)} dates")
                    return snapshots
            
        except Exception as e:
            print(f"Error getting domain snapshots: {str(e)}")
            traceback.print_exc()
            return []

async def handle_wayback_command(command: str) -> str:
    """Handle wayback command in format: YYYY! domain.com? or YYYY! ?webpage.com/path.html"""
    try:
        # Parse command
        parts = command.split('!')
        if len(parts) != 2:
            return "Invalid format. Use: YYYY! domain.com? or YYYY! ?webpage.com/path.html"
            
        year = parts[0].strip()
        url_part = parts[1].strip()
        
        # Validate year
        if not year.isdigit() or len(year) != 4:
            return "Invalid year format. Use 4 digits (e.g., 2022)"
        
        # Determine if domain-wide or specific page
        is_domain_wide = url_part.endswith('?')
        url = url_part.strip('?')
        
        scanner = WaybackKeywordScanner()
        
        if is_domain_wide:
            # Get all snapshots for domain using get_domain_snapshots
            snapshots = await scanner.get_domain_snapshots(url, year)
            if snapshots:
                # Group snapshots by date to show summary
                snapshots_by_date = {}
                for snapshot in snapshots:
                    date = f"{snapshot['metadata']['date'][0:2]}{snapshot['metadata']['date'][2:4]}{snapshot['metadata']['date'][4:6]}"
                    if date not in snapshots_by_date:
                        snapshots_by_date[date] = []
                    snapshots_by_date[date].append(snapshot)
                
                # Show summary of what was found
                summary = [f"\nFound {len(snapshots)} total pages:"]
                for date, date_snapshots in sorted(snapshots_by_date.items()):
                    summary.append(f"- {len(date_snapshots)} pages from {date}")
                
                return "\n".join(summary)
            return f"No snapshots found for {url} in {year}"
        else:
            # Get snapshots for specific page
            snapshots = await scanner.get_url_snapshots(url, year)
            if snapshots:
                return f"Retrieved {len(snapshots)} versions of {url} from {year}"
            return f"No snapshots found for {url} in {year}"
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return f"Error: {str(e)}"

async def main():
    """Main interactive loop"""
    print("\nWayback Machine Search")
    print("=" * 33)
    print("\nCommand formats:")
    print("1. Get domain content from year:")
    print("   2022! domain.com? (full domain)")
    print("   2022! ?example.com/page.html (single page)")
    print("\nType 'quit' to exit\n")
    
    while True:
        command = input("Enter command: ").strip()
        if command.lower() == 'quit':
            break
            
        result = await handle_wayback_command(command)
        print(f"\n{result}\n")

if __name__ == "__main__":
    asyncio.run(main())