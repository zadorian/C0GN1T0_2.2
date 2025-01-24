from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug print to check if env var is loaded
print(f"AHREFS_API_KEY from env: {os.getenv('AHREFS_API_KEY')}")

class Config:
    # Debug mode (set to False to reduce logging)
    DEBUG = False
    
    # API Keys
    GEMINI_API_KEY = "AIzaSyApYgmp9_2wNr4txTcRhEoyYALQ6cTlmgQ"
    OPENAI_API_KEY = "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"
    AZURE_KEY = "2sjQFI5N4n2lUxe5eaLNKbfmLqC0J4VRaa8jNQ4pz3w7Xd4GvsCzJQQJ99AKACPV0roXJ3w3AAAaACOGEea6"
    AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL")
    AHREFS_API_KEY = os.getenv("AHREFS_API_KEY")

    # Paths
    PROJECT_ROOT = Path(__file__).parent
    CONTENT_DIR = PROJECT_ROOT / 'Content'
    CACHE_DIR = CONTENT_DIR / 'Cache'
    MEMORY_DIR = PROJECT_ROOT / 'memory'

    # Memory settings
    MEMORY_INDEX_DIR = MEMORY_DIR / 'Index'
    OPERATIONAL_MEMORY_FILE = MEMORY_DIR / 'operational_memory.json'

    # Name variations for entity matching
    NAME_VARIATIONS = {
        'anthony': ['tony', 'ant'],
        'stephen': ['steve', 'steph'],
        'marton': ['marci', 'marti'],
        'tamas': ['tom', 'tommy'],
        'barnabas': ['barni', 'barney'],
        'domonkos': ['dom', 'domi'],
        'andras': ['andy', 'andi']
    }

    # Search Engine APIs
    WHOISXML_API_KEY = os.getenv("WHOISXML_API_KEY")
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    BING_API_KEY = os.getenv("BING_API_KEY")
    GOOGLE_CX = os.getenv("GOOGLE_CX")

# Create a singleton instance
config = Config()

# Make sure directories exist
config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_INDEX_DIR.mkdir(parents=True, exist_ok=True) 