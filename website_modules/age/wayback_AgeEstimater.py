import requests
from datetime import datetime
from urllib.parse import urlparse

def extract_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc or url

def format_date(timestamp):
    """Convert Wayback Machine timestamp to readable date."""
    try:
        date = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        return date.strftime("%d %B %Y")
    except ValueError:
        return None

def get_earliest_snapshot(url):
    """
    Fetch earliest snapshot from Wayback Machine.
    Returns tuple of (date_string, error_message)
    """
    cdx_api_url = f"http://web.archive.org/cdx/search/cdx"
    params = {
        'url': url,
        'output': 'json',
        'limit': 1,
        'filter': 'statuscode:200',
        'sort': 'oldest'
    }
    
    try:
        response = requests.get(cdx_api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if len(data) > 1:  # First row is header
            timestamp = data[1][1]
            formatted_date = format_date(timestamp)
            if formatted_date:
                return formatted_date, None
            
        return None, "No snapshots found"
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def main():
    # Get input URL
    url = input("Enter URL: ").strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Get domain
    domain = extract_domain(url)
    
    # Check specific URL if it's different from domain
    if url.replace('https://', '') != domain:
        url_date, url_error = get_earliest_snapshot(url)
        if url_error:
            print(f"No snapshots found for {url}")
        else:
            print(f"Earliest snapshot for {url} was on: {url_date}")
    
    # Check domain
    domain_date, domain_error = get_earliest_snapshot(domain)
    if domain_error:
        print(f"No snapshots found for domain {domain}")
    else:
        print(f"Earliest snapshot for domain {domain} was on: {domain_date}")

if __name__ == "__main__":
    main()