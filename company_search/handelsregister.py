#!/usr/bin/env python3
"""
Interactive CLI script to query the German Handelsregister for exact company name matches,
without any caching. Exits when user types "quit".

All relevant code based on the original "bundesAPI/handelsregister" logic,
but simplified for an interactive environment.
"""

import mechanize
from bs4 import BeautifulSoup
import sys
import ssl
import urllib3
import time

# Configure SSL globally
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# We'll do EXACT (option 3) searches always
SCHLAGWORT_OPTIONEN_EXACT = 3

def parse_result_row(row) -> dict:
    """Parse a single result row"""
    cells = []
    for cell in row.find_all('td'):
        cells.append(cell.text.strip())
        
    if len(cells) < 6:
        return None
        
    result = {
        'court': cells[1],
        'name': cells[2],
        'state': cells[3],
        'status': cells[4],
        'documents': cells[5],
        'history': []
    }
    
    # Parse history entries
    if len(cells) > 8:
        for i in range(8, len(cells), 3):
            if i + 1 < len(cells):
                result['history'].append((cells[i], cells[i+1]))
                
    return result

def parse_search_results(html: str) -> list:
    """Parse search results HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    grid = soup.find('table', role='grid')
    if not grid:
        return []
        
    results = []
    for row in grid.find_all('tr'):
        if row.get('data-ri') is not None:
            if result := parse_result_row(row):
                results.append(result)
    return results

def print_company_info(company: dict):
    """Print company information"""
    print("\n" + "=" * 40)
    print(f"Name:   {company['name']}")
    print(f"Court:  {company['court']}")
    print(f"State:  {company['state']}")
    print(f"Status: {company['status']}")
    
    if company['history']:
        print("\nHistory:")
        print("-" * 20)
        for name, location in company['history']:
            print(f"Name:     {name}")
            print(f"Location: {location}")
            print("-" * 20)
    print("=" * 40)

class HandelsregisterInteractive:
    def __init__(self, debug: bool = False):
        """Initialize interactive Handelsregister client"""
        self.debug = debug
        self.browser = mechanize.Browser()

        if debug:
            self.browser.set_debug_http(True)
            self.browser.set_debug_responses(True)

        # Configure browser
        self.browser.set_handle_robots(False)
        self.browser.set_handle_equiv(True)
        self.browser.set_handle_gzip(True)
        self.browser.set_handle_refresh(False)
        self.browser.set_handle_redirect(True)
        self.browser.set_handle_referer(True)

        # Set headers
        self.browser.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
            ),
            ("Accept-Language", "en-GB,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Connection", "keep-alive"),
        ]

    def open_startpage(self) -> bool:
        """Open the start page with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.browser.open("https://www.handelsregister.de", timeout=30.0)
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Error: Could not connect to Handelsregister: {e}")
                    return False
                print(f"Warning: Connection attempt {attempt + 1} failed. Retrying...")
                time.sleep(2 ** attempt)
        return False

    def search_company(self, query: str) -> list:
        """Search for a company by exact name"""
        try:
            # Navigate to advanced search
            response_search = self.browser.follow_link(text="Advanced search")
            
            # Fill out search form
            self.browser.select_form(name="form")
            self.browser["form:schlagwoerter"] = query
            self.browser["form:schlagwortOptionen"] = ['3']  # Exact match

            # Submit search
            response_result = self.browser.submit()
            html = response_result.read().decode("utf-8")
            
            # Parse results
            return parse_search_results(html)

        except Exception as e:
            print(f"Error during search: {e}")
            return []

def main():
    """Interactive CLI for searching companies"""
    print("\nHandelsregister Search")
    print("=" * 50)
    print("Type 'quit' to exit")
    
    client = HandelsregisterInteractive()
    
    while True:
        # Get user input first
        query = input("\nEnter company name to search: ").strip()
        
        if query.lower() == 'quit':
            print("\nGoodbye!")
            break
            
        if not query:
            continue
        
        # Only try to connect after user enters a query
        print("\nConnecting to Handelsregister...")
        if not client.open_startpage():
            print("Failed to connect. Please try again.")
            continue
        
        print("Searching...")
        companies = client.search_company(query)
        
        if not companies:
            print("\nNo results found.")
            continue
            
        print(f"\nFound {len(companies)} results:")
        for company in companies:
            print_company_info(company)

if __name__ == "__main__":
    main()