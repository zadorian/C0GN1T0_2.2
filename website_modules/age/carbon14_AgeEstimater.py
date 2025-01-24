# Carbon14 primarily focuses on estimating the “age” of a website by analyzing the last modified dates of its images. 

from __future__ import print_function

import logging
from datetime import datetime
from email.utils import parsedate

import pytz
import requests
import tzlocal
from lxml import etree
from urllib.parse import urljoin, urlparse

local_timezone = tzlocal.get_localzone()
log = logging.getLogger(__name__)

# Convert UTC time to local timezone
def localize(utc):
    return utc.replace(tzinfo=pytz.utc).astimezone(local_timezone)

# Format datetime as readable string
def readable_date(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")

# Store results for each image found
class Result:
    def __init__(self, timestamp, absolute, internal):
        self.timestamp = timestamp  # When image was last modified
        self.absolute = absolute    # Full URL of image
        self.internal = internal    # Whether image is hosted on same domain

# Main analysis class that processes a webpage
class Analysis:
    def __init__(self, url, author):
        self.url = url
        self.author = author
        self.images = []
        self.end = None
        # Set up requests session with browser user agent
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:57.0) Gecko/20100101 Firefox/57.0"
            }
        )

    # Process a single image URL
    def handle_image(self, address, requested):
        # Skip if already processed or invalid
        if address is None or address in requested:
            return
        requested.add(address)
        log.info("Working on image %s", address)
        
        # Get full URL and check last modified date
        absolute = urljoin(self.url, address)
        try:
            headers = self.session.get(absolute, stream=True).headers
            parsed = parsedate(headers["Last-Modified"])
            timestamp = datetime(*parsed[:6], tzinfo=pytz.utc)
        except:
            log.warning("Cannot fetch date for this image")
            return
            
        # Check if image is on same domain
        internal = urlparse(self.url).netloc == urlparse(absolute).netloc
        self.images.append(Result(timestamp, absolute, internal))

    # Main analysis method
    def run(self):
        self.start = datetime.now(tz=pytz.utc)
        log.info("Fetching page %s", self.url)
        
        # Get webpage HTML
        try:
            self.request = self.session.get(self.url)
        except:
            log.error("Error fetching page!")
            return

        html = etree.HTML(self.request.text)

        # Get page title
        titles = html.cssselect("title")
        self.title = titles[0].text if len(titles) else None

        # Find all images in HTML
        requested = set()
        
        # Process regular img tags
        images = html.cssselect("img")
        for image in images:
            if "src" not in image.attrib:
                continue
            address = image.attrib["src"]
            if address.startswith("data:"):
                continue
            self.handle_image(address, requested)
            
        # Process OpenGraph image meta tags
        opengraph = html.cssselect('meta[property="og:image"]')
        for image in opengraph:
            address = image.attrib["content"]
            self.handle_image(address, requested)

        self.end = datetime.now(tz=pytz.utc)
        self.images.sort(key=lambda i: i.timestamp)

    # Generate report for matching images
    def report_section(self, selector):
        filtered = list(filter(selector, self.images))
        if len(filtered) < 1:
            log.error("Could not date site.")
            return "Could not date site."

        r_state = ""
        r_state += "-" * 80
        labels = f'<br>Date (UTC){"-"*50}URL<br>'
        r_state += labels
        r_state += "-" * 80
        for result in filtered:
            return (
                f"<b>Dated to</b> ----------------- {readable_date(result.timestamp)}"
            )

    # Generate full report
    def report(self):
        return self.report_section(lambda x: True)

# Main entry point - process a domain
def process_date(domain):
    url = f"https://{domain.strip()}"
    analysis = Analysis(url, None)
    analysis.run()
    if analysis.end:
        return analysis.report()
    return None

# Add main entry point
if __name__ == "__main__":
    try:
        while True:
            domain = input("Enter a domain to analyze (or 'quit' to exit): ")
            if domain.lower() == 'quit':
                break
                
            result = process_date(domain)
            if result:
                print(result)
            else:
                print("Could not analyze domain.")
            print("\n" + "-"*50 + "\n")
            
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
