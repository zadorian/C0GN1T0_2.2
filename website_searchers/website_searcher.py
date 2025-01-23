from typing import Dict, Optional
import traceback
from pathlib import Path
import sys
import asyncio
import os

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


class WebsiteSearcher:
    def __init__(self):
        self.content_controller = ContentController()
        self.archiver = ArchivedContent()

    async def process_command(self, command: str) -> str:
        """
        Main entry for search commands. Three formats supported:
        
        1. Classic format: <searchObject> : <scrapeTarget1>, <scrapeTarget2>, ...
        Examples:
          p! :?sastreconsulting.com/about.html, 2022! ?sastreconsulting.com/about.html   (NER: People on current and 2022 versions)
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
                    print(f"\n=== Processing: {cmd} ===")
                    result = await self.process_command(cmd)
                    all_results.append(result)
                return "\n".join(all_results)
            
            # Single command processing (existing code)
            if ':' in command:
                search_object, scrape_target = command.split(':', 1)
                search_object = search_object.strip()
                scrape_target = scrape_target.strip()
            else:
                search_object, scrape_target = None, command.strip()

            # Get content based on presence of '!'
            content = None
            if '!' in scrape_target:
                print("\nFetching HISTORIC content...")
                if '<-!' in scrape_target:
                    parts = scrape_target.split('<-!')
                    year_part = parts[0].strip() + '<-'
                    url_part = parts[1].strip()
                else:
                    parts = scrape_target.split('!', 1)
                    year_part = parts[0].strip()
                    url_part = parts[1].strip() if len(parts) > 1 else ''

                print(f"Year: {year_part}, URL: {url_part}")
                content = await self.archiver.get_content(
                    url=url_part.lstrip('?'),
                    year=year_part,
                    is_domain_wide=url_part.endswith('?')
                )
            else:
                print("\nFetching CURRENT content...")
                content = await self.content_controller.get_content(scrape_target)

            # If no content, bail
            if not content:
                return "No content found for target URL"

            # If there's a search object, do NER, AI, or keyword
            if search_object:
                # First check if it's a keyword search (in quotes or 1-3 words)
                if (search_object.startswith('"') or search_object.startswith("'") or
                    (0 < len(search_object.split()) <= 3 and not search_object.endswith('!'))):
                    print("\nExecuting keyword search...")
                    return handle_keyword_search(search_object, scrape_target, content)
                    
                # Check if this is an AI query (>3 words not in quotes)
                elif len(search_object.split()) > 3 and not (search_object.startswith('"') or search_object.startswith("'")):
                    print("\nExecuting AI search...")
                    return await handle_ai_search(search_object, content)
                    
                # Handle multiple search types (e.g., "p! c! l!")
                search_types = search_object.split()
                
                # Check if any search type is NER-related
                ner_types = [t for t in search_types if t.rstrip('!') in ['p', 't', 'c', '@', 'e', 'l', 'ent']]
                if ner_types:
                    print(f"\nPerforming NER search for types: {' '.join(ner_types)}")
                    return await handle_ner_extraction(scrape_target, {
                        'ner_type': ' '.join(ner_types),
                        'cached_content': content
                    })
                # AI search?
                elif any(t.startswith('ai') for t in search_types):
                    print("\nExecuting AI search...")
                    return await handle_ai_search(search_object, content)
                else:
                    return f"Unknown search type: {search_object}"
            else:
                # If no search object, just show how many pages
                pages = content.get('pages', []) or content.get('urls', [])
                return f"Retrieved {len(pages)} pages. Use p!, t!, etc. to analyze."

        except Exception as e:
            print(f"Error in website searcher: {str(e)}")
            traceback.print_exc()
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
                    print(f"\nRunning {searcher} on {target}")
                    result = await self.process_command(classic_cmd)
                    all_results.append(f"\n--- {searcher} results ---\n{result}")

            return "\n".join(all_results)

        except Exception as e:
            print(f"Error in multi-searcher command: {str(e)}")
            traceback.print_exc()
            return f"Error: {str(e)}"


async def main():
    print("\nWebsite Search System")
    print("=" * 20)
    print("Format: <searchObject> : <scrapeTarget>\n")
    print("Examples:")
    print("  p! :?sastreconsulting.com/about.html")
    print("  c! :2022!example.com?")
    print("  e! :2020<-!example.org?\n")
    print("Type 'quit' to exit.\n")

    searcher = WebsiteSearcher()
    while True:
        cmd = input("Enter command: ").strip()
        if cmd.lower() == "quit":
            break
        result = await searcher.process_command(cmd)
        print(f"\n{result}\n")


if __name__ == "__main__":
    asyncio.run(main())