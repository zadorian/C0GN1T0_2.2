# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# WARNING: This file MUST use gpt-4o-mini as the model name.
# DO NOT CHANGE THIS UNDER ANY CIRCUMSTANCES!
# The model name must remain "gpt-4o-mini" for all OpenAI API calls!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

from typing import Dict, Optional, List, Any
import traceback
import sys
import time
import re
from pathlib import Path
from utils.logging_config import debug_logger, progress_logger

# -----------------------------------------------------------------------------
# Project Imports
# -----------------------------------------------------------------------------
# Add project root to path if needed
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# External libs
from openai import OpenAI
import google.generativeai as genai

# Local config
from config import config

# -----------------------------------------------------------------------------
# Initialize Clients
# -----------------------------------------------------------------------------
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url="https://api.openai.com/v1"
)

# WARNING: DO NOT MODIFY THE MODEL NAME BELOW!
MODEL_NAME = "gpt-4o-mini"  # This must stay as gpt-4o-mini - DO NOT CHANGE!

print(f"DEBUG: Using OpenAI API Key: {config.OPENAI_API_KEY[:10]}...")  # Print first 10 chars for security

# Also init Gemini if you need it
genai.configure(api_key=config.GEMINI_API_KEY)


# -----------------------------------------------------------------------------
# (Optional) Gemini generator function
# -----------------------------------------------------------------------------
def generate_with_gemini(prompt: str, max_retries: int = 3, delay: float = 1.0) -> Optional[str]:
    """Generate content using Gemini with retry logic"""
    model = genai.GenerativeModel('gemini-pro')
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            else:
                print(f"Empty Gemini response on attempt {attempt + 1}")
                
        except Exception as e:
            print(f"Gemini attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                print("Max retries reached for Gemini")
                return None
                
    return None


# -----------------------------------------------------------------------------
# Existing SINGLE-PASS approach (unchanged)
# -----------------------------------------------------------------------------
async def analyze_with_ai(query: str, batch_text: List[str], domain: str, chunk_range: str) -> Optional[str]:
    """Try both GPT-4 and Gemini for analysis, fall back as needed"""
    
    analysis_prompt = f"""Based ONLY on this content chunk, answer: {query}

Content from {domain} ({chunk_range}):
{chr(10).join(batch_text)}

Important:
1. Only use facts from this content
2. Note any changes over time
3. Include timestamps
4. Say "No relevant information" if nothing found
5. Be concise
6. List the exact URLs where information was found
7. When analyzing staff/employees, note any gender indicators including names
8. Look for mentions of team members, management, staff counts, and their descriptions
"""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{
                "role": "system",
                "content": "You are a helpful AI assistant analyzing website content. Always cite the specific URLs where you found information."
            }, {
                "role": "user",
                "content": analysis_prompt
            }]
        )
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"\nGPT-4 analysis failed: {str(e)}")
        print("Falling back to Gemini...")
        
        # Fall back to Gemini - fixed the f-string backslash issue
        gemini_prompt = f"""Carefully analyze this content to answer: {query}

Content from {domain} ({chunk_range}):
{chr(10).join(batch_text)}

Important:
1. Only use facts from this content
2. Note any changes over time
3. Include timestamps
4. List the exact URLs where information was found"""
        
        gemini_response = generate_with_gemini(gemini_prompt)
        if gemini_response:
            return gemini_response
        else:
            print("Both GPT-4 and Gemini failed to analyze content")
            return None


