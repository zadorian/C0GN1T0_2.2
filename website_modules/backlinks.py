import requests
from typing import Dict, List, Tuple
from datetime import datetime
from urllib.parse import urlparse
import aiohttp
import asyncio
import re
from typing import Dict, List, Optional, Set
import json
from collections import defaultdict
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables directly in backlinks.py
load_dotenv()

# Get API key directly from environment
AHREFS_API_KEY = os.getenv("AHREFS_API_KEY")
if not AHREFS_API_KEY:
    raise ValueError("AHREFS_API_KEY not found in environment variables")

AHREFS_ENDPOINT = "https://apiv2.ahrefs.com"

async def handle_backlinks_analysis(command: str) -> str:
    """Handle backlinks analysis command."""
    try:
        # Extract command type and domain
        parts = command.split()
        if len(parts) < 2:
            return "Please provide a domain for backlinks analysis"
            
        cmd_part = parts[0]  # Get !bl<N or bl!<N
        domain = parts[1].strip()
        
        # Check for limit parameter in command
        limit = 30  # Default limit
        if '<' in cmd_part:
            cmd_type, limit_str = cmd_part.split('<')
            try:
                limit = int(limit_str)
            except ValueError:
                return f"Invalid limit: {limit_str}. Please use a number."
        else:
            cmd_type = cmd_part
            
        # Remove trailing ? if present
        domain = domain.rstrip('?')
        
        # Handle different command types
        if cmd_type == "!bl":
            # Show reference pages (individual backlinks)
            return _analyze_reference_pages(domain, initial_results=limit)
        else:  # bl!
            # Show referring domains summary
            return _analyze_domain_backlinks(domain, initial_results=limit)
        
    except Exception as e:
        return f"Error in backlinks analysis: {str(e)}"

