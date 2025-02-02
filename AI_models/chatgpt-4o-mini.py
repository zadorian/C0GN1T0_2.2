import os
import re
from urllib.parse import urlparse
from openai import OpenAI
from config import config

# Use the correct API key
OPENAI_KEY = "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"

# Initialize client with the correct key and organization
client = OpenAI(
    api_key=OPENAI_KEY,
    organization='org-ATN9LuhPklzEu1L8tM0pxWyG'
)

def call_gpt4o_mini(prompt: str) -> str:
    """Call GPT-4o Mini model"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", #CORRECT MODEL NAME. DO NOT CHANGE!!!!!
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling GPT-4O Mini: {str(e)}")
        return None

def clean_url(url):
    """Clean a single URL by removing common unwanted elements."""
    # Remove Wayback Machine parts
    cleaned = re.sub(r'^https?://web\.archive\.org/(?:web/\d+\*/|web/\*/|details/|web/\d+/|web/)', '', url)
    
    # Remove protocol
    cleaned = re.sub(r'^https?://', '', cleaned)
    
    # Remove www
    cleaned = re.sub(r'^www\.', '', cleaned)
    
    # Remove trailing elements
    cleaned = re.sub(r'/#.*$|#.*$|/$', '', cleaned)
    
    return cleaned

def get_domain(url):
    """Extract domain from URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc if parsed_url.netloc else url

def clean_urls(urls):
    """Clean a list of URLs and return unique ones."""
    cleaned = [clean_url(url) for url in urls]
    return list(set(url for url in cleaned if url))

def get_unique_domains(urls):
    """Get list of unique domains from URLs."""
    domains = set()
    for url in urls:
        domain = get_domain(url)
        if domain:
            domains.add(domain)
    return list(domains)