def _score_page_relevance(url: str, content: str, search_type: str = 'company') -> float:
    """Score a page's relevance for different search types"""
    score = 0.0
    url = url.lower()
    
    # Base relevance patterns for company information
    high_value_patterns = {
        'url': {
            'company': ['about', 'company', 'overview', 'profile', 'history'],
            'people': ['team', 'people', 'management', 'leadership', 'staff'],
            'products': ['products', 'services', 'solutions', 'offerings'],
            'contact': ['contact', 'locations', 'offices']
        },
        'content': {
            'company': ['founded', 'established', 'history', 'mission', 'vision'],
            'people': ['ceo', 'president', 'director', 'board', 'management'],
            'products': ['provide', 'offer', 'deliver', 'product', 'service'],
            'contact': ['email', 'phone', 'address', 'contact']
        }
    }

    # Score based on URL patterns
    for pattern in high_value_patterns['url'].get(search_type, []):
        if pattern in url:
            score += 2.0
            debug_logger.debug(f"URL boost (+2.0) for '{pattern}' in {url}")

    # Penalize deep URLs
    depth = url.count('/')
    penalty = depth * 0.5
    score -= penalty
    if penalty > 0:
        debug_logger.debug(f"Depth penalty (-{penalty}) for {url}")

    # Penalize obviously irrelevant pages
    irrelevant = ['assets/', 'images/', 'css/', 'js/', '.pdf', '.jpg', '.png']
    for pattern in irrelevant:
        if pattern in url:
            score -= 5.0
            debug_logger.debug(f"Irrelevant content penalty (-5.0) for {url}")
            break

    # Score based on content patterns (if content is provided)
    if content:
        content = content.lower()
        for pattern in high_value_patterns['content'].get(search_type, []):
            if pattern in content:
                score += 1.0
                debug_logger.debug(f"Content boost (+1.0) for '{pattern}' in {url}")

    return score


async def handle_ai_search(prompt: str, content: Dict) -> str:
    """Handle AI-based analysis of website content"""
    try:
        debug_logger.debug("\nStarting handle_ai_search")
        
        # Get pages from content
        pages = content.get('pages', [])
        if not pages:
            return "No pages found to analyze"

        # Score and sort pages
        scored_pages = []
        for page in pages:
            url = page.get('url', '')
            page_content = page.get('content', '')
            score = _score_page_relevance(url, page_content, 'company')
            scored_pages.append((score, page))

        # Sort by score and take top N most relevant pages
        MAX_PAGES = 5  # Adjust this number based on your needs
        scored_pages.sort(reverse=True, key=lambda x: x[0])
        selected_pages = scored_pages[:MAX_PAGES]

        # Log page selection process
        debug_logger.debug(f"\nPage Selection Process:")
        debug_logger.debug(f"Total pages available: {len(pages)}")
        debug_logger.debug(f"Selected top {MAX_PAGES} most relevant pages:")
        for score, page in selected_pages:
            debug_logger.debug(f"- {page['url']} (score: {score:.1f})")

        # Process selected pages
        results = []
        for i, (score, page) in enumerate(selected_pages, 1):
            url = page.get('url', '')
            content = page.get('content', '')
            
            if not content:
                debug_logger.debug(f"Skipping empty page: {url}")
                continue

            progress_logger.info(f"\nAnalyzing page {i}/{len(selected_pages)}")
            progress_logger.info(f"URL: {url}")
            progress_logger.info(f"Content length: {len(content)} chars")

            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{
                        "role": "system",
                        "content": """You are a highly analytical AI assistant. When analyzing content:
                        1. Think deeply about the question being asked
                        2. Look for both direct and indirect evidence
                        3. Use logic and reasoning to draw conclusions
                        4. If you find ANY relevant information, include it in your answer
                        5. Don't say "no information" if you found ANYTHING relevant"""
                    }, {
                        "role": "user",
                        "content": f"""
                        Question: {prompt}
                        
                        Analyze this content carefully and provide the most complete answer possible:
                        URL: {url}
                        
                        Content:
                        {content}
                        """
                    }]
                )
                
                analysis = response.choices[0].message.content
                
                if analysis:
                    result = f"""
                    === Analysis of page {i}/{len(selected_pages)} ===
                    URL: {url}
                    
                    {analysis}
                    """
                    print("\n" + "-"*50)
                    print("Analysis Results:")
                    print("-"*50)
                    print(result)
                    print("-"*50)
                    
                    results.append(result)
                        
            except Exception as e:
                print(f"\nError analyzing page {url}: {str(e)}")
                print("Full error:", traceback.format_exc())
                continue
        
        return "\n\n".join(results)

    except Exception as e:
        debug_logger.error(f"Error in AI search: {str(e)}", exc_info=True)
        return f"Error during AI analysis: {str(e)}"


