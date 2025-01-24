import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Optional

# Make sure we can import from project root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import the module functions with relative imports
from .backlinks import handle_backlinks_analysis, handle_more_command
from .google_analytics import handle_ga_command
from .whois import handle_whois_command
from .age import handle_age_command
from .allDom import handle_alldom_command

class WebsiteModules:
    """
    Handles commands for various website analysis modules:
    - Backlinks analysis (bl!, !bl)
    - Google Analytics (ga!)
    - WHOIS information (whois!)
    - Domain age (age!)
    - All domain info (alldom!)
    """

    async def process_command(self, command: str) -> str:
        """Main entry point for processing website module commands."""
        try:
            cmd_lower = command.lower().strip()
            first_token = cmd_lower.split()[0]

            if first_token in ["bl!", "!bl"]:
                return await handle_backlinks_analysis(command)
            elif first_token == "ga!":
                return await handle_ga_command(command)
            elif first_token == "whois!":
                return await handle_whois_command(command)
            elif first_token == "age!":
                return await handle_age_command(command)
            elif first_token == "alldom!":
                return await handle_alldom_command(command)
            else:
                return f"Unknown command: {first_token}"

        except Exception as e:
            print(f"Error in website modules: {str(e)}")
            return f"Error: {str(e)}"

    def get_help(self) -> str:
        """Return help text for website module commands."""
        return """
Website Module Commands:
  bl! domain.com?     - Analyze backlinks
  !bl domain.com?     - Alternative backlink syntax
  ga! domain.com?     - Check Google Analytics
  whois! domain.com?  - Get WHOIS information
  age! domain.com?    - Get domain age
  alldom! domain.com? - Get all domain info
"""

async def main():
    """CLI interface for testing."""
    modules = WebsiteModules()
    
    print("\nWebsite Analysis Modules")
    print("Type 'help' for command syntax or 'quit' to exit")
    print("=" * 50)

    while True:
        command = input("\nEnter command: ").strip()
        
        if command.lower() == 'quit':
            break
        elif command.lower() == 'help':
            print(modules.get_help())
            continue
            
        result = await modules.process_command(command)
        print(f"\n{result}")

if __name__ == "__main__":
    asyncio.run(main())