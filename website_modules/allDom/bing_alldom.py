import requests
import logging
from urllib.parse import quote

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_bing_results(domain, num_results=100):
    subscription_key = "2ef8455202724be0ba166409ce51bad6"
    search_url = "https://api.bing.microsoft.com/v7.0/search"
    
    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key
    }
    
    all_results = set()
    
    # Search queries
    queries = [
        f'site:{domain}',
        f'inurl:{domain}'
    ]
    
    for query in queries:
        offset = 0
        while len(all_results) < num_results and offset < 100:
            try:
                params = {
                    "q": query,
                    "count": 50,
                    "offset": offset,
                    "responseFilter": "Webpages"
                }
                
                response = requests.get(search_url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if "webPages" not in data:
                    break
                    
                new_urls = [result["url"].replace('https://', '').replace('http://', '').replace('www.', '') 
                           for result in data["webPages"]["value"]]
                all_results.update(new_urls)
                
                if len(new_urls) < 50:
                    break
                    
                offset += 50
                
            except Exception as e:
                logging.error(f"Error fetching Bing results: {e}")
                break
    
    return list(all_results)[:num_results]

if __name__ == "__main__":
    domain = input("Enter domain (e.g., example.com): ")
    results = fetch_bing_results(domain)
    for url in results:
        print(url)