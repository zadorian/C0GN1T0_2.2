import aiohttp
import asyncio
from datetime import datetime
import re
from typing import Dict, List, Optional, Set
import json
from collections import defaultdict
from Engines.publicwww import search_publicwww_for_term
from Engines.google import search_google_tld
from Engines.bing import search_bing_tld
from Engines.brave import search_brave_tld
from Engines.yandex import search_yandex  # Assuming it's renamed

# Regular expressions for analytics codes
UA_PATTERN = r'UA-\d+-\d+'
GA4_PATTERN = r'G-[A-Z0-9]{7,}'
GTM_PATTERN = r'GTM-[A-Z0-9]+'

def validate_dates(start_date: str, end_date: str) -> bool:
    """Validate that start_date is before end_date."""
    start = datetime.strptime(start_date, "%d/%m/%Y:%H:%M")
    end = datetime.strptime(end_date, "%d/%m/%Y:%H:%M")
    return start < end

def get_14_digit_timestamp(date_str: str) -> str:
    """Convert date string to 14-digit timestamp."""
    dt = datetime.strptime(date_str, "%d/%m/%Y:%H:%M")
    return dt.strftime("%Y%m%d%H%M%S")

def format_timestamp(timestamp: str) -> str:
    """Convert 14-digit timestamp to readable format."""
    try:
        dt = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d")
    except:
        return timestamp

async def fetch_snapshots(session: aiohttp.ClientSession, url: str, from_date: str, to_date: Optional[str] = None) -> List[str]:
    """Fetch list of snapshots from Wayback CDX API with retry logic."""
    cdx_url = "https://web.archive.org/cdx/search/cdx"
    params = {
        'url': url,
        'output': 'json',
        'fl': 'timestamp',
        'filter': '!statuscode:[45]..',
        'from': from_date,
        'to': to_date if to_date else '',
        'collapse': 'timestamp:8'
    }
    
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            async with session.get(cdx_url, params=params) as response:
                if response.status == 429:  # Too Many Requests
                    if attempt < max_retries - 1:
                        print(f"\nRate limited by archive.org. Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print("\nRate limit persists. Please try again later.")
                        return []
                        
                if response.status == 200:
                    data = await response.json()
                    return [row[0] for row in data[1:]] if len(data) > 1 else []
                else:
                    print(f"\nUnexpected status code: {response.status}")
                    return []
                    
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"\nError fetching snapshots: {str(e)}. Retrying...")
                await asyncio.sleep(retry_delay)
                continue
            else:
                print(f"\nFailed to fetch snapshots after {max_retries} attempts: {str(e)}")
                return []
    
    return []

