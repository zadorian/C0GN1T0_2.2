import sys
import os
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
import asyncio
from typing import Tuple, Optional, Dict
from dotenv import load_dotenv
from Tags.scenarios.scenario_age import AgeScenario
import requests
import json
import logging
import aiohttp
import re

# Load environment variables
load_dotenv()

# Get API keys directly from environment
AHREFS_API_KEY = os.getenv("AHREFS_API_KEY")
WHOISXML_API_KEY = os.getenv("WHOISXML_API_KEY")

# Add the current directory to the Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import functions from other files - with error handling and absolute imports
try:
    from .carbon14_AgeEstimater import process_date
except ImportError as e:
    print(f"Warning: Could not import carbon14_AgeEstimater: {e}")
    process_date = None

try:
    from .ahrefs_AgeeEstimater import fetch_earliest_backlink_date
except ImportError as e:
    print(f"Warning: Could not import ahrefs_AgeeEstimater: {e}")
    fetch_earliest_backlink_date = None

try:
    from .whoisxmlapi_AgeEstimater import get_whois_data
except ImportError as e:
    print(f"Warning: Could not import whoisxmlapi_AgeEstimater: {e}")
    get_whois_data = None

try:
    from .wayback_AgeEstimater import get_earliest_snapshot
except ImportError as e:
    print(f"Warning: Could not import wayback_AgeEstimater: {e}")
    get_earliest_snapshot = None

def normalize_url(url: str) -> str:
    """Clean and normalize URL."""
    url = url.lower().strip()
    if url.startswith('?'):
        url = url[1:]  # Remove leading ? for single page analysis
    url = url.replace('http://', '').replace('https://', '').replace('www.', '')
    return url

async def analyze_domain(domain: str) -> str:
    """Analyze domain registration and age."""
    try:
        # Remove any trailing question mark
        domain = domain.strip('?')
        
        # Construct API URL
        api_url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService"
        params = {
            "apiKey": WHOISXML_API_KEY,
            "domainName": domain,
            "outputFormat": "JSON"
        }

        # Make API request
        response = requests.get(api_url, params=params)
        data = response.json()

        if "WhoisRecord" not in data:
            return "Domain creation date not found"

        whois_record = data["WhoisRecord"]
        creation_date = None

        # Try different possible locations for creation date
        if "createdDate" in whois_record:
            creation_date = whois_record["createdDate"]
        elif "registryData" in whois_record and "createdDate" in whois_record["registryData"]:
            creation_date = whois_record["registryData"]["createdDate"]

        if not creation_date:
            return "Domain creation date not found"

        # Parse creation date
        created = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
        age = datetime.now() - created

        # Format response
        years = age.days // 365
        months = (age.days % 365) // 30
        
        response = f"\nDomain Age Analysis for {domain}:\n"
        response += f"Created: {created.strftime('%d %B %Y')}\n"
        response += f"Age: {years} years, {months} months"
        
        return response

    except Exception as e:
        return f"Error analyzing domain age: {str(e)}"

async def get_wayback_date(url: str) -> Optional[str]:
    """Get earliest Wayback Machine snapshot."""
    date, error = get_earliest_snapshot(f"https://{url}")
    return date if not error else None

async def get_backlink_date(url: str) -> Optional[datetime]:
    """Get earliest backlink date."""
    return fetch_earliest_backlink_date(url, AHREFS_API_KEY)

async def get_content_date(url: str) -> Optional[str]:
    """Get content modification date."""
    results = process_date(url)
    if results and "Dated to" in results:
        carbon_date = results.split('----------------- ')[1].strip()
        try:
            dt = datetime.strptime(carbon_date, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d %B %Y')
        except:
            return carbon_date
    return None

async def analyze_page(url: str) -> str:
    """Analyze single page age using multiple methods."""
    # Run all checks concurrently
    wayback_date, backlink_date, content_date = await asyncio.gather(
        get_wayback_date(url),
        get_backlink_date(url),
        get_content_date(url)
    )
    
    # Build output
    results = []
    
    if wayback_date:
        results.append(f"First archive: {wayback_date}")
    if backlink_date:
        results.append(f"First backlink: {backlink_date.strftime('%d %B %Y')}")
    else:
        results.append("No backlinks found")
    if content_date:
        results.append(f"Last modified: {content_date}")
        
    if not results:
        return "No age data found"
        
    return "\n".join(results)

async def analyze_url(command: str) -> str:
    """Main entry point for URL analysis."""
    try:
        # Clean up the command
        command = command.strip()
        
        # Extract the URL part (remove 'age!' prefix)
        url_part = command.replace('age!', '').strip()
        
        # Normalize for analysis
        clean_url = normalize_url(url_part)
        
        # Determine analysis type and get result
        if url_part.endswith('?'):  # Domain analysis (example.com?)
            domain = clean_url.rstrip('?')
            result = await analyze_domain(domain)
        elif url_part.startswith('?'):  # Page analysis (?example.com)
            result = await analyze_page(clean_url)
        else:
            result = "Invalid format. Use:\nage! ?example.com/page - for page analysis\nage! example.com? - for domain analysis"
        
        # Create tags for the age analysis
        age_scenario = AgeScenario()
        age_scenario.process_age_command(command, result)
        
        return result
            
    except Exception as e:
        return f"Error: {str(e)}"

async def handle_age_command(command: str) -> str:
    """
    Handle age analysis command.
    Example: age! domain.com?
    """
    try:
        parts = command.split()
        if len(parts) < 2:
            return "Please provide a domain for age analysis"
            
        domain = parts[1].strip()
        
        # Remove trailing ? if present
        domain = domain.rstrip('?')
        
        # Analyze domain age using various methods
        async with aiohttp.ClientSession() as session:
            # Try Wayback Machine first
            wayback_age = await _check_wayback_age(session, domain)
            if wayback_age:
                return f"Domain {domain} first seen: {wayback_age}"
            
            # Try WHOIS data
            whois_age = await _check_whois_age(domain)
            if whois_age:
                return f"Domain {domain} registered: {whois_age}"
            
            return f"Could not determine age for {domain}"
            
    except Exception as e:
        return f"Error in age analysis: {str(e)}"

async def _check_wayback_age(session: aiohttp.ClientSession, domain: str) -> Optional[str]:
    """Check domain's first appearance in Wayback Machine."""
    try:
        url = f"https://web.archive.org/cdx/search/cdx"
        params = {
            'url': domain,
            'output': 'json',
            'fl': 'timestamp',
            'limit': 1,
            'sort': 'timestamp:asc'  # Get earliest snapshot
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if len(data) > 1:  # First row is header
                    timestamp = data[1][0]  # Get first timestamp
                    date = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
                    return date.strftime('%d %B %Y')
        return None
        
    except Exception:
        return None

async def _check_whois_age(domain: str) -> Optional[str]:
    """Check domain registration date from WHOIS data."""
    try:
        # Implement WHOIS lookup here
        # For now, return None as placeholder
        return None
        
    except Exception:
        return None

def main():
    while True:
        command = input("\nEnter URL to analyze (or 'quit' to exit): ").strip()
        if command.lower() == 'quit':
            break
        try:
            result = asyncio.run(analyze_url(command))
            print(f"\n{result}\n")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")

if __name__ == "__main__":
    main()