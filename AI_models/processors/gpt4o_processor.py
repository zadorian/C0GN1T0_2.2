import os
import re
from urllib.parse import urlparse
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GPT4OMiniProcessor:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            organization='org-ATN9LuhPklzEu1L8tM0pxWyG'
        )

    def call_gpt4o_mini(self, prompt: str) -> str:
        """Call GPT-4o Mini model"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling GPT-4O Mini: {str(e)}")
            return None

    def clean_url(self, url):
        """Clean a single URL by removing common unwanted elements."""
        cleaned = re.sub(r'^https?://web\.archive\.org/(?:web/\d+\*/|web/\*/|details/|web/\d+/|web/)', '', url)
        cleaned = re.sub(r'^https?://', '', cleaned)
        cleaned = re.sub(r'^www\.', '', cleaned)
        cleaned = re.sub(r'/#.*$|#.*$|/$', '', cleaned)
        return cleaned

    def get_domain(self, url):
        """Extract domain from URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc if parsed_url.netloc else url

    def clean_urls(self, urls):
        """Clean a list of URLs and return unique ones."""
        cleaned = [self.clean_url(url) for url in urls]
        return list(set(url for url in cleaned if url))

    def get_unique_domains(self, urls):
        """Get list of unique domains from URLs."""
        domains = set()
        for url in urls:
            domain = self.get_domain(url)
            if domain:
                domains.add(domain)
        return list(domains) 