async def fetch_snapshot_content(session: aiohttp.ClientSession, url: str, timestamp: str) -> str:
    """Fetch content of a specific snapshot with retry logic."""
    wb_url = f"https://web.archive.org/web/{timestamp}/{url}"
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            async with session.get(wb_url) as response:
                if response.status == 429:  # Too Many Requests
                    if attempt < max_retries - 1:
                        print(f"\nRate limited by archive.org. Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        return ""
                        
                if response.status == 200:
                    try:
                        return await response.text(encoding='utf-8')
                    except UnicodeDecodeError:
                        return await response.text(encoding='latin-1')
                else:
                    return ""
                    
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            else:
                return ""
    
    return ""

async def get_last_seen_date(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Find the most recent date a URL appears in Wayback Machine."""
    try:
        snapshots = await fetch_snapshots(session, url, "20120101000000")
        if snapshots:
            # Get the most recent snapshot
            latest = snapshots[-1]
            return datetime.strptime(latest, "%Y%m%d%H%M%S").strftime("%d %B %Y")
        return None
    except Exception:
        return None

async def search_google_async(code: str) -> Set[str]:
    """Async wrapper for Google search."""
    try:
        results = await search_google_tld(f'"{code}"', "com", 
            api_key="AIzaSyBuCDQ7tCn5WEFR_EqJHGHDyXk-LLVT8", 
            cse_id="partner-pub-2312233746874721:6063379595")
        return {result['url'] for result in results}
    except Exception as e:
        print(f"\nGoogle search error: {str(e)}")
        return set()

async def search_bing_async(code: str) -> Set[str]:
    """Async wrapper for Bing search."""
    try:
        results = await search_bing_tld(f'"{code}"', "com", 
            api_key="d9c396364fd6474eb31347750e0e7b83")
        return {result['url'] for result in results}
    except Exception as e:
        print(f"\nBing search error: {str(e)}")
        return set()

async def search_brave_async(code: str) -> Set[str]:
    """Async wrapper for Brave search."""
    try:
        results = await search_brave_tld(f'"{code}"', "com", 
            api_key="BSA-0fb6e6e4-0d2f-4c9f-9ce6-5b")
        return {result['url'] for result in results}
    except Exception as e:
        print(f"\nBrave search error: {str(e)}")
        return set()

async def search_yandex_async(code: str) -> Set[str]:
    """Async wrapper for Yandex search."""
    try:
        yandex_api_key = "pdct.1.1.20240301T125530Z.46dff848c28f67ff.6beeb23baf2b749dd33af50a46b9dfcce03ffeac"
        results = await search_yandex(f'[{code}]', yandex_api_key)
        if results and 'response' in results and 'results' in results['response']:
            return {result['url'] for result in results['response']['results']}
        return set()
    except Exception as e:
        print(f"\nYandex search error: {str(e)}")
        return set()

async def search_all_engines(code: str) -> List[str]:
    """Search all engines for a given analytics code in parallel."""
    # Run all searches concurrently
    google_urls, bing_urls, brave_urls, yandex_urls = await asyncio.gather(
        search_google_async(code),
        search_bing_async(code),
        search_brave_async(code),
        search_yandex_async(code)
    )
    
    # Combine all results
    all_urls = google_urls | bing_urls | brave_urls | yandex_urls
    return list(all_urls)

async def search_publicwww_background(session: aiohttp.ClientSession, code: str, found_urls: defaultdict) -> None:
    """Search PublicWWW and other engines for a code and display results with last seen dates."""
    try:
        # Run PublicWWW and other engine searches concurrently
        publicwww_urls, other_urls = await asyncio.gather(
            asyncio.to_thread(search_publicwww_for_term, code),
            search_all_engines(code)
        )
        
        # Combine all unique URLs
        all_urls = list(set(publicwww_urls + other_urls))
        
        if all_urls:
            print(f"\nConnected sites for {code}:")
            # Process last seen dates in parallel
            tasks = [get_last_seen_date(session, url) for url in all_urls]
            last_seen_dates = await asyncio.gather(*tasks)
            
            for url, last_seen in zip(all_urls, last_seen_dates):
                date_str = f" [{last_seen}]" if last_seen else ""
                print(f"  • {url}{date_str}")
            found_urls[code].extend(all_urls)
    except Exception as e:
        print(f"\nError in search: {str(e)}")

async def process_snapshot(session: aiohttp.ClientSession, url: str, timestamp: str, 
                         code_dates: Dict, found_urls: defaultdict, processed_count: List[int], total: int) -> None:
    """Process a single snapshot and update progress counter."""
    try:
        content = await fetch_snapshot_content(session, url, timestamp)
        if not content:
            return
            
        formatted_date = format_timestamp(timestamp)
        
        # Find codes in this snapshot
        ua_codes = set(re.findall(UA_PATTERN, content))
        ga_codes = set(re.findall(GA4_PATTERN, content))
        gtm_codes = set(re.findall(GTM_PATTERN, content))
        
        # Update findings silently unless new code found
        for code_type, codes in [('UA', ua_codes), ('GA', ga_codes), ('GTM', gtm_codes)]:
            for code in codes:
                if code not in code_dates[code_type]:
                    code_dates[code_type][code] = {'first_seen': formatted_date, 'last_seen': formatted_date}
                    print(f"\nFound {code_type}: {code} ({formatted_date})")
                    # Start PublicWWW search in background
                    asyncio.create_task(search_publicwww_background(session, code, found_urls))
                else:
                    code_dates[code_type][code]['last_seen'] = formatted_date
        
        # Update progress counter
        processed_count[0] += 1
        print(f"\rProcessing snapshots: {processed_count[0]}/{total}", end='', flush=True)
                
    except Exception as e:
        processed_count[0] += 1
        print(f"\rProcessing snapshots: {processed_count[0]}/{total}", end='', flush=True)

async def analyze_codes(session: aiohttp.ClientSession, url: str, from_date: str, to_date: Optional[str] = None) -> Dict:
    """Analyze historical and current analytics codes for a URL."""
    results = {
        'current_codes': {'UA': [], 'GA': [], 'GTM': []},
        'historical_codes': {'UA': {}, 'GA': {}, 'GTM': {}},
        'connected_sites': defaultdict(list)
    }
    
    print(f"\nAnalyzing: {url}")
    
    # Get current codes first
    current_content = await fetch_snapshot_content(session, url, "")
    current_codes = {
        'UA': set(re.findall(UA_PATTERN, current_content)),
        'GA': set(re.findall(GA4_PATTERN, current_content)),
        'GTM': set(re.findall(GTM_PATTERN, current_content))
    }
    
    # Start PublicWWW searches for current codes immediately
    for code_type, codes in current_codes.items():
        for code in codes:
            print(f"\nFound current {code_type}: {code}")
            asyncio.create_task(search_publicwww_background(session, code, results['connected_sites']))
            results['current_codes'][code_type].append(code)
    
    # Process historical data
    snapshots = await fetch_snapshots(session, url, from_date, to_date)
    if snapshots:
        processed_count = [0]  # Using list to allow modification in nested function
        total_snapshots = len(snapshots)
        print(f"\rProcessing snapshots: 0/{total_snapshots}", end='', flush=True)
        
        code_dates = {'UA': {}, 'GA': {}, 'GTM': {}}
        
        # Process snapshots in parallel
        chunk_size = 10
        for i in range(0, len(snapshots), chunk_size):
            chunk = snapshots[i:i + chunk_size]
            tasks = [
                process_snapshot(
                    session, url, timestamp, code_dates, 
                    results['connected_sites'], processed_count, total_snapshots
                )
                for timestamp in chunk
            ]
            await asyncio.gather(*tasks)
        
        print()  # New line after progress counter
        results['historical_codes'] = code_dates
        
    return results

async def check_analytics(domain: str) -> None:
    """Main handler for analytics checking command."""
    if not domain.startswith(('http://', 'https://')):
        domain = f'http://{domain}'
    
    async with aiohttp.ClientSession() as session:
        try:
            start_timestamp = get_14_digit_timestamp("01/10/2012:00:00")
            results = await analyze_codes(session, domain, start_timestamp)
            
            # Check if any codes were found
            found_codes = False
            
            # Check current codes
            for code_type in ['UA', 'GA', 'GTM']:
                if results['current_codes'][code_type]:
                    found_codes = True
                    print(f"\nCurrent {code_type} codes:")
                    for code in results['current_codes'][code_type]:
                        print(f"• {code}")
            
            # Check historical codes
            for code_type in ['UA', 'GA', 'GTM']:
                if results['historical_codes'][code_type]:
                    found_codes = True
                    print(f"\nHistorical {code_type} codes:")
                    for code, dates in results['historical_codes'][code_type].items():
                        print(f"• {code} ({dates['first_seen']} to {dates['last_seen']})")
            
            # If no codes found at all
            if not found_codes:
                print("\nNo Google Analytics codes found for this domain")
                
        except Exception as e:
            print(f"\nError analyzing {domain}: {str(e)}")

def parse_input(user_input: str) -> tuple[str, Optional[str], Optional[str]]:
    """Parse user input for domain and optional date range."""
    parts = user_input.split('!')
    domain = parts[-1].strip()
    
    if len(parts) > 1:
        date_part = parts[0].strip()
        if '-' in date_part:
            # Range format: 2022-2024
            start_year, end_year = date_part.split('-')
            start_date = f"{start_year}0101000000"
            end_date = f"{end_year}1231235959"
        else:
            # Single year format: 2022
            year = date_part
            start_date = f"{year}0101000000"
            end_date = f"{year}1231235959"
        return domain, start_date, end_date
    
    # Default: all time
    return domain, "20121001000000", None

async def main():
    # Get URLs
    urls = input("Enter URLs (space-separated): ").split()
    if not urls:
        print("No URLs provided!")
        return

    async with aiohttp.ClientSession() as session:
        try:
            for raw_url in urls:
                url, start_timestamp, end_timestamp = parse_input(raw_url)
                print(f"\n=== {url} ===")
                results = await analyze_codes(session, url, start_timestamp, end_timestamp)
                
                # Display current codes
                print("\nCurrent Codes:")
                for code_type in ['UA', 'GA', 'GTM']:
                    if results['current_codes'][code_type]:
                        for code in results['current_codes'][code_type]:
                            print(f"{code_type}: {code}")
                
                # Display historical codes
                print("\nHistorical Codes:")
                for code_type in ['UA', 'GA', 'GTM']:
                    if results['historical_codes'][code_type]:
                        for code, dates in results['historical_codes'][code_type].items():
                            print(f"{code_type}: {code} ({dates['first_seen']} to {dates['last_seen']})")

        except aiohttp.ClientError:
            print("Error: Rate limited by archive.org. Wait 5 minutes and try again.")
            return

async def handle_ga_command(command: str) -> str:
    """Handle Google Analytics command."""
    try:
        parts = command.split()
        if len(parts) < 2:
            return "Please provide a domain for GA analysis"
            
        domain = parts[1].strip()
        # Your existing GA analysis code here
        return f"Analyzing Google Analytics for {domain}..."
        
    except Exception as e:
        return f"Error in GA analysis: {str(e)}"

if __name__ == "__main__":
    asyncio.run(main())