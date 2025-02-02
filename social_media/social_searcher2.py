import requests
from datetime import datetime
import sys

class SocialSearcher:
    def __init__(self):
        self.api_key = 'decdab3ea83f1df1c6386f620a6ca72f'
        self.base_url = 'https://api.social-searcher.com/v2/search'
        
        # Expanded platform mapping with all common variations
        self.platform_mapping = {
            'reddit': 'reddit',
            'reddit.com': 'reddit',
            'youtube': 'youtube',
            'youtube.com': 'youtube',
            'yt': 'youtube',
            'vk': 'vkontakte',
            'vk.com': 'vkontakte',
            'vk.ru': 'vkontakte',
            'vkontakte': 'vkontakte',
            'vkontakte.com': 'vkontakte',
            'vkontakte.ru': 'vkontakte',
            'tumblr': 'tumblr',
            'tumblr.com': 'tumblr',
            'web': 'web'
        }

    def parse_query(self, query: str) -> tuple[str, str]:
        """Parse query string to extract search term and platform"""
        # Split for platform specific search
        parts = query.split(':')
        if len(parts) == 2:
            search_term = parts[0].strip()
            platform = parts[1].strip().lower().rstrip('?')
            
            # Check if platform is supported
            if platform in ['twitter', 'twitter.com', 'x', 'x.com']:
                print("\nSorry, Twitter/X searches are not supported by this API.")
                return None, None
            
            platform = self.platform_mapping.get(platform)
            if platform is None:
                print(f"\nUnsupported platform. Available platforms are:")
                print("Reddit: :reddit, :reddit.com")
                print("YouTube: :youtube, :youtube.com, :yt")
                print("VKontakte: :vk, :vk.com, :vk.ru, :vkontakte")
                print("Tumblr: :tumblr, :tumblr.com")
                print("Web: :web")
                return None, None
                
            return search_term, platform
            
        return query.strip(), None

    def search(self, query: str) -> None:
        """
        Search using the format 'keyword :platform?'
        """
        search_term, platform = self.parse_query(query)
        if search_term is None:  # Invalid platform was specified
            return
            
        params = {
            'q': search_term,
            'key': self.api_key,
            'network': platform
        }

        try:
            print(f"\nMaking request to: {self.base_url}")
            print(f"Searching for: {search_term}")
            if platform:
                print(f"Platform: {platform}")
                
            response = requests.get(self.base_url, params=params)
            print(f"Status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error: {response.text}")
                return
                
            data = response.json()
            
            if 'posts' in data and data['posts']:
                print(f"\nFound {len(data['posts'])} results")
                for post in data['posts']:
                    print("\n" + "="*50)
                    print(f"Network: {post.get('network', 'Unknown')}")
                    
                    posted = post.get('posted')
                    if posted:
                        try:
                            if isinstance(posted, str):
                                date_obj = datetime.fromisoformat(posted.replace('Z', '+00:00'))
                            else:
                                date_obj = datetime.fromtimestamp(posted)
                            print(f"Posted: {date_obj.strftime('%Y-%m-%d %H:%M:%S')}")
                        except (ValueError, TypeError):
                            print(f"Posted: {posted}")
                    
                    print(f"User: {post.get('user', {}).get('name', 'Anonymous')}")
                    print(f"Type: {post.get('type', 'Unknown')}")
                    print(f"Sentiment: {post.get('sentiment', 'Unknown')}")
                    print("-"*50)
                    print(f"Content: {post.get('text', 'No content')}")
                    if post.get('url'):
                        print(f"URL: {post['url']}")
                    print("="*50)
            else:
                print(f"No results found{f' on {platform}' if platform else ''}")
                
        except requests.exceptions.RequestException as e:
            print(f"Error performing search: {e}")
            print(f"Full error details: {str(e)}")
            return

def main():
    searcher = SocialSearcher()
    
    print("\nWelcome to Social Searcher!")
    print("Search formats:")
    print("  - keyword :platform? (e.g., 'python :reddit?')")
    print("  - keyword (search all platforms)")
    print("\nAvailable platforms and their aliases:")
    print("  - Reddit: :reddit, :reddit.com")
    print("  - YouTube: :youtube, :youtube.com, :yt")
    print("  - VKontakte: :vk, :vk.com, :vk.ru, :vkontakte")
    print("  - Tumblr: :tumblr, :tumblr.com")
    print("  - Web: :web")
    
    while True:
        try:
            query = input("\nEnter search query (or 'quit' to exit): ").strip()
            if query.lower() == 'quit':
                break
                
            if not query:
                print("Search query cannot be empty")
                continue
                
            searcher.search(query)
            
        except KeyboardInterrupt:
            break
            
    print("\nGoodbye!")

if __name__ == "__main__":
    main()