import requests
import sys
from time import sleep

def search_users_all_networks(username):
    """
    Search for a username across all supported networks.
    """
    api_key = 'your_api_key_here'
    base_url = 'https://api.social-searcher.com/v2/users'
    
    # List of supported networks
    networks = [
        'web',
        'facebook', 
        'twitter',
        'youtube',
        'instagram',
        'tumblr',
        'reddit',
        'flickr',
        'dailymotion',
        'vimeo',
        'vkontakte'
    ]
    
    print(f"\nSearching for username '{username}' across all supported networks...")
    print("-" * 50)
    
    found_results = False
    
    for network in networks:
        params = {
            'q': username,
            'key': api_key,
            'network': network
        }
        
        try:
            print(f"\nTrying {network.capitalize()}...")
            response = requests.get(base_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'users' in data and data['users']:
                    found_results = True
                    print(f"✓ Found {len(data['users'])} results on {network.capitalize()}:")
                    
                    for user in data['users']:
                        print("\n" + "="*50)
                        print(f"Username: {user.get('username', 'N/A')}")
                        print(f"Name: {user.get('name', 'N/A')}")
                        print(f"Network: {user.get('network', 'N/A')}")
                        if user.get('url'):
                            print(f"Profile URL: {user['url']}")
                        if user.get('description'):
                            print(f"Bio: {user['description']}")
                        print("="*50)
                else:
                    print(f"× No results on {network.capitalize()}")
            else:
                print(f"× Error with {network.capitalize()}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"× Error trying {network.capitalize()}: {str(e)}")
            
        # Small delay between requests to be considerate to the API
        sleep(1)
    
    if not found_results:
        print("\nNo results found on any network.")
    
    print("\nSearch complete.")
    return found_results

def main():
    print("Social Searcher - Username Search (All Networks)")
    print("=" * 45)
    
    while True:
        username = input("\nEnter username to search (or 'quit' to exit): ").strip()
        
        if username.lower() == 'quit':
            break
            
        if not username:
            print("Please enter a username")
            continue
            
        search_users_all_networks(username)

if __name__ == "__main__":
    main()