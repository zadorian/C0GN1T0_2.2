from typing import Dict, Optional, List, Any
import traceback
import sys
import time
import re
from pathlib import Path

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
    
    analysis_prompt = f"""
    Based ONLY on this content chunk, answer: {query}
    
    Content from {domain} ({chunk_range}):
    {'\n'.join(batch_text)}
    
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
            model="gpt-4",
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
        
        # Fall back to Gemini
        gemini_prompt = f"""
        Carefully analyze this content to answer: {query}
        
        Content from {domain} ({chunk_range}):
        {'\n'.join(batch_text)}
        
        Important:
        1. Only use facts from this content
        2. Note any changes over time
        3. Include timestamps
        4. List the exact URLs where information was found
        """
        
        gemini_response = generate_with_gemini(gemini_prompt)
        if gemini_response:
            return gemini_response
        else:
            print("Both GPT-4 and Gemini failed to analyze content")
            return None


async def handle_ai_search(query: str, content: Dict) -> str:
    """(Existing) Handle AI-based search with provided content one URL at a time"""
    try:
        print("\nDEBUG: Starting handle_ai_search")
        
        print("\n" + "="*50)
        print("Starting AI Analysis")
        print(f"Query: {query}")
        print("="*50 + "\n")
        
        # Get pages from either historic or current content
        pages = content.get('pages', []) or content.get('urls', [])
        total_pages = len(pages)
        print(f"Total pages to analyze: {total_pages}\n")
        
        all_responses = []
        
        # Process each page in a single pass
        for i, page in enumerate(pages, 1):
            url = page.get('url', '')
            text = (page.get('text', '') or 
                    page.get('content', '') or 
                    page.get('raw_text', ''))
            timestamp = page.get('timestamp', '')
            
            if not text:
                print(f"Page {i}/{total_pages}: {url} (No content)")
                continue
                
            print(f"\nAnalyzing page {i}/{total_pages}")
            print(f"URL: {url}")
            print(f"Content length: {len(text)} chars")
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
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
                        Question: {query}
                        
                        Analyze this content carefully and provide the most complete answer possible:
                        URL: {url}
                        Timestamp: {timestamp}
                        
                        Content:
                        {text}
                        """
                    }]
                )
                
                analysis = response.choices[0].message.content
                
                if analysis:
                    result = f"""
                    === Analysis of page {i}/{total_pages} ===
                    URL: {url}
                    
                    {analysis}
                    """
                    print("\n" + "-"*50)
                    print("Analysis Results:")
                    print("-"*50)
                    print(result)
                    print("-"*50)
                    
                    all_responses.append(result)
                        
            except Exception as e:
                print(f"\nError analyzing page {url}: {str(e)}")
                print("Full error:", traceback.format_exc())
                continue
        
        final_response = "\n\n".join(all_responses)
        
        print("\n" + "="*50)
        print("Analysis Complete")
        print("="*50 + "\n")
        
        return final_response

    except Exception as e:
        print(f"Error in AI search: {str(e)}")
        traceback.print_exc()
        return f"Error processing AI search: {str(e)}"


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
            model="gpt-4",
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
    """
    TWO-STEP approach:
      1) Let the AI pick which pages (URLs) are relevant based on short info.
      2) Analyze only those pages in detail.
    If no conclusive answer is found, automatically continues with remaining pages
    unless user chooses to stop.
    """
    try:
        print("\nDEBUG: Starting handle_ai_search_two_step")
        
        print("\n" + "="*50)
        print("Starting AI Analysis (Two-Step)")
        print(f"Query: {query}")
        print("="*50 + "\n")
        
        # Get pages from either historic or current content
        pages = content.get('pages', []) or content.get('urls', [])
        total_pages = len(pages)
        print(f"Total pages found: {total_pages}\n")
        
        # Track analyzed pages across iterations
        analyzed_urls = set()
        all_responses = []
        conclusive_answer = False
        
        while not conclusive_answer and pages:
            # ---------------------------------------------------------------
            # PHASE 1: Let GPT-4 pick relevant pages just from URLs/snippets
            # ---------------------------------------------------------------
            # Filter out already analyzed pages
            remaining_pages = [p for p in pages if p.get('url', '') not in analyzed_urls]
            if not remaining_pages:
                break
                
            relevant_pages = await select_relevant_urls(query, remaining_pages)
            if not relevant_pages:
                break
                
            print(f"AI selected {len(relevant_pages)} new pages to analyze (of {len(remaining_pages)} remaining).\n")
            
            # ---------------------------------------------------------------
            # PHASE 2: Analyze selected pages in detail
            # ---------------------------------------------------------------
            for i, page in enumerate(relevant_pages, 1):
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

                print(f"\nAnalyzing page {i}/{len(relevant_pages)}")
                print(f"URL: {url}")
                print(f"Content length: {len(text)} chars")

                try:
                    response = client.chat.completions.create(
                        model="gpt-4",
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
            
            # After each batch of pages
            if not conclusive_answer:
                remaining_count = len(pages) - len(analyzed_urls)
                if remaining_count > 0:
                    print(f"\nNo conclusive answer yet. {remaining_count} pages remain unanalyzed.")
                    print("Press Enter to continue automatically, or type 'stop' to finish here: ")
                    
                    user_input = input().strip().lower()
                    if user_input == 'stop':
                        break
                else:
                    print("\nAll pages have been analyzed without finding a conclusive answer.")
                    break

        final_response = "\n\n".join(all_responses)
        
        print("\n" + "="*50)
        print("Two-Step Analysis Complete")
        print(f"Analyzed {len(analyzed_urls)} pages total")
        print("="*50 + "\n")
        
        return final_response

    except Exception as e:
        print(f"Error in two-step AI search: {str(e)}")
        traceback.print_exc()
        return f"Error processing two-step AI search: {str(e)}"