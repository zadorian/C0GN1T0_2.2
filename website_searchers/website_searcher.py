from typing import Dict, Optional
import traceback
from pathlib import Path
import sys
import asyncio
import os
import logging
from prompts import get_company_summary_prompt

#
# 1) HACK: Insert paths so that "scrapers", "caching", and "indexing" 
#    become visible as top-level modules, just like archived_scraping.py expects.
#
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # e.g. "C.0.G.N.1.T.0.2.2" folder
scraping_folder = project_root / "scraping"  # Contains "scrapers/", "caching/"
indexing_folder = project_root / "indexing"  # If archived_scraping references indexing

if scraping_folder.is_dir():
    sys.path.insert(0, str(scraping_folder))
if indexing_folder.is_dir():
    sys.path.insert(0, str(indexing_folder))

# Optionally insert the project root, in case you need other modules
sys.path.insert(0, str(project_root))

#
# 2) Import from your existing archived_scraping/current_scraping
#
from scraping.archived_scraping import ArchivedContent
from scraping.current_scraping import ContentController
from scraping.caching.scrape_caching import content_cache

# 3) Import your NER, AI, and keyword searches
from website_searchers.ner_searcher import handle_ner_extraction
from website_searchers.ai_searcher import handle_ai_search
from website_searchers.keyword_searcher import handle_keyword_search

# At the top of the file, after imports
# Create module-level loggers with specific purposes
debug_logger = logging.getLogger('websearch_debug')
content_logger = logging.getLogger('content')
api_logger = logging.getLogger('api')
progress_logger = logging.getLogger('progress')

