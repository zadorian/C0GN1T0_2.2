"""
Website Modules Package
Contains modules for various website analysis tasks:
- Backlinks analysis
- Google Analytics detection
- WHOIS information
- Domain age analysis
- All domain info
"""

from .website_modules import WebsiteModules

__all__ = ['WebsiteModules']

# Make the directory a Python package
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Use absolute imports
from website_modules.backlinks import handle_backlinks_analysis, handle_more_command
from website_modules.whois import handle_whois_command
from website_modules.google_analytics import check_analytics
from website_modules.age.age import analyze_url as analyze_age

# Export the functions
__all__ = [
    'handle_backlinks_analysis',
    'handle_more_command',
    'handle_whois_command',
    'check_analytics',
    'analyze_age'
] 