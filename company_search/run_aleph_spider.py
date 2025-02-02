from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from aleph_spider import AlephSpider
import json
import sys

ALEPH_API_KEY = "1c0971afa4804c2aafabb125c79b275e"

def run_spider(entity_id: str) -> None:
    """Run the Aleph spider for a given entity ID"""
    process = CrawlerProcess(get_project_settings())
    
    # Configure spider settings
    settings = {
        'LOG_LEVEL': 'INFO',
        'LOG_FORMAT': '%(levelname)s: %(message)s',
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': False,
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
    }
    
    for key, value in settings.items():
        process.settings.set(key, value)
    
    # Run spider
    process.crawl(AlephSpider, entity_id=entity_id, api_key=ALEPH_API_KEY)
    process.start()

def main():
    if len(sys.argv) != 2:
        print("Usage: python run_aleph_spider.py <entity_id>")
        print("\nExample: python run_aleph_spider.py 10e17164c0049066d0179852e6414676ba387a8d.3c162f5a1273c2accaa43f7eb80c18119a6093d3")
        return
        
    entity_id = sys.argv[1]
    print(f"\nStarting Aleph spider for entity: {entity_id}")
    print("This may take a few moments...\n")
    
    try:
        run_spider(entity_id)
    except KeyboardInterrupt:
        print("\nSpider cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main() 