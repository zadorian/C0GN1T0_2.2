from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        # Debug mode (set to False to reduce logging)
        self.DEBUG = False
        
        # API Keys - load all from environment variables with fallbacks
        self.OPENAI_API_KEY = (
            os.getenv("OPENAI_API_KEY") or 
            "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"
        )
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.AZURE_KEY = os.getenv("AZURE_KEY", "7a7c3b1f5e9d4f2b8e6a0c4d2b1f3e5a")
        self.AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://eye-ai.cognitiveservices.azure.com/")
        self.FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
        self.FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL")
        self.AHREFS_API_KEY = os.getenv("AHREFS_API_KEY")
        self.WHOISXML_API_KEY = os.getenv("WHOISXML_API_KEY")
        self.BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.BING_API_KEY = os.getenv("BING_API_KEY")
        self.GOOGLE_CX = os.getenv("GOOGLE_CX")
        self.CH_API_KEY = os.getenv("CH_API_KEY")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        self.OPENCORPORATES_API_KEY = os.getenv("OPENCORPORATES_API_KEY")
        self.EXA_API_KEY = os.getenv("EXA_API_KEY", "ecd713df-48c2-4fb7-b99a-55f3472478b1")
        self.ALEPH_API_KEY = "1c0971afa4804c2aafabb125c79b275e"  # Hardcoded as it's public
            
        # Debug prints
        print("\nDebug: Environment variables check:")
        print(f"OPENAI_API_KEY exists: {'OPENAI_API_KEY' in os.environ}")
        print(f"Using OpenAI API Key: {self.OPENAI_API_KEY[:10]}...")
        print(f"ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")
        print(f"ANTHROPIC_API_KEY value: {os.getenv('ANTHROPIC_API_KEY')}")
        print(f"CH_API_KEY exists: {'CH_API_KEY' in os.environ}")
        print(f"CH_API_KEY value: {os.getenv('CH_API_KEY')}")
        print(f"OPENCORPORATES_API_KEY exists: {'OPENCORPORATES_API_KEY' in os.environ}")
        print(f"OPENCORPORATES_API_KEY value: {os.getenv('OPENCORPORATES_API_KEY')}")
        print(f"EXA_API_KEY exists: {'EXA_API_KEY' in os.environ}")
        print(f"EXA_API_KEY value: {os.getenv('EXA_API_KEY')}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"All environment variables: {list(os.environ.keys())}")
        
        # Verify API key format
        if not self.OPENAI_API_KEY.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format")
            
        # Verify required API keys
        if not self.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        if not self.CH_API_KEY:
            raise ValueError("CH_API_KEY not found in environment variables")
        if not self.OPENCORPORATES_API_KEY:
            raise ValueError("OPENCORPORATES_API_KEY not found in environment variables")
        
        # Paths
        self.PROJECT_ROOT = Path(__file__).parent
        self.CONTENT_DIR = self.PROJECT_ROOT / 'Content'
        self.CACHE_DIR = self.CONTENT_DIR / 'Cache'
        self.MEMORY_DIR = self.PROJECT_ROOT / 'memory'

        # Memory settings
        self.MEMORY_INDEX_DIR = self.MEMORY_DIR / 'Index'
        self.OPERATIONAL_MEMORY_FILE = self.MEMORY_DIR / 'operational_memory.json'

        # Name variations for entity matching
        self.NAME_VARIATIONS = {
            'anthony': ['tony', 'ant'],
            'stephen': ['steve', 'steph'],
            'marton': ['marci', 'marti'],
            'tamas': ['tom', 'tommy'],
            'barnabas': ['barni', 'barney'],
            'domonkos': ['dom', 'domi'],
            'andras': ['andy', 'andi']
        }

# Create a singleton instance
config = Config()

# Make sure directories exist
config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
config.MEMORY_INDEX_DIR.mkdir(parents=True, exist_ok=True)