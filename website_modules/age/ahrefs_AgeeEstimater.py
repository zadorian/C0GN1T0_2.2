import requests
from datetime import datetime
from urllib.parse import urlparse

def normalize_url(url):
    """Normalize URL by adding https:// if needed."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

def extract_domain(url):
    """Extract domain from URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc.lower()

def format_date(date):
    """Format date as dd Month YYYY."""
    return date.strftime("%d %B %Y")

def fetch_earliest_backlink_date(url, api_key):
    """Fetch earliest backlink date for a URL or domain."""
    endpoint = "https://apiv2.ahrefs.com"
    params = {
        'from': 'backlinks_new_lost',
        'target': url,
        'token': api_key,
        'limit': 1000,
        'output': 'json',
        'order_by': 'first_seen',
        'sort': 'asc'
    }

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

        if not data or 'refpages' not in data:
            return None

        earliest_date = None
        for item in data.get('refpages', []):
            first_seen = item.get('first_seen')
            if first_seen:
                try:
                    first_seen_date = datetime.strptime(first_seen, '%Y-%m-%dT%H:%M:%SZ')
                    if earliest_date is None or first_seen_date < earliest_date:
                        earliest_date = first_seen_date
                except ValueError:
                    continue
        
        return earliest_date
    except Exception as e:
        print(f"Ahrefs API Error: {str(e)}")
        return None

def main():
    ahrefs_api_key = "001VsvfrsqI3boNHFLs-XUTfgIkSm_jbrash5Cvh"
    
    # Get input URL
    url = input("Enter URL: ").strip()
    url = normalize_url(url)
    domain = extract_domain(url)
    
    # Check specific URL
    url_date = fetch_earliest_backlink_date(url, ahrefs_api_key)
    if url_date:
        print(f"The earliest backlink for {url} was detected on: {format_date(url_date)}")
    else:
        print(f"No backlinks found for {url}")
    
    # Check domain if different from URL
    if url != f"https://{domain}":
        domain_date = fetch_earliest_backlink_date(domain, ahrefs_api_key)
        if domain_date and (not url_date or domain_date != url_date):
            print(f"The earliest backlink for domain {domain} was detected on: {format_date(domain_date)}")

if __name__ == "__main__":
    main()
