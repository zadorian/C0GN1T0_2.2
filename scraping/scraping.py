import sys
from pathlib import Path
import asyncio
from typing import Dict, Optional
import traceback

# Add project root to path
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

from config import config
from caching.scrape_caching import content_cache

class ContentController:
    def __init__(self):
        # Add Content directory to path - using CORRECT casing!
        sys.path.append(str(Path(config.CONTENT_DIR)))
        self.content_cache = content_cache
        
    async def get_content(self, url: str) -> Optional[Dict]:
        """Route to appropriate content getter based on URL format"""
        try:
            # Historic content (any URL with !)
            if '!' in url:
                # Import here to avoid circular import
                from . import archived_scraping
                return await archived_scraping.content_controller.get_content(url)
            
            # Current content (everything else)
            return await self.content_cache.get_content(url)
            
        except Exception as e:
            print(f"Error routing content request: {str(e)}")
            traceback.print_exc()
            return None

# Single global instance
content_controller = ContentController()

async def main():
    """Simple interface for testing content fetching"""
    print("\nC0GN1T0 Content Fetcher")
    print("=" * 50)
    print("\nURL formats:")
    print("- Historic specific year: 2020!example.com")
    print("- Historic year range: 2021-2023!example.com")
    print("- Historic back to year: 2020<-!example.com")
    print("- Current single page: ?example.com/page.html")
    print("- Current full domain: example.com?")
    print("\nType 'quit' to exit")
    
    while True:
        url = input("\nEnter URL: ").strip()
        if url.lower() == 'quit':
            break
            
        print(f"\nProcessing: {url}")
        print("=" * 50)
        
        content = await content_controller.get_content(url)
        if content:
            print("\nContent retrieved and cached. Use memory search to explore.")
        else:
            print("\nNo content retrieved")

if __name__ == "__main__":
    asyncio.run(main())
