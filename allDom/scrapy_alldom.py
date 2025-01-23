import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.crawler import CrawlerProcess

class DeepSpider(CrawlSpider):
    name = 'deep_spider'

    rules = (
        Rule(LinkExtractor(), callback='parse_item', follow=True),
    )

    def __init__(self, *args, **kwargs):
        super(DeepSpider, self).__init__(*args, **kwargs)
        self.allowed_domains = kwargs.get('allowed_domains', [])
        self.start_urls = kwargs.get('start_urls', [])

    def parse_item(self, response):
        # This method will be called for each visited page
        url = response.url
        print(url)

# Prompt for URL input and set it as the starting URL
if __name__ == "__main__":
    url_to_scrape = input("Enter the URL of the website you want to scrape: ")
    
    # Ensure the URL has a scheme and www prefix if missing
    if not url_to_scrape.startswith(('http://', 'https://')):
        url_to_scrape = 'http://' + url_to_scrape
    if not url_to_scrape.startswith(('http://www.', 'https://www.')):
        url_to_scrape = url_to_scrape.replace('http://', 'http://www.').replace('https://', 'https://www.')

    domain = url_to_scrape.split("//")[-1].split("/")[0]  # Extract domain from URL

    process = CrawlerProcess(settings={
        'LOG_LEVEL': 'ERROR',
    })
    process.crawl(DeepSpider, start_urls=[url_to_scrape], allowed_domains=[domain])
    process.start()
