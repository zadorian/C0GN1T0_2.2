import requests
from urllib.parse import quote
import logging
from datetime import datetime, timedelta
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up API key
GOOGLE_API_KEY = "AIzaSyBEqsmskKDyXqIOPl26Gf0QdA4pVwM-M2s"
CSE_ID = "3224c9c84183240de"

def fetch_google_results(domain, num_results=100):
    all_results = set()
    
    # Search queries
    queries = [
        f'site:{domain}',
        f'inurl:{domain}'
    ]
    
    for query in queries:
        encoded_query = quote(query, safe='')
        start_index = 1
        
        while len(all_results) < num_results and start_index <= 100:
            url = f"https://www.googleapis.com/customsearch/v1?q={encoded_query}&key={GOOGLE_API_KEY}&cx={CSE_ID}&num=10&start={start_index}"
            
            try:
                response = requests.get(url)
                response.raise_for_status()
                results = response.json().get('items', [])
                if not results:
                    break
                
                # Clean the URLs by removing http://, https://, and www.
                new_results = [item['link'].replace('https://', '').replace('http://', '').replace('www.', '') for item in results]
                all_results.update(new_results)
                
                if len(new_results) < 10:
                    break
                    
                start_index += 10
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching Google results: {e}")
                break
    
    return list(all_results)[:num_results]

if __name__ == "__main__":
    domain = input("Enter domain (e.g., example.com): ")
    results = fetch_google_results(domain)
    for url in results:
        print(url)