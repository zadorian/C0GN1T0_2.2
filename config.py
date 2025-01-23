from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Debug mode (set to False to reduce logging)
    DEBUG = False
    
    # API Keys - Direct assignment instead of environment variables
    OPENAI_API_KEY = "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"
    GEMINI_API_KEY = "AIzaSyApYgmp9_2wNr4txTcRhEoyYALQ6cTlmgQ"
    AZURE_KEY = os.getenv("AZURE_KEY", "")
    AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://nersearch.cognitiveservices.azure.com/")
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
    FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"

    # Paths - SIMPLIFIED
    PROJECT_ROOT = Path(__file__).parent
    CACHE_DIR = PROJECT_ROOT / 'cache'  # Use main cache directory
    MEMORY_DIR = PROJECT_ROOT / 'memory'
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

# Make sure directories exist - NO Content/Cache creation!
config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_INDEX_DIR.mkdir(parents=True, exist_ok=True) 