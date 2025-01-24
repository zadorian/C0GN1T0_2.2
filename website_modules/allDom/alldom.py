import os
import sys
from urllib.parse import urlparse
from .firecrawl_alldom import InternalURLTracker, discover_internal_urls
from .bing_alldom import fetch_bing_results
from .google_alldom import fetch_google_results
from .sublist3r_alldom import sublist3r
from .wayback_list import list_unique_urls
from .url_categorizer import categorize_urls
import logging
import time
import asyncio
import aiohttp
import argparse
from typing import List, Dict
import json

# Set up logging
logging.basicConfig(level=logging.ERROR)  # Only show errors

class URLCollector:
    def __init__(self):
        self.unique_urls = set()

    def add_urls(self, urls):
        """Add URLs to the collection"""
        for url in urls:
            if not url:  # Skip only empty URLs
                continue
                
            # Clean the URL but keep all file types
            cleaned_url = url.replace('https://', '').replace('http://', '').replace('www.', '')
            cleaned_url = cleaned_url.rstrip('/')  # Remove trailing slash only
            
            if cleaned_url:
                self.unique_urls.add(cleaned_url)

def clean_url(url):
    """Clean URL by removing http://, https://, www. and leading/trailing slashes"""
    return url.replace('https://', '').replace('http://', '').replace('www.', '').strip('/')

async def fetch_wayback_urls(domain, seen_urls):
    try:
        async with aiohttp.ClientSession() as session:
            urls = await list_unique_urls(session, domain)
            for url in urls:
                cleaned = clean_url(url)
                if cleaned and cleaned not in seen_urls:
                    seen_urls.add(cleaned)
                    print(cleaned)
                    await asyncio.sleep(1)
    except Exception:
        pass

async def collect_all_urls(domain):
    seen_urls = set()
    
    # Create tasks for all sources
    tasks = [
        fetch_bing_urls(domain, seen_urls),
        fetch_google_urls(domain, seen_urls),
        fetch_wayback_urls(domain, seen_urls),
        fetch_firecrawl_urls(domain, seen_urls),
        fetch_sublist3r_urls(domain, seen_urls)
    ]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)
    return seen_urls

async def fetch_bing_urls(domain, seen_urls):
    try:
        results = fetch_bing_results(domain)
        for url in results:
            cleaned = clean_url(url)
            if cleaned and cleaned not in seen_urls:
                seen_urls.add(cleaned)
                print(cleaned)
    except Exception:
        pass

async def fetch_google_urls(domain, seen_urls):
    try:
        results = fetch_google_results(domain)
        for url in results:
            cleaned = clean_url(url)
            if cleaned and cleaned not in seen_urls:
                seen_urls.add(cleaned)
                print(cleaned)
    except Exception:
        pass

async def fetch_firecrawl_urls(domain, seen_urls):
    try:
        tracker = InternalURLTracker(urlparse(domain).hostname)
        results = discover_internal_urls(domain, tracker)
        for url in results:
            cleaned = clean_url(url)
            if cleaned and cleaned not in seen_urls:
                seen_urls.add(cleaned)
                print(cleaned)
    except Exception:
        pass

async def fetch_sublist3r_urls(domain, seen_urls):
    try:
        clean_domain = clean_url(domain)
        subdomains = sublist3r.main(
            clean_domain,
            threads=40,
            savefile=None,
            ports=None,
            silent=True,
            verbose=False,
            enable_bruteforce=False,
            engines="ssl,virustotal,threatcrowd,netcraft,google,bing,baidu"
        ) or []
        
        for subdomain in subdomains:
            cleaned = clean_url(subdomain)
            if cleaned and cleaned not in seen_urls:
                seen_urls.add(cleaned)
                print(cleaned)
    except Exception:
        pass

async def main():
    parser = argparse.ArgumentParser(description='Domain URL Discovery Tool')
    parser.add_argument('--domain', type=str, help='Domain to analyze')
    args = parser.parse_args()
    
    domain = args.domain
    if not domain:
        print("\nEnter the domain to analyze (e.g., example.com):")
        domain = input().strip()
    
    if not domain.startswith(('http://', 'https://')):
        domain = 'https://' + domain

    print(f"\nCollecting URLs for {domain}...")
    urls = await collect_all_urls(domain)
    
    # Categorize and display results
    print("\nCategorized Results:")
    print("=" * 50)
    
    categorized = categorize_urls(urls)
    
    for category, name in {
        'html': 'HTML Pages',
        'core': 'Core Files',
        'images': 'Images',
        'favicons': 'Favicons',
        'subdomains': 'Subdomains',
        'other': 'Other URLs'
    }.items():
        url_list = categorized[category]
        if url_list:
            print(f"\n{name} ({len(url_list)} URLs):")
            for url in sorted(url_list):
                print(f"  {url}")
    
    print(f"\nTotal unique URLs found: {len(urls)}")

if __name__ == "__main__":
    asyncio.run(main())

