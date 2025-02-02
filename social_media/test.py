import requests
import json
from datetime import datetime
import sys
from time import sleep

# API key for Social Searcher
API_KEY = "decdab3ea83f1df1c6386f620a6ca72f"

# Network mappings for filtering
NETWORK_MAP = {
    "facebook": "facebook",
    "facebook.com": "facebook",
    "twitter": "twitter",
    "twitter.com": "twitter",
    "instagram": "instagram",
    "instagram.com": "instagram",
    "linkedin": "linkedin",
    "linkedin.com": "linkedin",
    "youtube": "youtube",
    "youtube.com": "youtube",
    "web": "web"
}

class SocialSearcher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.social-searcher.com/v2"
        self.available_networks = []
        self.monitoring_enabled = False
        self.check_account()

    def check_account(self):
        """Check account details and available features"""
        url = f"{self.base_url}/accounts"
        params = {"key": self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "accounts" in data and data["accounts"]:
                account = data["accounts"][0]
                
                # Get available networks
                if "premium" in account and "networks" in account["premium"]:
                    self.available_networks = account["premium"]["networks"].split(",")
                
                # Check if monitoring is enabled
                if "monitoring" in account and account["monitoring"]["allowed"] == "Y":
                    self.monitoring_enabled = True
                    self.monitoring_limit = account["monitoring"]["limit"]
                    self.monitoring_count = account["monitoring"]["monitorings_count"]
                    self.monitoring_max = account["monitoring"]["monitorings_max"]
                
                print("\n=== ACCOUNT DETAILS ===")
                print("Plan:", account.get("plan", "Unknown"))
                print("Available networks:", ", ".join(self.available_networks))
                print("Search requests remaining:", account["search"]["limit"] - account["search"]["requests_count"])
                if self.monitoring_enabled:
                    print("\nMonitoring enabled:")
                    print(f"- Active monitors: {self.monitoring_count}/{self.monitoring_max}")
                    print(f"- Posts limit: {self.monitoring_limit}")
                print("\nFull account details:")
                print(json.dumps(data, indent=2))
                
        except requests.exceptions.RequestException as e:
            print("Error checking account:", e)
            if hasattr(e, "response") and e.response is not None:
                print("Response:", e.response.text)

    def normalize_network(self, network):
        """Convert network input to normalized form"""
        if not network:
            return None
        network = network.lower().strip()
        return NETWORK_MAP.get(network, network)

    def search_posts(self, query, network=None):
        """
        Search posts across networks using GET /v2/search endpoint
        """
        url = f"{self.base_url}/search"
        params = {
            "key": self.api_key,
            "q": query,
            "limit": 100  # Maximum allowed
        }
        
        # Normalize network name if provided
        normalized_network = self.normalize_network(network)
        if normalized_network:
            print(f"Will filter results to show only {normalized_network} posts...")
            
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "posts" in data and data["posts"]:
                # If network was specified, filter results client-side
                if normalized_network:
                    filtered_posts = [post for post in data["posts"] 
                                    if self.normalize_network(post.get("network", "")) == normalized_network]
                    if filtered_posts:
                        self._print_posts(filtered_posts)
                    else:
                        print(f"No results found on {network}")
                else:
                    self._print_posts(data["posts"])
            else:
                print("No results found")
                
        except requests.exceptions.HTTPError as e:
            print(f"Error: {str(e)}")
            if e.response.status_code == 400:
                print("Invalid search query. For exact phrase matching, use quotes: \"your phrase\"")
            if hasattr(e, "response") and e.response is not None:
                print("Response:", e.response.text)
        except requests.exceptions.RequestException as e:
            print(f"Error: {str(e)}")

    def search_users(self, username, network=None):
        """
        Search for users using GET /v2/users endpoint
        """
        if not network:
            # If no network specified, search each available network
            print(f"Searching for user '{username}' across all networks...")
            all_users = []
            for net in self.available_networks:
                try:
                    url = f"{self.base_url}/users"  # Changed endpoint
                    params = {
                        "key": self.api_key,
                        "q": username,  # Changed to use q parameter
                        "network": net
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if "users" in data and data["users"]:  # Changed to check for users
                        all_users.extend(data["users"])
                        
                except requests.exceptions.RequestException:
                    continue  # Skip errors for individual networks
                    
            if all_users:
                self._print_users(all_users)
            else:
                print(f"No users found matching '{username}'")
            return
            
        # Single network search
        normalized_network = self.normalize_network(network)
        if normalized_network not in self.available_networks:
            print(f"Network '{network}' not available. Available networks: {', '.join(self.available_networks)}")
            return
            
        url = f"{self.base_url}/users"  # Changed endpoint
        params = {
            "key": self.api_key,
            "q": username,  # Changed to use q parameter
            "network": normalized_network
        }
        
        print(f"Searching for user '{username}' on {normalized_network}...")

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "users" in data and data["users"]:  # Changed to check for users
                self._print_users(data["users"])
            else:
                print(f"No users found matching '{username}' on {normalized_network}")
                
        except requests.exceptions.HTTPError as e:
            print(f"Error: {str(e)}")
            if e.response.status_code == 405:
                print(f"User search not available for {normalized_network} on your plan.")
            if hasattr(e, "response") and e.response is not None:
                print("Response:", e.response.text)
        except requests.exceptions.RequestException as e:
            print(f"Error: {str(e)}")

    def _print_posts(self, posts):
        """Format and print posts"""
        print(f"\nFound {len(posts)} results:")
        for post in posts:
            print("\n" + "="*50)
            print(f"Network: {post.get('network', 'Unknown')}")
            
            posted_date = post.get('posted')
            if posted_date:
                try:
                    if isinstance(posted_date, str):
                        date_obj = datetime.fromisoformat(posted_date.replace('Z', '+00:00'))
                    else:
                        date_obj = datetime.fromtimestamp(posted_date)
                    print(f"Posted: {date_obj.strftime('%Y-%m-%d %H:%M:%S')}")
                except (ValueError, TypeError):
                    print(f"Posted: {posted_date}")
            
            print(f"Type: {post.get('type', 'Unknown')}")
            
            text = post.get("text", "No text")
            if len(text) > 200:
                text = text[:197] + "..."
            print(f"Text: {text}")
            
            if "user" in post:
                print(f"User: {post['user'].get('name', 'Unknown')}")
                
            if "url" in post:
                print(f"URL: {post['url']}")
                
            print("="*50)

    def _print_users(self, users):
        """Format and print user results"""
        print(f"\nFound {len(users)} users:")
        for user in users:
            print("\n" + "="*50)
            print(f"Network: {user.get('network', 'Unknown')}")
            print(f"Name: {user.get('name', 'Unknown')}")
            print(f"Username: {user.get('username', 'Unknown')}")
            if "url" in user:
                print(f"Profile URL: {user['url']}")
            if "description" in user:
                desc = user["description"]
                if len(desc) > 200:
                    desc = desc[:197] + "..."
                print(f"Bio: {desc}")
            print("="*50)

def interactive_cli():
    """Interactive CLI for Social Searcher API"""
    searcher = SocialSearcher(API_KEY)
    
    while True:
        print("\nSocial Searcher CLI")
        print("Commands:")
        print("  Basic search examples: (returns up to 100 results)")
        print("    donald trump                     - Search across all networks")
        print("    \"donald trump\"                   - Exact phrase match")
        print("\n  Filter results by network:")
        print("    trump :facebook                  - Show only Facebook results")
        print("    trump :facebook.com              - Same as above")
        print("    \"exact phrase\" :linkedin         - Show only LinkedIn results")
        print("\n  User search examples:")
        print("    @johndoe                        - Search user on all networks")
        print("    @johndoe :facebook              - Search user on specific network")
        print("\n  Other commands:")
        print("    exit                            - Quit program")
        print("\nTips:")
        print("- Use \"quotes\" for exact phrase matching")
        print("- Each search returns up to 100 results")
        print("- Network filtering is done client-side")
        print("- Network names like ':facebook' and ':facebook.com' both work")
        print(f"Available networks: {', '.join(searcher.available_networks)}\n")
        
        user_input = input("> ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break
            
        try:
            if user_input.startswith("@"):
                # User search
                username = user_input[1:]  # Remove @ symbol
                network = None
                
                # Check if network is specified
                if ":" in username:
                    username, network = username.split(":", 1)
                
                searcher.search_users(username.strip(), network.strip() if network else None)
            else:
                # Post search
                if ":" in user_input:
                    query, network = user_input.rsplit(":", 1)  # Use rsplit to handle quotes with colons
                    searcher.search_posts(query.strip(), network.strip())
                else:
                    searcher.search_posts(user_input)
                    
        except KeyboardInterrupt:
            print("\nOperation cancelled")
            break
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    interactive_cli()