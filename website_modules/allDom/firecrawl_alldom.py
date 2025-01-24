import requests
import urllib.parse
import time
import re

API_KEY = "fc-00fe2a9f75b8431b99f92c34b4e9927c"
BASE_URL = "https://api.firecrawl.dev/v1"

class InternalURLTracker:
    def __init__(self, domain_hostname):
        self.domain_hostname = domain_hostname
        self.internal_urls = set()

    def is_internal_url(self, url):
        try:
            parsed = urllib.parse.urlparse(url)
            url_hostname = parsed.hostname
            if url_hostname is None:
                return False
            
            if self.domain_hostname.startswith('www.'):
                domain = self.domain_hostname[4:]
            else:
                domain = self.domain_hostname
                
            if url_hostname.startswith('www.'):
                url_hostname = url_hostname[4:]
                
            return url_hostname == domain or url_hostname.endswith('.' + domain)
        except:
            return False

    def add_urls(self, urls):
        """Add only internal URLs, removing duplicates and cleaning URLs"""
        for url in urls:
            cleaned_url = self.clean_url(url)
            if self.is_internal_url(cleaned_url):
                self.internal_urls.add(cleaned_url)

    def clean_url(self, url):
        """Clean the URL by removing trailing parentheses and fragments"""
        url = url.split('#')[0]  # Remove fragments
        url = url.rstrip(')')  # Remove trailing parenthesis
        return url.rstrip('/')  # Remove trailing slash for consistency

    def print_results(self):
        """Print all internal URLs in order"""
        print("\nInternal URLs:")
        for url in sorted(self.internal_urls):
            print(f"  {url}")
        print(f"\nTotal internal URLs found: {len(self.internal_urls)}")

def discover_internal_urls(domain, tracker):
    # Map the domain
    try:
        response = requests.post(
            f"{BASE_URL}/map",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "url": domain,
                "ignoreSitemap": True,
                "includeSubdomains": True,
                "limit": 5000
            }
        )
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('links'):
                for url in result.get('links'):
                    cleaned_url = url.replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
                    if tracker.is_internal_url(f"https://{cleaned_url}"):
                        yield cleaned_url
    except Exception:
        pass

    # Crawl the domain
    try:
        response = requests.post(
            f"{BASE_URL}/crawl",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "url": domain,
                "scrapeOptions": {
                    "formats": ["rawHtml", "markdown"],
                    "onlyMainContent": False
                }
            }
        )
        
        if response.status_code == 200:
            job_id = response.json().get('id')
            
            while True:
                status_response = requests.get(
                    f"{BASE_URL}/crawl/{job_id}",
                    headers={"Authorization": f"Bearer {API_KEY}"}
                )
                
                if status_response.status_code == 200:
                    data = status_response.json()
                    
                    if 'data' in data:
                        urls = set()
                        for page in data['data']:
                            if 'links' in page:
                                urls.update(page['links'])
                            for content_type in ['rawHtml', 'markdown']:
                                if content_type in page:
                                    content_urls = extract_urls_from_content(page[content_type])
                                    urls.update(content_urls)
                        
                        # Handle relative URLs and yield them immediately
                        for url in urls:
                            if url.startswith('/'):
                                url = f"https://{tracker.domain_hostname}{url}"
                            elif not url.startswith(('http://', 'https://')):
                                url = f"https://{tracker.domain_hostname}/{url.lstrip('/')}"
                            
                            cleaned_url = tracker.clean_url(url)
                            if tracker.is_internal_url(cleaned_url):
                                yield cleaned_url
                    
                    if data.get('status') == 'completed':
                        break
                    time.sleep(2)

    except Exception as e:
        pass

def extract_urls_from_content(content):
    """Extract URLs from HTML or text content"""
    urls = set()
    patterns = [
        r'https?://[^\s<>"\'`]+',
        r'href=["\']([^"\']+)["\']',
        r'src=["\']([^"\']+)["\']',
        r'url\(["\']?([^"\'\)]+)["\']?\)',
        r'["\'](/[^"\']*)["\']',
        r'content=["\'][^"\']*?https?://[^\s<>"\']+',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            url = match[0] if isinstance(match, tuple) else match
            urls.add(url)

    return urls

def main():
    print("\nEnter the domain to analyze (e.g., example.com):")
    domain = input().strip()
    if not domain.startswith(('http://', 'https://')):
        domain = 'https://' + domain

    domain_hostname = urllib.parse.urlparse(domain).hostname
    tracker = InternalURLTracker(domain_hostname)
    
    discover_internal_urls(domain, tracker)
    tracker.print_results()

if __name__ == "__main__":
    main()
