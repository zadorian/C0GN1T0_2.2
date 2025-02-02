import google.generativeai as genai
from typing import Optional, Dict, List, Any, TypedDict
import json
import time
from pathlib import Path
from typing_extensions import TypedDict
from config import config
from prompts import get_brand_analysis_prompt

# Update model name
MODEL_NAME = "gemini-2.0-flash-exp"
TEMPLATE_PATH = Path("template/Asia Pharma LLC.txt")

def load_template() -> str:
    """Load the report template."""
    try:
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not load template: {e}")
        return ""

class CompanyBackground(TypedDict):
    Company_Overview: str
    Key_Personnel: str
    Operations: str
    Financial_Information: str
    Regulatory_Status: str

class ReportSections(TypedDict):
    ASSIGNMENT: str
    COMPANY_BACKGROUND_INFORMATION: CompanyBackground

class Report(TypedDict):
    sections: ReportSections
    footnotes: List[str]

def generate_with_retry(prompt: str, 
                       max_retries: int = 3, 
                       delay: float = 1.0,
                       temperature: float = 0.7,
                       json_response: bool = False) -> Optional[str]:
    """Generate content using Gemini 2.0 with proper JSON schema."""
    
    # Configure Gemini
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Define JSON schema for report structure
    class CompanyBackground(TypedDict):
        Company_Overview: str
        Key_Personnel: str
        Operations: str
        Financial_Information: str
        Regulatory_Status: str

    class ReportSections(TypedDict):
        ASSIGNMENT: str
        COMPANY_BACKGROUND_INFORMATION: CompanyBackground

    class Report(TypedDict):
        sections: ReportSections
        footnotes: List[str]
    
    # Generation config with schema when JSON is requested
    generation_config = {
        'temperature': temperature,
        'top_p': 0.8,
        'top_k': 40,
        'max_output_tokens': 8192,
    }

    if json_response:
        generation_config.update({
            'candidate_count': 1,
            'response_mime_type': 'application/json',
            'response_schema': Report
        })

    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(**generation_config)
            )
            
            if response and response.text:
                text = response.text.strip()
                
                if json_response:
                    try:
                        # Ensure response matches our schema
                        parsed_json = json.loads(text)
                        if not isinstance(parsed_json, dict):
                            raise json.JSONDecodeError("Response must be an object", text, 0)
                        
                        # Validate required fields
                        if 'sections' not in parsed_json:
                            parsed_json['sections'] = {
                                "ASSIGNMENT": "Analysis could not be completed.",
                                "COMPANY_BACKGROUND_INFORMATION": {
                                    "Company_Overview": "No information available",
                                    "Key_Personnel": "No information available", 
                                    "Operations": "No information available",
                                    "Financial_Information": "No information available",
                                    "Regulatory_Status": "No information available"
                                }
                            }
                        
                        if 'footnotes' not in parsed_json:
                            parsed_json['footnotes'] = []
                            
                        return json.dumps(parsed_json, indent=2)
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON response on attempt {attempt + 1}: {str(e)}")
                        if attempt == max_retries - 1:
                            # Return default structure on final attempt
                            return json.dumps({
                                "sections": {
                                    "ASSIGNMENT": "Analysis could not be completed.",
                                    "COMPANY_BACKGROUND_INFORMATION": {
                                        "Company_Overview": "No information available",
                                        "Key_Personnel": "No information available",
                                        "Operations": "No information available",
                                        "Financial_Information": "No information available",
                                        "Regulatory_Status": "No information available"
                                    }
                                },
                                "footnotes": []
                            }, indent=2)
                        continue
                return text
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
            
    return None

def list_twitter_exports():
    """List all Twitter export files in the data directory."""
    data_dir = Path("data/twitter")
    
    # Create directories if they don't exist
    data_dir.parent.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)
    
    files = sorted(data_dir.glob("*.json"))
    if not files:
        print(f"No JSON files found in {data_dir}")
        print("Please add your Twitter export JSON files to the data/twitter directory")
        exit(1)
    
    return files

def analyze_twitter_json(file_path, question, instruction=""):
    """
    Analyze Twitter JSON data based on a specific question and optional instruction.
    
    Args:
        file_path (str): Path to the Twitter JSON file
        question (str): Question to analyze
        instruction (str): Optional additional instructions for analysis
    
    Returns:
        str: Analysis result
    """
    # Implementation depends on your Gemini API setup
    # This is a placeholder - you'll need to implement the actual analysis logic
    return f"Analysis of {file_path} based on question: {question}"

def extract_brand_name(company_name: str) -> str:
    """Extract brand name from company name using Gemini"""
    from prompts import get_brand_analysis_prompt
    
    prompt = get_brand_analysis_prompt(company_name)
    
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    
    try:
        response = model.generate_content(prompt)
        if response and response.text:
            brand = response.text.strip().upper()
            if brand == "NONE":
                return "NONE"
            if len(brand) > 2 and not any(x in brand.lower() for x in ["ltd", "limited", "consulting", "services"]):
                return brand
        return "NONE"
    except Exception as e:
        print(f"Brand extraction failed: {e}")
        return "NONE"

def analyze_content(content: str, query: str = "", question: str = "") -> str:
    """Analyze content with specific focus using Gemini 2.0 Flash."""
    template = load_template()
    
    prompt = f"""Study this EXAMPLE REPORT format carefully:

{template}

Using the EXACT SAME STYLE AND FORMAT as this example report, analyze this content{f' about {query}' if query else ''}{f' answering: {question}' if query else ''}:

{content}

CRITICAL FOOTNOTING REQUIREMENTS:
1. Every fact, statement, or piece of information MUST have a footnote
2. Use ONLY the provided source URLs for footnotes - NEVER make up sources
3. Each footnote should link to the specific URL where the information was found
4. Follow the exact same footnoting style as the template
5. If a piece of information has no verifiable source URL, mark it as "Source not verified"
6. Number footnotes sequentially as in the template
7. List all footnotes with their full URLs at the end of the report
8. Each distinct fact should have its own footnote, even if from the same source
9. When multiple sources confirm a fact, include all relevant URLs in the footnote

IMPORTANT FORMATTING REQUIREMENTS:
1. Match the exact structure of sections and subsections
2. Use the same table formats
3. Copy the writing style - formal, factual, and detailed
4. Use same date formats and headers
5. Include all company background details in the same format
6. Present media findings in the same way
7. Use identical reference formatting

Your report should be indistinguishable in format from the example, only the content should be different.
Remember: NEVER invent or make up sources - only use the provided URLs."""
    
    return generate_with_retry(prompt, temperature=0.3) or "Analysis could not be generated."
