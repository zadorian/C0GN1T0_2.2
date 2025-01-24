import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

async def fetch_urls(session: aiohttp.ClientSession, domain: str) -> dict:
    """Fetch all URLs and their snapshot dates from Wayback CDX API."""
    cdx_url = "https://web.archive.org/cdx/search/cdx"
    params = {
        'url': domain,
        'matchType': 'domain',
        'output': 'json',
        'fl': 'original,timestamp',
        'collapse': 'timestamp:8'  # Daily level
    }

    try:
        async with session.get(cdx_url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if len(data) <= 1:
                    return {}

                url_dates = defaultdict(set)
                
                for row in data[1:]:
                    original_url, timestamp = row
                    
                    # Parse the URL and remove www.
                    parsed_url = urlparse(original_url)
                    domain = parsed_url.netloc.lower()
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    
                    # Get full path if it exists
                    path = parsed_url.path
                    if path and path != '/':
                        full_url = f"{domain}{path}"
                    else:
                        full_url = domain
                    
                    # Convert timestamp to formatted date with short month names
                    date_obj = datetime.strptime(timestamp[:8], '%Y%m%d')
                    formatted_date = date_obj.strftime('%-d %b %Y')  # %-d removes leading zeros
                    
                    url_dates[full_url].add(formatted_date)

                # Convert sets to sorted lists
                return {
                    url: sorted(list(dates), 
                              key=lambda x: datetime.strptime(x, '%d %b %Y'))
                    for url, dates in url_dates.items()
                }

    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return {}

async def list_unique_urls(session: aiohttp.ClientSession, domain: str) -> set:
    """Fetch and return just unique URLs for a domain."""
    cdx_url = "https://web.archive.org/cdx/search/cdx"
    params = {
        'url': domain,
        'matchType': 'domain',
        'output': 'json',
        'fl': 'original',
        'collapse': 'timestamp:8',
        'limit': 100000
    }

    try:
        async with session.get(cdx_url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if len(data) <= 1:
                    return set()

                unique_urls = set()
                for row in data[1:]:  # Skip header row
                    original_url = row[0]
                    parsed_url = urlparse(original_url)
                    domain = parsed_url.netloc.lower()
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    
                    path = parsed_url.path
                    if path and path != '/':
                        full_url = f"{domain}{path}"
                    else:
                        full_url = domain
                    
                    unique_urls.add(full_url)

                return unique_urls

    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return set()

async def main():
    domain = input("Enter domain (e.g., example.com): ").strip()
    if not domain:
        print("No domain provided!")
        return

    print(f"\nFetching URLs for {domain}...")
    print("(This might take a while depending on the size of the archive)")

    async with aiohttp.ClientSession() as session:
        try:
            results = await fetch_urls(session, domain)
            
            if not results:
                print("\nNo results found or domain not archived.")
                return

            print("\nResults:")
            print("=========")
            
            for url in sorted(results.keys()):
                dates = results[url]
                date_range = f"({dates[0]}, {dates[-1]})" if len(dates) > 1 else f"({dates[0]})"
                print(f"{url} {date_range}")
            
            print(f"\nTotal unique URLs found: {len(results)}")

        except aiohttp.ClientError as e:
            print("Error: Rate limited by archive.org. Wait 5 minutes and try again.")
            return

async def just_urls():
    """Simple function to list unique URLs for a domain."""
    domain = input("Enter domain (e.g., example.com): ").strip()
    if not domain:
        print("No domain provided!")
        return

    print(f"\nFetching unique URLs for {domain}...")
    print("(This might take a while depending on the size of the archive)")

    async with aiohttp.ClientSession() as session:
        try:
            urls = await list_unique_urls(session, domain)
            
            if not urls:
                print("\nNo results found or domain not archived.")
                return

            print("\nUnique URLs:")
            print("============")
            
            for url in sorted(urls):
                print(url)
            
            print(f"\nTotal unique URLs found: {len(urls)}")

        except aiohttp.ClientError as e:
            print("Error: Rate limited by archive.org. Wait 5 minutes and try again.")
            return

# Modify the __main__ block to allow choosing which function to run
if __name__ == "__main__":
    print("Choose operation:")
    print("1. List URLs with dates")
    print("2. List unique URLs only")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(main())
    elif choice == "2":
        asyncio.run(just_urls())
    else:
        print("Invalid choice!")