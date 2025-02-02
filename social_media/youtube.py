import requests
from datetime import datetime
import re

def parse_input(user_input):
    """
    Parse inputs like:
    2022! trump            (specific year)
    2022-2023! biden       (year range)
    2023-> election        (from year onwards)
    <-2023 politics        (up to year)
    >> news               (most recent)
    << history           (oldest)
    """
    user_input = user_input.strip()
    
    # Check for recent/oldest patterns first
    if user_input.startswith('>>'):
        return '>>', user_input[2:].strip()
    elif user_input.startswith('<<'):
        return '<<', user_input[2:].strip()
    
    # Patterns for date ranges
    patterns = [
        r'^(\d{4}!)\s+(.+)$',             # 2022! keyword
        r'^(\d{4}-\d{4}!)\s+(.+)$',       # 2022-2023! keyword
        r'^(\d{4}->)\s+(.+)$',            # 2023-> keyword
        r'^(<-\d{4})\s+(.+)$'             # <-2023 keyword
    ]
    
    for pattern in patterns:
        match = re.match(pattern, user_input)
        if match:
            return match.group(1), match.group(2)
    
    return None, None

def parse_date_pattern(pattern):
    """Parse date patterns into start and end dates"""
    if pattern == '>>' or pattern == '<<':
        return None, None
        
    if pattern.endswith('!'):  # Specific year or range
        years = pattern[:-1].split('-')
        if len(years) == 1:  # Single year (2022!)
            start = f"{years[0]}-01-01"
            end = f"{years[0]}-12-31"
        else:  # Year range (2022-2023!)
            start = f"{years[0]}-01-01"
            end = f"{years[1]}-12-31"
    
    elif pattern.endswith('->'):  # From year onwards
        year = pattern[:-2]
        start = f"{year}-01-01"
        end = datetime.now().strftime('%Y-%m-%d')
        
    elif pattern.startswith('<-'):  # Up to year
        year = pattern[2:]
        start = "2000-01-01"
        end = f"{year}-12-31"
        
    else:
        raise ValueError("Invalid date pattern")
        
    return start, end

def search_youtube(query, date_pattern):
    """Search YouTube content with date range and/or sorting"""
    api_key = 'decdab3ea83f1df1c6386f620a6ca72f'
    base_url = 'https://api.social-searcher.com/v2/search'
    
    params = {
        'q': query,
        'key': api_key,
        'network': 'youtube'
    }
    
    # Add date period if it's a date pattern
    if date_pattern not in ['>>', '<<']:
        start_date, end_date = parse_date_pattern(date_pattern)
        if start_date and end_date:
            params['period'] = f"{start_date},{end_date}"
            print(f"\nSearching YouTube from {start_date} to {end_date}")
    else:
        print(f"\nSearching YouTube for {'most recent' if date_pattern == '>>' else 'oldest'} results")
        # Add sort parameter
        params['sort'] = 'date' if date_pattern == '>>' else '-date'
    
    print(f"Query: {query}")
    
    try:
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'posts' in data and data['posts']:
                print(f"\nFound {len(data['posts'])} results:")
                
                for post in data['posts']:
                    print("\n" + "="*70)
                    
                    # Format the posted date
                    posted_date = post.get('posted')
                    if posted_date:
                        try:
                            if isinstance(posted_date, str):
                                date_obj = datetime.fromisoformat(posted_date.replace('Z', '+00:00'))
                            else:
                                date_obj = datetime.fromtimestamp(posted_date)
                            print(f"Posted: {date_obj.strftime('%Y-%m-%d %H:%M:%S')}")
                        except (ValueError, TypeError):
                            print(f"Posted: {posted_date}")
                    
                    if post.get('user', {}).get('name'):
                        print(f"Channel: {post['user']['name']}")
                        
                    print("\nTitle/Content:")
                    print("-" * 50)
                    print(post.get('text', 'No content'))
                    print("-" * 50)
                    
                    if post.get('url'):
                        print(f"URL: {post['url']}")
                    
                    print("="*70)
            else:
                print("No results found")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    print("YouTube Content Search")
    print("Format examples:")
    print("  2022! trump            - specific year")
    print("  2022-2023! biden       - year range")
    print("  2023-> election        - from 2023 onwards")
    print("  <-2023 politics        - up to 2023")
    print("  >> news               - most recent")
    print("  << history           - oldest")
    print("=" * 40)
    
    while True:
        user_input = input("\nEnter search (or 'quit'): ").strip()
        if user_input.lower() == 'quit':
            break
            
        date_pattern, query = parse_input(user_input)
        
        if not date_pattern or not query:
            print("Invalid format! Use examples shown above.")
            continue
            
        try:
            search_youtube(query, date_pattern)
        except ValueError as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()