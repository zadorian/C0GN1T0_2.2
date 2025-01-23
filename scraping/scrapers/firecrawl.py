# =====================================
# FIRECRAWL Controller
# =====================================

import aiohttp
import asyncio
from typing import Dict, Optional, List
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
from config import config
from datetime import datetime
import traceback

async def get_content(url: str, is_domain_wide: bool = False) -> Optional[Dict]:
    """Get content from FireCrawl API"""
    try:
        # Clean up domain first
        domain = url.strip('?')
        if '://' in domain:
            domain = domain.split('://', 1)[1]
        domain = domain.split('/', 1)[0]  # Remove any paths
        
        # Debug: Check API key
        print(f"\nDEBUG: FireCrawl API Key length: {len(config.FIRECRAWL_API_KEY) if config.FIRECRAWL_API_KEY else 0}")
        print(f"DEBUG: FireCrawl Base URL: {config.FIRECRAWL_BASE_URL}")
        
        headers = {
            "Authorization": f"Bearer {config.FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG: Request headers: {headers}")
        
        async with aiohttp.ClientSession() as session:
            if is_domain_wide:
                # First get map of all URLs
                map_response = await session.post(
                    f"{config.FIRECRAWL_BASE_URL}/map",
                    headers=headers,
                    json={
                        "url": url,
                        "limit": 1000,
                        "includeSubdomains": True
                    }
                )
                
                if map_response.status != 200:
                    print(f"FireCrawl map error: {map_response.status}")
                    return None
                    
                map_data = await map_response.json()
                urls_to_scrape = map_data.get('links', [])
                if not urls_to_scrape:
                    print("No URLs found in site map")
                    return None
                
                print(f"\nFound {len(urls_to_scrape)} URLs to scrape:")
                
                # Use batch scrape endpoint
                batch_response = await session.post(
                    f"{config.FIRECRAWL_BASE_URL}/batch/scrape",
                    headers=headers,
                    json={
                        "urls": urls_to_scrape,
                        "formats": ["markdown"],
                        "onlyMainContent": True
                    }
                )
                
                if batch_response.status != 200:
                    print(f"FireCrawl batch scrape error: {batch_response.status}")
                    return None
                
                batch_data = await batch_response.json()
                batch_id = batch_data.get('id')
                if not batch_id:
                    print("No batch ID received")
                    return None
                
                # Poll for results
                while True:
                    status_response = await session.get(
                        f"{config.FIRECRAWL_BASE_URL}/batch/scrape/{batch_id}",
                        headers=headers
                    )
                    
                    if status_response.status == 200:
                        status_data = await status_response.json()
                        
                        if status_data.get('status') == 'completed':
                            pages = []
                            for page_data in status_data.get('data', []):
                                if page_data.get('markdown'):
                                    url = page_data.get('metadata', {}).get('sourceURL', '')
                                    print(f"Scraped: {url}")
                                    pages.append({
                                        'url': url,
                                        'content': page_data['markdown'],
                                        'timestamp': datetime.now().strftime('%Y-%m-%d')
                                    })
                            
                            print(f"\nSaved {len(pages)} pages to cache")
                            return {
                                'pages': pages,
                                'metadata': {
                                    'domain': domain,
                                    'source': 'firecrawl',
                                    'timestamp': datetime.now().strftime('%Y-%m-%d'),
                                    'is_domain_wide': True
                                }
                            }
                            
                        elif status_data.get('status') == 'failed':
                            print(f"Batch scrape failed: {status_data.get('error')}")
                            return None
                            
                        await asyncio.sleep(2)
                        
            else:
                # Single page scrape
                scrape_response = await session.post(
                    f"{config.FIRECRAWL_BASE_URL}/scrape",
                    headers=headers,
                    json={
                        "url": url,
                        "formats": ["markdown"],
                        "onlyMainContent": True
                    }
                )
                
                if scrape_response.status == 200:
                    data = await scrape_response.json()
                    if not data.get('data'):
                        return None
                        
                    page_data = data['data']
                    return {
                        'pages': [{
                            'url': url,
                            'content': page_data.get('markdown', ''),
                            'timestamp': datetime.now().strftime('%Y-%m-%d')
                        }],
                        'metadata': {
                            'domain': domain,
                            'source': 'firecrawl',
                            'timestamp': datetime.now().strftime('%Y-%m-%d'),
                            'is_domain_wide': False
                        }
                    }
                else:
                    print(f"FireCrawl scrape error: {scrape_response.status}")
                    return None
                    
    except Exception as e:
        print(f"Error in get_content: {str(e)}")
        traceback.print_exc()
        return None