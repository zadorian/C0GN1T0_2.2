import requests
import json
from typing import Dict, List, Optional, Set, Tuple
import os
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime
import asyncio
import base64
from config import Config
import sys
from prompts import (
    get_brand_analysis_prompt,
    get_address_significance_prompt,
    get_company_relationship_prompt
)
import httpx
from companies_house import CompaniesHouseFetcher
import time

# Add the project root and AI_models to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AI_models'))

# Import the Gemini function directly from the file
import importlib.util
gemini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AI_models/gemini_flash_1_5.py')
spec = importlib.util.spec_from_file_location('gemini', gemini_path)
gemini = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gemini)
generate_with_retry = gemini.generate_with_retry

# Initialize config
config = Config()

class CompanyNetworkAnalyzer:
    def __init__(self):
        """Initialize with API keys from config"""
        self.ch_key = config.CH_API_KEY
        self.base_url = "https://api.company-information.service.gov.uk"
        self.session = requests.Session()
        auth = base64.b64encode(f"{self.ch_key}:".encode('utf-8')).decode('utf-8')
        self.session.headers.update({'Authorization': f'Basic {auth}'})
        
        # Store for all companies found
        self.companies_data: Dict[str, Dict] = {}
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
        self.requests_this_minute = 0
        self.minute_start = time.time()
        self.max_requests_per_minute = 30

    async def _make_api_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make an API request with rate limiting and retries"""
        max_retries = 3
        retry_delay = 5
        
        # Check and reset minute counter
        current_time = time.time()
        if current_time - self.minute_start >= 60:
            self.minute_start = current_time
            self.requests_this_minute = 0
        
        # Check if we're over the per-minute limit
        if self.requests_this_minute >= self.max_requests_per_minute:
            wait_time = 60 - (current_time - self.minute_start)
            if wait_time > 0:
                print(f"Rate limit approaching - waiting {wait_time:.1f} seconds...")
                await asyncio.sleep(wait_time)
                self.minute_start = time.time()
                self.requests_this_minute = 0
        
        for attempt in range(max_retries):
            # Rate limiting per-request
            now = time.time()
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
            
            try:
                response = self.session.get(url, params=params)
                self.last_request_time = time.time()
                self.requests_this_minute += 1
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        print(f"Rate limit hit, waiting {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        self.minute_start = time.time()
                        self.requests_this_minute = 0
                        continue
                    else:
                        print("Rate limit reached, skipping request")
                        return None
                else:
                    print(f"API request failed with status {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"Error making request: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return None
        
        return None

    async def search_company(self, query: str, items_per_page: int = 20) -> List[Dict]:
        """Rate-limited company search"""
        url = f"{self.base_url}/search/companies"
        params = {
            'q': query,
            'items_per_page': items_per_page,
            'start_index': 0
        }
        result = await self._make_api_request(url, params)
        return result.get('items', []) if result else []

    async def get_company_details(self, company_number: str) -> Optional[Dict]:
        """Rate-limited company details fetch"""
        url = f"{self.base_url}/company/{company_number}"
        return await self._make_api_request(url)

    async def get_company_officers(self, company_number: str) -> List[Dict]:
        """Rate-limited company officers fetch"""
        url = f"{self.base_url}/company/{company_number}/officers"
        result = await self._make_api_request(url)
        return result.get('items', []) if result else []

    async def search_by_postcode(self, postcode: str) -> List[Dict]:
        """Search companies by postcode using the Companies House API"""
        url = f"{self.base_url}/advanced-search/companies"
        params = {
            'postcode': postcode,
            'items_per_page': 50,
            'start_index': 0
        }
        result = await self._make_api_request(url, params)
        return result.get('items', []) if result else []

    async def analyze_brand(self, company_name: str) -> Optional[str]:
        """Extract the brand part of a company name"""
        prompt = get_brand_analysis_prompt(company_name)
        response = generate_with_retry(prompt)
        if not response:
            return None
        response_clean = response.strip().lower()
        if response_clean == "none" or "none" in response_clean:
            return None
        return response.strip()

    async def analyze_address_significance(self, address: str, company_count: int) -> str:
        """Determine if an address is a service address"""
        prompt = get_address_significance_prompt(address, company_count)
        response = generate_with_retry(prompt)
        return response.strip()

    def _merge_company_data(self, company_info: Dict) -> None:
        """Safely merge company info into companies_data, preserving existing data"""
        num = company_info['company_number']
        if num not in self.companies_data:
            self.companies_data[num] = company_info
            self.companies_data[num]['links'] = set()
            self.companies_data[num]['relationships'] = {
                'shared_directors': [],
                'same_address': False,
                'same_brand': False
            }
        else:
            # Merge directors
            existing_dirs = set(self.companies_data[num].get('directors', []))
            new_dirs = set(company_info.get('directors', []))
            all_dirs = list(existing_dirs.union(new_dirs))
            self.companies_data[num]['directors'] = all_dirs
            
            # Merge brand if not set
            if not self.companies_data[num].get('brand'):
                self.companies_data[num]['brand'] = company_info.get('brand')
            
            # Merge found_via
            old_via = self.companies_data[num].get('found_via', [])
            if isinstance(old_via, str):
                old_via = [old_via]
            new_via = company_info.get('found_via', [])
            if isinstance(new_via, str):
                new_via = [new_via]
            self.companies_data[num]['found_via'] = list(set(old_via + new_via))

    def _format_director_name(self, name: str) -> str:
        """Format director name for searching - if comma present, reverse the order"""
        if ',' in name:
            # Split on comma and handle any number of parts
            parts = [p.strip() for p in name.split(',')]
            # Put the first part (surname) at the end
            parts.append(parts.pop(0))
            return ' '.join(parts)
        return name

    async def gather_company_info(self, ch_company_item: Dict, found_via: str) -> Optional[Dict]:
        """Gather full company details including directors, address, and brand"""
        if not ch_company_item:
            return None
        
        company_number = ch_company_item.get('company_number')
        if not company_number:
            return None
        
        details = await self.get_company_details(company_number)
        if not details:
            return None
        
        officers = await self.get_company_officers(company_number)
        directors = [
            self._format_director_name(off['name'].strip())
            for off in officers
            if off.get('officer_role', '').lower() == 'director'
        ]
        address = details.get('registered_office_address', {})
        brand = await self.analyze_brand(ch_company_item['title'])

        return {
            'company_number': company_number,
            'name': ch_company_item['title'],
            'details': details,
            'directors': directors,
            'address': address,
            'brand': brand,
            'found_via': found_via
        }

    async def search_company_network(self, company_name: str) -> Dict:
        """Search for a company and analyze relationships"""
        print(f"\nSearching for companies matching: {company_name}")
        initial_results = await self.search_company(company_name, items_per_page=5)
        if not initial_results:
            print(f"No companies found matching: {company_name}")
            return None

        # Get target company's full details
        target = initial_results[0]
        target_info = await self.gather_company_info(target, 'target')
        if not target_info:
            print("Could not get target company details")
            return None

        self._merge_company_data(target_info)
        target_number = target_info['company_number']

        print(f"\nTarget company: {target_info['name']} ({target_number})")
        print(f"Directors: {', '.join(target_info['directors'])}")
        print(f"Address: {target_info['address'].get('address_line_1')}, {target_info['address'].get('postal_code')}")
        print(f"Brand: {target_info['brand']}")

        # Deep searches
        print("\nSearching for related companies...")

        # 1. Director search
        for director in target_info['directors']:
            print(f"\nSearching companies for director: {director}")
            director_companies = await self.search_company(director, items_per_page=20)
            for company in director_companies:
                company_info = await self.gather_company_info(company, f'director_search_{director}')
                if company_info:
                    self._merge_company_data(company_info)

        # 2. Address search - just use postcode
        if target_info['address']:
            postcode = target_info['address'].get('postal_code', '').strip()
            if postcode:
                print(f"\nSearching companies at postcode: {postcode}")
                addr_companies = await self.search_by_postcode(postcode)
                
                # Count exact matches at this address
                exact_matches = [c for c in addr_companies if 
                    c.get('registered_office_address', {}).get('address_line_1') == target_info['address'].get('address_line_1') and
                    c.get('registered_office_address', {}).get('postal_code') == postcode
                ]
                
                print(f"Found {len(exact_matches)} companies at exact address")
                
                # Process based on count
                if len(exact_matches) < 10:
                    print("Processing all companies at this address")
                    for company in addr_companies:
                        company_info = await self.gather_company_info(company, 'address_search')
                        if company_info:
                            self._merge_company_data(company_info)
                else:
                    print(f"Found {len(exact_matches)} companies at this address - only including ones with other connections")

        # 3. Brand search
        if target_info['brand']:
            print(f"\nChecking brand: {target_info['brand']}")
            brand_companies = await self.search_company(target_info['brand'], items_per_page=50)
            
            # Only process if less than 10 matches or they have other connections
            brand_matches = []
            for company in brand_companies:
                company_info = await self.gather_company_info(company, 'brand_search')
                if company_info and company_info['brand'] == target_info['brand']:
                    brand_matches.append(company_info)
            
            if len(brand_matches) < 10:
                print(f"Found {len(brand_matches)} companies with brand - processing all")
                for company_info in brand_matches:
                    self._merge_company_data(company_info)
            else:
                print(f"Found {len(brand_matches)} companies with brand - will only include those with other connections")

        # Analyze relationships between all companies
        numbers = list(self.companies_data.keys())
        for i in range(len(numbers)):
            for j in range(i + 1, len(numbers)):
                c1 = self.companies_data[numbers[i]]
                c2 = self.companies_data[numbers[j]]
                
                # Check relationships
                shared_directors = set(c1.get('directors', [])) & set(c2.get('directors', []))
                
                same_address = False
                if c1['address'] and c2['address']:
                    same_address = (
                        c1['address'].get('address_line_1') == c2['address'].get('address_line_1') and
                        c1['address'].get('postal_code') == c2['address'].get('postal_code')
                    )
                
                same_brand = False
                if c1.get('brand') and c2.get('brand'):
                    same_brand = (c1['brand'].lower() == c2['brand'].lower())
                
                # If any relationship found, update both companies
                if shared_directors or same_address or same_brand:
                    c1['links'].add(numbers[j])
                    c2['links'].add(numbers[i])
                    
                    if shared_directors:
                        c1['relationships']['shared_directors'].extend(list(shared_directors))
                        c2['relationships']['shared_directors'].extend(list(shared_directors))
                    if same_address:
                        c1['relationships']['same_address'] = True
                        c2['relationships']['same_address'] = True
                    if same_brand:
                        c1['relationships']['same_brand'] = True
                        c2['relationships']['same_brand'] = True

        # Print findings
        print("\nRELATIONSHIP ANALYSIS:")
        for number, data in self.companies_data.items():
            if number == target_number:
                continue
            if not data['links']:
                continue
                
            print(f"\n{data['name']} ({number}):")
            rels = data['relationships']
            if rels['shared_directors']:
                print(f"- Shared directors: {', '.join(set(rels['shared_directors']))}")
            if rels['same_address']:
                print(f"- Same address: {data['address'].get('address_line_1')}, {data['address'].get('postal_code')}")
            if rels['same_brand']:
                print(f"- Same brand: {data['brand']}")
            print(f"- Found via: {data['found_via']}")

        # Save results
        output_file = f"company_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert sets to lists for JSON
        save_data = {}
        for k, v in self.companies_data.items():
            v_copy = dict(v)
            v_copy['links'] = list(v_copy['links'])
            save_data[k] = v_copy
            
        with open(output_file, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"\nAnalysis complete! Results saved to {output_file}")
        return save_data

async def main():
    analyzer = CompanyNetworkAnalyzer()
    company_name = input("Enter company name to analyze: ")
    await analyzer.search_company_network(company_name)

if __name__ == "__main__":
    asyncio.run(main())