# -----------------------------------------------------------------------------
#  NEW: Two-Step Approach
# -----------------------------------------------------------------------------

def parse_page_numbers(ai_response: str, max_pages: int) -> List[int]:
    """
    Naive parser to extract 'Page X' references from AI's response,
    returning them as a list of integers (1-based).
    """
    # This is just an example. You might prefer JSON-based answers, or more robust logic.
    possible = re.findall(r'[Pp]age\s*(\d+)', ai_response)
    chosen = []
    for val in possible:
        try:
            num = int(val)
            if 1 <= num <= max_pages:
                chosen.append(num)
        except ValueError:
            pass
    # Deduplicate while preserving order
    final = []
    for page_idx in chosen:
        if page_idx not in final:
            final.append(page_idx)
    return final


async def select_relevant_urls(query: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Let GPT-4 pick which pages are relevant to the query, based on just the URL or a short snippet.
    Returns a subset of `pages`.
    """
    if not pages:
        return []

    # Optionally skip media/binary files you know are not textual:
    text_like_pages = []
    skip_extensions = (".jpg", ".jpeg", ".gif", ".png", ".svg", ".pdf", ".zip", ".rar", "/media/")
    for page in pages:
        url = page.get("url", "").lower()
        if not any(url.endswith(ext) or (ext in url) for ext in skip_extensions):
            text_like_pages.append(page)

    # Make short summaries (URL + snippet) for the model
    summaries = []
    for idx, page in enumerate(text_like_pages):
        url = page.get('url', '')
        snippet = (page.get('text', '') or page.get('content', '') or page.get('raw_text', ''))
        snippet_preview = snippet[:200].replace('\n', ' ')
        summaries.append(f"Page {idx+1}: URL={url}\n  snippet={snippet_preview}...\n")

    # Create the prompt
    content_for_model = f"""
We have {len(text_like_pages)} possible pages (URLs). The user's query is:
    {query}

Below are short summaries (URLs + snippet). 
For each page that seems relevant, explain WHY you think it might contain useful information.
Then list the page numbers in order of likely relevance.

Format your response as:
REASONING:
- Page X: <reason why this page might be relevant>
- Page Y: <reason why this page might be relevant>

SELECTED PAGES: Page X, Page Y, ...

If no pages seem relevant, explain why and say "SELECTED PAGES: none"

Summaries:
{chr(10).join(summaries)}
"""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are an AI that selects relevant web pages based on user queries."},
                {"role": "user", "content": content_for_model}
            ]
        )
        ai_response = response.choices[0].message.content
        print("\n=== Page Selection Analysis ===\n", ai_response, "\n==================================\n")

        # Extract numeric page references from the SELECTED PAGES line
        selected_line = [line for line in ai_response.split('\n') if line.startswith('SELECTED PAGES:')]
        if not selected_line:
            return text_like_pages  # Fallback to all pages if format is wrong
            
        selected_text = selected_line[0].replace('SELECTED PAGES:', '').strip()
        
        if selected_text.lower() == 'none':
            print("\nNo pages were deemed relevant by initial analysis.")
            print("Falling back to analyzing all pages...\n")
            return text_like_pages

        chosen_numbers = parse_page_numbers(selected_text, max_pages=len(text_like_pages))
        if not chosen_numbers:
            print("\nNo pages were successfully parsed from selection.")
            print("Falling back to analyzing all pages...\n")
            return text_like_pages

        # Convert from 1-based to actual pages
        relevant_pages = []
        for idx in chosen_numbers:
            relevant_pages.append(text_like_pages[idx-1])
        return relevant_pages

    except Exception as e:
        print(f"Error selecting relevant URLs: {e}")
        # If something fails, fallback to returning all text-like pages
        return text_like_pages


async def handle_ai_search_two_step(query: str, content: Dict) -> str:
    """Two-step analysis with user interaction for second-tier pages."""
    try:
        debug_logger.debug("\nStarting handle_ai_search_two_step")
        
        print("\n" + "="*50)
        print("Starting AI Analysis (Two-Step)")
        print(f"Query: {query}")
        print("="*50 + "\n")
        
        # Get pages from either historic or current content
        pages = content.get('pages', []) or content.get('urls', [])
        total_pages = len(pages)
        print(f"Total pages found: {total_pages}\n")
        
        # Track analyzed pages and their tiers
        analyzed_urls = set()
        tier1_pages = []
        tier2_pages = []
        all_responses = []
        conclusive_answer = False
        
        # First pass - analyze high priority pages
        remaining_pages = [p for p in pages if p.get('url', '') not in analyzed_urls]
        relevant_pages = await select_relevant_urls(query, remaining_pages)
        
        if relevant_pages:
            tier1_pages = relevant_pages[:5]  # Top 5 most relevant
            tier2_pages = relevant_pages[5:]  # Rest are tier 2
            
            print("\nTier 1 (High Priority) Pages:")
            for i, page in enumerate(tier1_pages, 1):
                print(f"{i}. {page.get('url', '')}")
            
            # Analyze tier 1 pages
            for i, page in enumerate(tier1_pages, 1):
                url = page.get('url', '')
                text = (page.get('text', '') or 
                        page.get('content', '') or 
                        page.get('raw_text', ''))
                timestamp = page.get('timestamp', '')
                
                # Track this URL as analyzed
                analyzed_urls.add(url)

                if not text:
                    print(f"Skipping page {url}, no textual content.")
                    continue

                print(f"\nAnalyzing page {i}/{len(tier1_pages)}")
                print(f"URL: {url}")
                print(f"Content length: {len(text)} chars")

                try:
                    response = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[{
                            "role": "system",
                            "content": (
                                "You are a highly analytical AI assistant. "
                                "When analyzing content:\n"
                                "1. Think deeply about the question.\n"
                                "2. Look for direct or indirect evidence.\n"
                                "3. Use logic and reasoning.\n"
                                "4. If you find ANY relevant info, include it.\n"
                                "5. Don't say 'no info' if there's anything relevant.\n"
                                "6. Indicate if this provides a conclusive answer to the query."
                            )
                        }, {
                            "role": "user",
                            "content": f"""
                            Question: {query}

                            URL: {url}
                            Timestamp: {timestamp}
                            
                            Content:
                            {text}
                            
                            End your analysis with CONCLUSIVE: Yes/No to indicate if this provides a full answer to the query.
                            """
                        }]
                    )
                    
                    analysis = response.choices[0].message.content
                    if analysis:
                        result = f"""
                        === Analysis of page {i} ===
                        URL: {url}
                        
                        {analysis}
                        """
                        print("\n" + "-"*50)
                        print("Analysis Results:")
                        print("-"*50)
                        print(result)
                        print("-"*50)
                        all_responses.append(result)
                        
                        # Check if this provided a conclusive answer
                        if "CONCLUSIVE: Yes" in analysis:
                            conclusive_answer = True
                            break  # Exit the page analysis loop

                except Exception as e:
                    print(f"\nError analyzing page {url}: {str(e)}")
                    print("Full error:", traceback.format_exc())
                    continue
            
            # After tier 1 analysis, handle tier 2 pages
            if not conclusive_answer and (tier2_pages or remaining_pages):
                print("\n" + "="*50)
                print("Tier 1 analysis complete. Additional pages available:")
                print("="*50)
                
                # Show tier 2 pages
                if tier2_pages:
                    print("\nTier 2 (Medium Priority) Pages:")
                    for i, page in enumerate(tier2_pages, 1):
                        print(f"{i}. {page.get('url', '')}")
                
                # Show remaining unanalyzed pages
                remaining = [p for p in pages if p.get('url', '') not in analyzed_urls]
                if remaining:
                    print("\nRemaining Unanalyzed Pages:")
                    for i, page in enumerate(remaining, len(tier2_pages) + 1):
                        print(f"{i}. {page.get('url', '')}")
                
                while True:
                    print("\nOptions:")
                    print("1. Analyze all tier 2 pages")
                    print("2. Select specific pages to analyze")
                    print("3. Stop analysis")
                    choice = input("Enter your choice (1-3): ").strip()
                    
                    if choice == "1":
                        pages_to_analyze = tier2_pages
                        break
                    elif choice == "2":
                        print("\nEnter page numbers to analyze (comma-separated, e.g., '1,3,5')")
                        print("Or enter 'range X-Y' for a range (e.g., 'range 1-5')")
                        selection = input("> ").strip().lower()
                        
                        try:
                            if selection.startswith('range'):
                                start, end = map(int, selection.replace('range', '').strip().split('-'))
                                selected_indices = range(start-1, end)
                            else:
                                selected_indices = [int(i.strip())-1 for i in selection.split(',')]
                            
                            all_available = tier2_pages + remaining
                            pages_to_analyze = [all_available[i] for i in selected_indices if i < len(all_available)]
                            break
                        except Exception as e:
                            print(f"Invalid selection: {e}")
                            continue
                    elif choice == "3":
                        pages_to_analyze = []
                        break
                    else:
                        print("Invalid choice. Please try again.")
                
                # Analyze selected additional pages
                if pages_to_analyze:
                    print(f"\nAnalyzing {len(pages_to_analyze)} additional pages...")
                    for i, page in enumerate(pages_to_analyze, 1):
                        url = page.get('url', '')
                        text = (page.get('text', '') or 
                                page.get('content', '') or 
                                page.get('raw_text', ''))
                        timestamp = page.get('timestamp', '')
                        
                        # Track this URL as analyzed
                        analyzed_urls.add(url)

                        if not text:
                            print(f"Skipping page {url}, no textual content.")
                            continue

                        print(f"\nAnalyzing page {i}/{len(pages_to_analyze)}")
                        print(f"URL: {url}")
                        print(f"Content length: {len(text)} chars")

                        try:
                            response = client.chat.completions.create(
                                model=MODEL_NAME,
                                messages=[{
                                    "role": "system",
                                    "content": (
                                        "You are a highly analytical AI assistant. "
                                        "When analyzing content:\n"
                                        "1. Think deeply about the question.\n"
                                        "2. Look for direct or indirect evidence.\n"
                                        "3. Use logic and reasoning.\n"
                                        "4. If you find ANY relevant info, include it.\n"
                                        "5. Don't say 'no info' if there's anything relevant.\n"
                                        "6. Indicate if this provides a conclusive answer to the query."
                                    )
                                }, {
                                    "role": "user",
                                    "content": f"""
                                    Question: {query}

                                    URL: {url}
                                    Timestamp: {timestamp}
                                    
                                    Content:
                                    {text}
                                    
                                    End your analysis with CONCLUSIVE: Yes/No to indicate if this provides a full answer to the query.
                                    """
                                }]
                            )
                            
                            analysis = response.choices[0].message.content
                            if analysis:
                                result = f"""
                                === Analysis of page {i} ===
                                URL: {url}
                                
                                {analysis}
                                """
                                print("\n" + "-"*50)
                                print("Analysis Results:")
                                print("-"*50)
                                print(result)
                                print("-"*50)
                                all_responses.append(result)
                                
                                # Check if this provided a conclusive answer
                                if "CONCLUSIVE: Yes" in analysis:
                                    conclusive_answer = True
                                    break  # Exit the page analysis loop

                        except Exception as e:
                            print(f"\nError analyzing page {url}: {str(e)}")
                            print("Full error:", traceback.format_exc())
                            continue
        
        final_response = "\n\n".join(all_responses)
        
        print("\n" + "="*50)
        print("Two-Step Analysis Complete")
        print(f"Analyzed {len(analyzed_urls)} pages total")
        print("="*50 + "\n")
        
        return final_response

    except Exception as e:
        debug_logger.error(f"Error in two-step AI search: {str(e)}", exc_info=True)
        return f"Error processing two-step AI search: {str(e)}"