class WebsiteSearcher:
    def __init__(self):
        self.content_controller = ContentController()
        self.archiver = ArchivedContent()
        
        # Configure loggers for minimal output
        for logger in [debug_logger, content_logger, api_logger, progress_logger]:
            logger.propagate = False
            logger.handlers = []
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.WARNING)  # Default to WARNING
        
        # Only debug_logger shows DEBUG messages
        debug_logger.setLevel(logging.DEBUG)

    async def process_command(self, command: str) -> str:
        """
        Main entry for search commands. Three formats supported:
        
        1. Classic format: <searchObject> : <scrapeTarget1>, <scrapeTarget2>, ...
        Examples:
          p! :?sexample.com/about.html, 2022! ?example.com/about.html   (NER: People on current and 2022 versions)
          c! :2022! example.com?, 2023! example.com?                                      (NER: Companies from two different years)
          p! c! l! :domain.com?, otherdomain.com?                                        (Multiple entity types on multiple domains)
        
        2. Multi-searcher format: <searcher1>,<searcher2>,... -> <target1>, <target2>, ...
        Examples:
          ai,ner,keyword -> example.com, example.org/page.html
          p!,c!,l! -> domain.com, 2022! otherdomain.com

        3. Comparison format: <searchObject> : <target1> =? <target2> =? <target3> ...
        Examples:
          products sold by the company? :company1.com? =? company2.com?
          p! :company1.com! =? company2.com?
        """
        try:
            command = ''.join(char for char in command if ord(char) >= 32)
            
            # Replace all logging calls with debug_logger
            if ':' in command:
                search_object, scrape_target = command.split(':', 1)
                debug_logger.debug("\nDEBUG: Split command into:")
                debug_logger.debug(f"- Search object: '{search_object.strip()}'")
                debug_logger.debug(f"- Scrape target: '{scrape_target.strip()}'\n")

                # Add URL evaluation logging
                debug_logger.debug("\nEvaluating target URLs:")
                if ',' in scrape_target:
                    urls = [url.strip() for url in scrape_target.split(',')]
                    for url in urls:
                        debug_logger.debug(f"- Will check: {url}")
                else:
                    debug_logger.debug(f"- Will check: {scrape_target.strip()}")

                # Add search type logging
                debug_logger.debug("\nDetermining search type:")
                if search_object.startswith('sum!'):
                    debug_logger.debug("- Company summary search selected")
                elif search_object.startswith(('p!', 'c!', 'l!', '@!', 't!', 'ent!')):
                    debug_logger.debug("- Entity extraction search selected")
                elif search_object.startswith(('bl!', '!bl')):
                    debug_logger.debug("- Backlink analysis selected")
                debug_logger.debug("")  # Empty line for readability

            # Check if this is a comparison command (using =?)
            if '=?' in command:
                from website_searchers.comparison import ComparisonSearcher
                comparison_searcher = ComparisonSearcher()
                return await comparison_searcher.handle_comparison_command(command)
            
            # Check if this is a multi-searcher command (using arrow)
            if '->' in command:
                return await self._handle_multi_searcher_command(command)
            
            # If there's a comma, split into multiple commands and run each
            if ',' in command and ':' in command:
                search_object, targets = command.split(':', 1)
                search_object = search_object.strip()
                
                # Split targets and create individual commands
                all_results = []
                for target in targets.split(','):
                    target = target.strip()
                    cmd = f"{search_object}:{target}"
                    debug_logger.info(f"\n=== Processing: {cmd} ===")
                    result = await self.process_command(cmd)
                    all_results.append(result)
                return "\n".join(all_results)
            
            # Single command processing (existing code)
            if ':' in command:
                search_object, scrape_target = command.split(':', 1)
                search_object = search_object.strip()
                scrape_target = scrape_target.strip()
            else:
                # For comparison commands, we need to handle each part separately
                if '=?' in command:
                    parts = command.split('=?')
                    first_part = parts[0].strip()
                    if ':' in first_part:
                        search_object, scrape_target = first_part.split(':', 1)
                    else:
                        search_object, scrape_target = None, first_part
                else:
                    search_object, scrape_target = None, command.strip()

            # Get content with minimal output
            content = None
            if '!' in scrape_target:
                progress_logger.info("\nRetrieving archived content...")
                content = await self._get_archived_content(scrape_target)
                progress_logger.info(" done")
            else:
                progress_logger.info("\nRetrieving current content...")
                content = await self.content_controller.get_content(scrape_target)
                progress_logger.info(" done")

            # If no content, bail
            if not content:
                return "No content found for target URL"

            # Replace all logging.info calls
            if search_object:
                if (search_object.startswith('"') or search_object.startswith("'") or
                    (0 < len(search_object.split()) <= 3 and not search_object.endswith('!'))):
                    debug_logger.info("\nExecuting keyword search...")
                    return handle_keyword_search(search_object, scrape_target, content)
                    
                elif len(search_object.split()) > 3 and not (search_object.startswith('"') or search_object.startswith("'")):
                    debug_logger.info("\nExecuting AI search...")
                    return await handle_ai_search(search_object, content)
                    
                # Handle multiple search types (e.g., "p! c! l!")
                search_types = search_object.split()
                
                # Check if any search type is NER-related
                ner_types = [t for t in search_types if t.rstrip('!') in ['p', 't', 'c', '@', 'e', 'l', 'ent']]
                if ner_types:
                    debug_logger.info(f"\nPerforming NER search for types: {' '.join(ner_types)}")
                    return await handle_ner_extraction(scrape_target, {
                        'ner_type': ' '.join(ner_types),
                        'cached_content': content
                    })
                # AI search?
                elif any(t.startswith('ai') for t in search_types):
                    debug_logger.info("\nExecuting AI search...")
                    return await handle_ai_search(search_object, content)
                # Check if it's a summary request
                elif any(t.strip('!') in ['sum', 'summarize', 'summarise'] for t in search_types):
                    debug_logger.info("\nExecuting company summary search...")
                    # Get the specialized summary prompt from prompts.py
                    summary_prompt = get_company_summary_prompt()
                    # Use the existing AI search with our summary prompt
                    return await handle_ai_search(summary_prompt, content)
                else:
                    return f"Unknown search type: {search_object}"
            else:
                # If no search object, just show how many pages
                pages = content.get('pages', []) or content.get('urls', [])
                return f"Retrieved {len(pages)} pages. Use p!, t!, etc. to analyze."

        except Exception as e:
            debug_logger.error(f"Error in website searcher: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

    async def _handle_multi_searcher_command(self, command: str) -> str:
        """Handle the new multi-searcher command format."""
        try:
            # Parse command: "p!,c!,l! -> example.com, example.org"
            parts = command.split("->")
            if len(parts) != 2:
                return "Invalid command format. Expected: searcher1,searcher2,... -> target1, target2, ..."

            searchers_part = parts[0].strip()
            targets_part = parts[1].strip()

            # Split searchers and targets
            searchers = [s.strip() for s in searchers_part.split(",") if s.strip()]
            targets = [t.strip() for t in targets_part.split(",") if t.strip()]

            if not searchers or not targets:
                return "No searchers or targets found"

            # Process each target with each searcher
            all_results = []
            for target in targets:
                all_results.append(f"\n=== Target: {target} ===")
                for searcher in searchers:
                    # Convert searcher to classic format and run
                    classic_cmd = f"{searcher}:{target}"
                    debug_logger.info(f"\nRunning {searcher} on {target}")
                    result = await self.process_command(classic_cmd)
                    all_results.append(f"\n--- {searcher} results ---\n{result}")

            return "\n".join(all_results)

        except Exception as e:
            debug_logger.error(f"Error in multi-searcher command: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

    async def _get_archived_content(self, scrape_target: str) -> Dict:
        # Implementation of _get_archived_content method
        # This method should return the content from the archived content
        # based on the scrape_target.
        # It should return a dictionary containing the content data.
        # This is a placeholder and should be implemented based on your specific requirements.
        return {}

async def main():
    print("\nWebsite Search System")
    print("=" * 20)
    print("Format: <searchObject> : <scrapeTarget>\n")
    print("Examples:")
    print("  p! :?example.com/about.html")
    print("  c! :2022!example.com?")
    print("  e! :2020<-!example.org?\n")
    print("Type 'quit' to exit.\n")

    searcher = WebsiteSearcher()
    while True:
        try:
            command = input("Enter command: ").strip()
            if command.lower() == "quit":
                break

            result = await searcher.process_command(command)
            print(f"\n{result}\n")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit.")
            continue
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            continue

if __name__ == "__main__":
    # Silence everything by default
    logging.basicConfig(
        level=logging.WARNING,
        format='%(message)s',
        handlers=[logging.NullHandler()]
    )
    
    # Explicitly silence ALL loggers except ours
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        logger.handlers = [logging.NullHandler()]
    
    # Only show essential startup info
    print("\nCache checker initialized at:", project_root / "cache")
    from config import OPENAI_API_KEY
    print(f"\nDEBUG: Using OpenAI API Key: {OPENAI_API_KEY[:10]}...")
    
    asyncio.run(main())