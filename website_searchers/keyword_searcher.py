from typing import List, Dict, Optional
import traceback
from collections import defaultdict
import re
from datetime import datetime

# If your scenario is indeed in `Tags/scenarios/`, keep this:
from Tags.scenarios.scenario_keyword_search import KeywordSearchScenario


def handle_keyword_search(keyword: str, domain: str, content: Dict) -> str:
    """Handle keyword-based search"""
    try:
        print("\n=== SEARCH PROCESS ===")
        print("Search parameters:")
        print(f"- Keyword: {keyword}")
        print(f"- Domain: {domain}")
        
        matches = []
        results_for_tags = []  # Store results for tag creation
        urls_found = set()
        
        # Support both historic and current content structures
        pages_data = content.get('pages', []) or content.get('urls', [])
        if not pages_data:
            return "No content found to search"
            
        pattern = re.compile(keyword, re.IGNORECASE)
        seen_paragraphs = set()
        
        for page in pages_data:
            url = page.get('url', '')
            text_content = (page.get('content', '') or 
                            page.get('raw_text', '') or 
                            page.get('text', ''))
            timestamp = page.get('timestamp', '')
            
            if not text_content:
                continue
                
            paragraphs = text_content.split('\n\n')
            url_matches = []
            
            for idx, paragraph in enumerate(paragraphs):
                if pattern.search(paragraph):
                    clean_para = re.sub(r'\s+', ' ', paragraph.strip())
                    if clean_para in seen_paragraphs:
                        continue
                    seen_paragraphs.add(clean_para)
                    
                    # Store result for tag creation
                    results_for_tags.append({
                        'url': url,
                        'context': clean_para,
                        'timestamp': timestamp or datetime.now().isoformat()
                    })
                    
                    # Build snippet with some preceding/following paragraphs
                    context = []
                    context.append("\n=== MATCH FOUND ===\n")
                    if timestamp:
                        context.append(f"Date: {timestamp[:8]}\n")
                    
                    start_idx = max(0, idx - 2)
                    for i in range(start_idx, idx):
                        prev_para = paragraphs[i].strip()
                        if prev_para:
                            context.append(prev_para)
                    
                    # Highlight the matched keyword
                    highlighted = re.sub(pattern, lambda m: f"**{m.group(0)}**", clean_para)
                    context.append(f"\n{highlighted}\n")
                    
                    end_idx = min(len(paragraphs), idx + 3)
                    for i in range(idx + 1, end_idx):
                        next_para = paragraphs[i].strip()
                        if next_para:
                            context.append(next_para)
                    
                    context.append("\n" + "=" * 50 + "\n")
                    url_matches.append("\n".join(context))
            
            if url_matches:
                urls_found.add(url)
                matches.append(f"\n\nURL: {url}")
                matches.append("=" * (len(url) + 5))
                matches.extend(url_matches)

        # Determine search type from metadata
        search_type = "current_page"
        if content.get('metadata'):
            if content['metadata'].get('source') == 'archived':
                search_type = "historic_page"
            if content['metadata'].get('is_domain_wide'):
                search_type = search_type.replace('page', 'domain')

        # Create tags using scenario
        if results_for_tags:
            scenario = KeywordSearchScenario()
            scenario.process(
                query=f"{keyword} :{domain}",
                results=results_for_tags,
                search_type=search_type
            )
        
        print(f"\nFound matches in {len(urls_found)} URLs")
        return "\n".join(matches) if matches else "No matches found"
        
    except Exception as e:
        print(f"Error in keyword search: {str(e)}")
        traceback.print_exc()
        return f"Error: {str(e)}"


def is_keyword_search(command: str) -> bool:
    """
    Check if the given command is a keyword search.
    (Optional utility, not strictly required.)
    """
    if '"' in command:
        return True
    words = [w for w in command.split() if w != '?']
    return 0 < len(words) <= 3