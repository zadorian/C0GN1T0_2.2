import sys
from collections import defaultdict
import re

def categorize_urls(urls):
    """Accept either a file object or a set of URLs and return categorized results"""
    # Initialize categories
    results = {
        'html': [],
        'core': [],
        'images': [],
        'favicons': [],
        'subdomains': [],
        'other': []
    }
    
    # Convert input to list if it's a set
    if isinstance(urls, set):
        urls = list(urls)
    
    # Handle different input types
    if hasattr(urls, 'read'):
        urls = [line.strip() for line in urls if line.strip()]
    
    for url in urls:
        if not url or 'javascript:' in url:
            continue
            
        # Handle paths and full URLs
        path = url.split('/')[-1] if '/' in url else url
        
        # Categorize based on patterns
        if '.html' in url.lower():
            results['html'].append(url)
        elif any(ext in url.lower() for ext in ['.php', '.css', '.js']):
            results['core'].append(url)
        elif '/images/' in url.lower() or any(ext in url.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
            results['images'].append(url)
        elif '/favicon' in url.lower() or 'favicon' in url.lower():
            results['favicons'].append(url)
        elif url.count('.') > 1 and '/' not in url:
            results['subdomains'].append(url)
        else:
            if not any(url in category for category in results.values()):
                results['other'].append(url)
    
    return results

def main():
    if len(sys.argv) > 1:
        # Read from file if provided
        with open(sys.argv[1], 'r') as f:
            categorize_urls(f)
    else:
        # Read from stdin
        categorize_urls(sys.stdin)

if __name__ == "__main__":
    main()