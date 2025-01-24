import asyncio
import sys
import logging
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Configure logging
def setup_logging():
    # Create logs directory if it doesn't exist
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure file handler for detailed logs
    file_handler = logging.FileHandler(
        logs_dir / "latest.log",
        mode='w'  # Overwrite the file each time
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    # Configure console handler for progress only
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    # Only show progress messages (no timestamp, level, etc.)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress detailed logs from other libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

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

    # 2. Handle scraping index searcher commands
    if cmd_lower.endswith('???') or cmd_lower.endswith('??'):
        query = cmd_lower.rstrip('?')
        matches = scraping_indexer.search_index(query)
        if cmd_lower.endswith('???'):
            return scraping_indexer.format_raw_results(matches)
        else:
            return scraping_indexer.save_to_memory(query, matches)

    # 3. Check for comparison commands
    if "=?" in command:
        from website_searchers.comparison import ComparisonSearcher
        comp = ComparisonSearcher()
        return await comp.handle_comparison_command(command)

    # 4. Check for website_modules commands
    first_token = command.split()[0] if command else ""
    module_prefixes = ["bl!", "!bl", "ga!", "whois!", "age!", "alldom!"]
    if any(first_token.startswith(op) for op in module_prefixes):
        return await wsm.process_command(command)

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