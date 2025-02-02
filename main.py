import asyncio
import sys
import logging
from pathlib import Path
from typing import Optional
import os
from openai import OpenAI
from utils.logging_config import configure_logging, debug_logger

# Increase recursion limit
sys.setrecursionlimit(10000)  # Default is usually 1000

# Ensure project root is on sys.path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Configure logging
def setup_logging():
    # Create logs directory
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure our custom logging
    configure_logging(logs_dir / "latest.log")

# Import your modules
from website_modules.website_modules import WebsiteModules
from website_searchers.website_searcher import WebsiteSearcher
from scraping_indexing.scraping_indexer import scraping_indexer
from cleanup import cleanup

def get_help_text() -> str:
    """Returns formatted help text for all commands."""
    return """
=== Website Search Commands ===
1. Entity Extraction:
   p! :domain.com?              (Find people)
   c! :domain.com?              (Find companies)
   l! :domain.com?              (Find locations)
   @! :domain.com?              (Find emails)
   t! :domain.com?              (Find phone numbers)
   ent! :domain.com?            (Find all entity types)
   sum! :domain.com?            (Get company summary)

2. Historic Content:
   p! :2022! domain.com?        (Find people from 2022)
   c! :2020<-! domain.com?      (Find companies from 2020)

3. Multi-Searcher Format:
   p!,c!,l! -> domain.com      (Run multiple searchers)
   ai,ner,keyword -> domain.com (Run different search types)

4. Comparison Format:
   p! :domain1.com? =? domain2.com?     (Compare entities between domains)
   p! :2022! domain.com? =? domain.com? (Compare entities over time)

=== Website Analysis Commands ===
bl!<N domain.com?     (Analyze N referring domains)
!bl<N domain.com?     (Show N individual backlinks)
ga! domain.com?       (Check Google Analytics)
whois! domain.com?    (Get WHOIS information)
age! domain.com?      (Get domain age)
alldom! domain.com?   (Get all domain info)

=== Social Media Search Commands ===
keyword :reddit?      (Search Reddit)
keyword :youtube?     (Search YouTube)
keyword :vk?         (Search VKontakte)
keyword :tumblr?     (Search Tumblr)
keyword              (Search all platforms)

Available platform aliases:
- Reddit: :reddit, :reddit.com
- YouTube: :youtube, :youtube.com, :yt
- VKontakte: :vk, :vk.com, :vk.ru, :vkontakte
- Tumblr: :tumblr, :tumblr.com
- Web: :web

=== System Commands ===
reindex! all          (Reindex all cached files)
forget!               (Clean all cache and index files)
help                  (Show this help message)
quit                  (Exit the program)
"""

async def dispatch_command(command: str, wsm: WebsiteModules, wss: WebsiteSearcher) -> str:
    """
    Dispatch command to appropriate module based on prefix or content.
    """
    cmd_lower = command.strip().lower()

    # 1. Handle system commands first
    if cmd_lower.startswith("reindex!"):
        success = scraping_indexer.reindex_all_cached()
        return "Reindex completed" if success else "Reindex failed"
    elif cmd_lower == "forget!":
        cleanup()
        return "Cache and index files cleaned successfully"
    elif cmd_lower == "help":
        return get_help_text()

    # 2. Handle comparison commands
    if "=?" in command:
        from website_searchers.comparison import ComparisonSearcher
        comp = ComparisonSearcher()
        return await comp.handle_comparison_command(command)

    # 3. Check for website_modules commands
    first_token = command.split()[0] if command else ""
    module_prefixes = ["bl!", "!bl", "ga!", "whois!", "age!", "alldom!"]
    if any(first_token.startswith(op) for op in module_prefixes):
        return await wsm.process_command(command)

    # 4. Check for social media platform specific searches
    social_platforms = [':reddit', ':reddit.com', ':youtube', ':youtube.com', ':yt',
                       ':vk', ':vk.com', ':vk.ru', ':vkontakte', ':tumblr', ':tumblr.com']
    if any(platform in cmd_lower for platform in social_platforms):
        from search_engines.socialsearcher import SocialSearcher
        searcher = SocialSearcher()
        searcher.search(command)
        return ""  # Return empty string since searcher handles its own output

    # 5. All other commands go to WebsiteSearcher
    return await wss.process_command(command)

async def main():
    setup_logging()
    wsm = WebsiteModules()
    wss = WebsiteSearcher()

    print("\nUnified Website Analysis CLI")
    print("===========================")
    print("Type 'help' for usage, 'quit' to exit.\n")
    print("Detailed logs are written to logs/latest.log\n")

    while True:
        try:
            command = input("> ").strip()
            if not command:
                continue

            if command.lower() in ["quit", "exit"]:
                break

            if command.lower() == "help":
                print(get_help_text())
                continue

            result = await dispatch_command(command, wsm, wss)
            print(f"\n{result}\n")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit.")
            continue
        except Exception as e:
            logging.error(f"Error: {str(e)}", exc_info=True)
            print(f"\nError occurred. Check logs/latest.log for details.\n")
            continue

if __name__ == "__main__":
    asyncio.run(main())  