import requests
import os
from config import Config
import json
from datetime import datetime

def check_rate_limit():
    """Check OpenCorporates API rate limit status."""
    # Get API token from config
    config = Config()
    api_token = config.OPENCORPORATES_API_KEY
    
    if not api_token:
        print("Error: OpenCorporates API token not found in environment variables")
        return
    
    # API endpoint
    url = "https://api.opencorporates.com/v0.4/account_status"
    
    try:
        # Make request
        response = requests.get(url, params={'api_token': api_token})
        response.raise_for_status()
        
        # Parse response
        data = response.json()
        status = data.get('results', {}).get('account_status', {})
        
        # Print status in a nice format
        print("\nOpenCorporates API Status:")
        print("=" * 50)
        print(f"Plan: {status.get('plan', 'Unknown')}")
        print(f"Status: {status.get('status', 'Unknown')}")
        print(f"Expiry Date: {status.get('expiry_date', 'Unknown')}")
        
        print("\nUsage Today:")
        print(f"  Calls Made: {status.get('usage', {}).get('today', 0)}")
        print(f"  Calls Remaining: {status.get('calls_remaining', {}).get('today', 0)}")
        
        print("\nUsage This Month:")
        print(f"  Calls Made: {status.get('usage', {}).get('this_month', 0)}")
        print(f"  Calls Remaining: {status.get('calls_remaining', {}).get('this_month', 0)}")
        
        # Save status to file for reference
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'rate_limit_status_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nFull status saved to: {filename}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error checking rate limit: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    check_rate_limit() 