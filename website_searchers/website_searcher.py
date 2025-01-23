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
        Main entry for search commands: <searchObject> : <scrapeTarget>
        
        Examples:
          p! :?sastreconsulting.com/about.html   (NER: People on current single page)
          c! :2022!example.com?                  (NER: Companies on archived domain)
          p! c! l! :domain.com?                  (Multiple entity types)
          ent! :domain.com?                      (All entity types)
        """
        try:
            # 1) Split on ':'
            if ':' in command:
                search_object, scrape_target = command.split(':', 1)
                search_object = search_object.strip()
                scrape_target = scrape_target.strip()
                print(f"DEBUG: Split command into:")
                print(f"- Search object: '{search_object}'")
                print(f"- Scrape target: '{scrape_target}'")
            else:
                search_object, scrape_target = None, command.strip()

            # 2) Get content based on presence of '!'
            content = None
            if '!' in scrape_target:
                print("\nFetching HISTORIC content...")
                if '<-!' in scrape_target:
                    parts = scrape_target.split('<-!')
                    year_part = parts[0].strip() + '<-' if parts[0].strip() else '<-'
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

            # 3) If no content, bail
            if not content:
                return "No content found for target URL"

            # 4) Determine search type and execute
            if search_object:
                # Check if this is an AI query (>3 words not in quotes)
                words = search_object.split()
                if len(words) > 3 and not (search_object.startswith('"') or search_object.startswith("'")):
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
                # Keyword search
                else:
                    return handle_keyword_search(search_types[0], scrape_target, content)
            
            # If no search object, just show how many pages
            pages = content.get('pages', []) or content.get('urls', [])
            return f"Retrieved {len(pages)} pages. Use p!, t!, etc. to analyze."

        except Exception as e:
            print(f"Error in website searcher: {str(e)}")
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