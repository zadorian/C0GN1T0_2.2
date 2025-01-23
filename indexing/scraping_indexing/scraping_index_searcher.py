from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List
from whoosh import index
from whoosh.qparser import QueryParser
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from AI.gemini_flash import generate_with_retry

# Memory files
MEMORY_DIR = Path(__file__).parent / 'memory'
OPERATIONAL_MEMORY_FILE = MEMORY_DIR / 'operational_memory.json'

# Create directories if needed
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# Initialize operational memory file if it doesn't exist
if not OPERATIONAL_MEMORY_FILE.exists():
    OPERATIONAL_MEMORY_FILE.write_text('[]')

def search_index(query: str) -> List[Dict]:
    """Search the scraping index"""
    index_dir = Path(__file__).parent / 'index'
    print(f"Looking for index in: {index_dir}")
    
    if not index.exists_in(str(index_dir)):
        print("No index found! Please run indexing first.")
        return []
    
    ix = index.open_dir(str(index_dir))
    with ix.searcher() as searcher:
        # Make search case-insensitive
        query_parser = QueryParser("content", ix.schema)
        q = query_parser.parse(query.lower())
        results = searcher.search(q, limit=10)
        
        # Use set to track unique URL+timestamp combinations
        seen = set()
        matches = []
        
        for r in results:
            # Get content and do case-insensitive split
            content = r.get('content', '').lower()
            query_lower = query.lower()
            parts = content.split(query_lower)
            
            # Get original content for display
            original_content = r.get('content', '')
            url = r['url']
            timestamp = r['timestamp']
            
            # Only process this URL+timestamp combination if we haven't seen it
            key = f"{url}_{timestamp}"
            if key not in seen:
                seen.add(key)
                
                # Find the first good match in the content
                for i in range(len(parts)-1):
                    start_pos = len(parts[i])
                    end_pos = start_pos + len(query)
                    original_match = original_content[start_pos:end_pos]
                    
                    context = {
                        'before': original_content[max(0, start_pos-500):start_pos],
                        'match': original_match,
                        'after': original_content[end_pos:end_pos+500]
                    }
                    
                    matches.append({
                        'url': url,
                        'timestamp': timestamp,
                        'context': context,
                        'score': r.score
                    })
                    # Only take the first match from this document
                    break
            
        return matches

def format_raw_results(matches: List[Dict]) -> str:
    """Format raw search results with extended context"""
    output = []
    for match in matches:
        # Convert timestamp to readable date
        try:
            ts = match['timestamp']
            if len(ts) >= 8:  # Basic validation
                date = datetime.strptime(ts[:8], '%Y%m%d')
                date_str = date.strftime('%d %B %Y')
            else:
                date_str = "Unknown Date"
        except Exception:
            date_str = "Unknown Date"
            
        # Format URL and date with spacing
        output.append(f"\n{match['url']} [{date_str}]\n")  # Added newline after date
        
        # Clean up the context by removing excessive whitespace and line breaks
        before = ' '.join(match['context']['before'].split())
        after = ' '.join(match['context']['after'].split())
        
        output.append(f"...{before}")
        output.append(f"**{match['context']['match']}**")
        output.append(f"{after}...")
        output.append("-" * 80)  # Separator line
    return "\n".join(output)

def save_to_memory(query: str, matches: List[Dict]) -> str:
    """Save search results to memory and return AI analysis"""
    try:
        # Load existing memory
        memory_data = []
        if OPERATIONAL_MEMORY_FILE.exists():
            memory_data = json.loads(OPERATIONAL_MEMORY_FILE.read_text())
        
        # Create new memory entry
        memory_entry = {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'results': matches
        }
        memory_data.append(memory_entry)
        
        # Save updated memory
        OPERATIONAL_MEMORY_FILE.write_text(json.dumps(memory_data, indent=2))
        
        # Get AI analysis with improved prompt
        context = json.dumps(matches, indent=2)
        prompt = f"""Analyze ALL search results for query: "{query}"

        IMPORTANT: Always start your analysis by stating the date range of the information (e.g., "Based on data from March 2021 to November 2023").

        For each distinct match:
        1. Who/what is it? (name, role, location, etc.)
        2. What is their context? (company, position, responsibilities)
        3. What are their connections to other matches?
        4. What unique information is provided about them?
        5. When was this information valid? (specify dates)

        Then provide:
        1. Patterns and relationships between different matches
        2. Common themes or connections
        3. Potential areas for further investigation
        4. Any inconsistencies or gaps in the information
        5. Timeline of any changes or developments

        Results: {context}
        """
        
        return generate_with_retry(prompt)
        
    except Exception as e:
        print(f"Error in memory processing: {str(e)}")
        return format_raw_results(matches)

def main():
    query = input("Enter search query (end with ??? for raw results, ?? for AI analysis): ")
    
    if query.endswith('???'):
        query = query[:-3].strip()
        matches = search_index(query)
        print(format_raw_results(matches))
    elif query.endswith('??'):
        query = query[:-2].strip()
        matches = search_index(query)
        print(save_to_memory(query, matches))
    else:
        print("Please end your query with ??? for raw results or ?? for AI analysis")

if __name__ == "__main__":
    main()
