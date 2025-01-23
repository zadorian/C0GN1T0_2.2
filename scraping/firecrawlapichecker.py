import requests
from config import config

def test_firecrawl():
    headers = {
        'Authorization': f'Bearer {config.FIRECRAWL_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Simplest possible request
    url = f"{config.FIRECRAWL_BASE_URL}/scrape"
    data = {
        "url": "https://example.com"
    }
    
    try:
        print("\nSending request...")
        print(f"URL: {url}")
        print(f"Data: {data}")
        print(f"Headers: {headers}")
        
        response = requests.post(url, headers=headers, json=data)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("\nSuccess! The API is working with basic parameters.")
            print("We can now add more parameters one by one to see what's supported.")
        elif response.status_code == 401:
            print("\nAPI Key might be invalid or expired")
        elif response.status_code == 404:
            print("\nAPI endpoint might have changed")
        elif response.status_code >= 500:
            print("\nServer might be down")
            
    except Exception as e:
        print(f"Error: {str(e)}")

print("Testing Firecrawl API...")
print(f"Base URL: {config.FIRECRAWL_BASE_URL}")
print(f"API Key (first 10 chars): {config.FIRECRAWL_API_KEY[:10]}...")
test_firecrawl()