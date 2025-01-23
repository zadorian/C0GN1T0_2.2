from typing import Dict, Optional, List, Any
import traceback
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path if needed
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# External libs
from openai import OpenAI  # NEW IMPORT STYLE
import google.generativeai as genai

# Local config
from config import config

# Initialize clients at the top level with base URL
client = OpenAI(
    api_key=config.OPENAI_API_KEY,
    base_url="https://api.openai.com/v1"  # FIXED THE FUCKING URL
)

print(f"DEBUG: Using OpenAI API Key: {config.OPENAI_API_KEY[:10]}...")  # Print first 10 chars for security

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
        # NEW OPENAI FORMAT
        response = client.chat.completions.create(
            model="gpt-4",  # FIXED THE MODEL NAME TOO
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
    """Handle AI-based search with provided content one URL at a time"""
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
        
        # Process ONE PAGE AT A TIME - NO PROMPTS
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
                    model="gpt-4",  # FIXED THE MODEL NAME TOO
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
                print("Full error:", traceback.format_exc())  # MORE ERROR INFO
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