def _make_api_request(params: Dict, api_key: str) -> Dict:
    """Make request to Ahrefs API v2"""
    try:
        params.update({
            'token': api_key,
            'output': 'json'
        })
        
        response = requests.get(AHREFS_ENDPOINT, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return {}
    except Exception as e:
        print(f"API Request Error: {str(e)}")
        return {}

def _analyze_domain_backlinks(domain: str, initial_results: int = 30, api_key: str = None) -> str:
    """Analyze domains linking to a domain using refdomains_by_type endpoint"""
    api_key = api_key or AHREFS_API_KEY
    params = {
        'from': 'refdomains_by_type',
        'target': domain,
        'mode': 'domain',
        'limit': max(initial_results, 100),  # Ensure we get enough results for pagination
        'order_by': 'refdomains:asc'  # Order by number of outgoing links ascending
    }
    
    data = _make_api_request(params, api_key)
    if not data or 'refdomains' not in data:
        return f"No backlink data found for domain: {domain}"
        
    output = [f"\nBacklink Analysis for {domain} (showing first {initial_results} results)"]
    
    # Add stats from the API response
    if 'stats' in data:
        stats = data['stats']
        output.extend([
            f"Total referring domains: {stats.get('refdomains', 0)}",
            f"Total referring IPs: {stats.get('ips', 0)}",
            f"Total backlinks: {stats.get('total_backlinks', 0)}",
            f"DoFollow backlinks: {stats.get('total_backlinks_dofollow', 0)}"
        ])
    
    output.append("\nTop referring domains:")
    
    # Store results for pagination
    handle_backlinks_analysis.current_results = {
        domain: {
            'results': data['refdomains'],
            'page': 0,
            'total': len(data['refdomains']),
            'initial_results': initial_results
        }
    }
    
    # Show first N results
    results = data['refdomains'][:initial_results]
    for i, ref in enumerate(results, 1):
        domain_rating = ref.get('domain_rating', 'N/A')
        backlinks = ref.get('backlinks', 0)
        backlinks_dofollow = ref.get('backlinks_dofollow', 0)
        first_seen = _format_date(ref.get('first_seen'))
        outgoing_links = ref.get('refdomains', 0)  # Number of outgoing links
        
        output.append(f"\n{i}. {ref['refdomain']}")
        output.append(f"   DR: {domain_rating}")
        output.append(f"   Backlinks: {backlinks} ({backlinks_dofollow} dofollow)")
        output.append(f"   Outgoing Links: {outgoing_links}")
        output.append(f"   First seen: {first_seen}")
    
    if len(data['refdomains']) > initial_results:
        output.append("\nType 'more' to see additional results")
        
    return "\n".join(output)

def _analyze_reference_pages(domain: str, initial_results: int = 30, api_key: str = None) -> str:
    """Get reference pages linking to target domain"""
    api_key = api_key or AHREFS_API_KEY
    params = {
        'from': 'backlinks',
        'target': domain,
        'mode': 'domain',
        'limit': max(initial_results, 100),  # Ensure we get enough results for pagination
        'output': 'json',
        'token': api_key,
        'order_by': 'links_external:asc'  # Order by number of outgoing links ascending
    }
    
    data = _make_api_request(params, api_key)
    if not data or 'refpages' not in data:
        return f"No backlink data found for domain: {domain}"
        
    output = [f"\nReference Pages Analysis for {domain} (showing first {initial_results} results)"]
    
    # Add stats if available
    if 'stats' in data:
        output.append(f"Total backlinks: {data['stats'].get('backlinks', 0)}")
    
    output.append("\nTop linking pages:")
    
    # Store results for pagination
    handle_backlinks_analysis.current_results = {
        domain: {
            'results': data['refpages'],
            'page': 0,
            'total': len(data['refpages']),
            'initial_results': initial_results
        }
    }
    
    # Show first N results
    results = data['refpages'][:initial_results]
    for i, link in enumerate(results, 1):
        output.append(f"\n{i}. {link.get('url_from', '')}")
        output.append(f"   AR: {link.get('ahrefs_rank', 'N/A')}")
        output.append(f"   Anchor: {link.get('anchor', '')}")
        output.append(f"   Outgoing Links: {link.get('links_external', 'N/A')}")
        output.append(f"   Type: {link.get('link_type', '')} ({'NoFollow' if link.get('nofollow') else 'DoFollow'})")
            
    if len(data['refpages']) > initial_results:
        output.append("\nType 'more' to see additional results")
    
    return "\n".join(output)

def _format_date(date_str: str) -> str:
    """Format date string from API response"""
    if not date_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d %B %Y')
    except:
        return date_str

def handle_more_command(domain: str) -> str:
    """Handle the 'more' command for pagination"""
    try:
        if not hasattr(handle_backlinks_analysis, 'current_results') or \
           domain not in handle_backlinks_analysis.current_results:
            return "No active backlinks analysis. Please run a new search."

        data = handle_backlinks_analysis.current_results[domain]
        data['page'] += 1
        
        initial_results = data.get('initial_results', 30)  # Get initial results count
        start_idx = initial_results + (data['page'] - 1) * 10  # Start after initial results
        results = data['results'][start_idx:start_idx + 10]
        
        if not results:
            data['page'] -= 1
            return "No more results available."

        output = []
        for i, result in enumerate(results, start_idx + 1):
            if 'refdomain' in result:  # Domain results
                output.append(f"\n{i}. {result['refdomain']}")
                output.append(f"   DR: {result.get('domain_rating', 'N/A')}")
                output.append(f"   Backlinks: {result.get('backlinks', 0)}")
                output.append(f"   Outgoing Links: {result.get('refdomains', 0)}")
                output.append(f"   First seen: {_format_date(result.get('first_seen'))}")
            else:  # URL results
                output.append(f"\n{i}. {result.get('url_from', '')}")
                output.append(f"   AR: {result.get('ahrefs_rank', 'N/A')}")
                output.append(f"   Anchor: {result.get('anchor', '')}")
                output.append(f"   Outgoing Links: {result.get('links_external', 'N/A')}")
                output.append(f"   Type: {result.get('link_type', '')} ({'NoFollow' if result.get('nofollow') else 'DoFollow'})")
        
        if len(data['results']) > (start_idx + 10):
            output.append("\nType 'more' for next page")
        
        return "\n".join(output)

    except Exception as e:
        return f"Error displaying more results: {str(e)}"