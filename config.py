from pathlib import Path
import os

class Config:
    # API Keys - Load from environment variables
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    AZURE_KEY = os.getenv("AZURE_KEY", "")
    AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://nersearch.cognitiveservices.azure.com/")
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
    FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"

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

    # Search Engine APIs - Load from environment variables
    WHOISXML_API_KEY = os.getenv("WHOISXML_API_KEY", "")
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    BING_API_KEY = os.getenv("BING_API_KEY", "")
    GOOGLE_CX = os.getenv("GOOGLE_CX", "")

# Create a singleton instance
config = Config()

# Make sure directories exist
config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_INDEX_DIR.mkdir(parents=True, exist_ok=True) 