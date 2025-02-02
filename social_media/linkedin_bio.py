import sys
from pathlib import Path
import importlib.util
import os
from dotenv import load_dotenv
from PIL import ImageGrab, Image

# Load environment variables
load_dotenv()

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import base64
from anthropic import Anthropic
from config import config
from openai import OpenAI

# Force the correct API key
OPENAI_KEY = "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"

# Debug prints
print(f"\nDebug - Environment OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
print(f"Debug - Config OPENAI_API_KEY: {config.OPENAI_API_KEY}")
print(f"Debug - Using forced OPENAI_API_KEY: {OPENAI_KEY}")

# Initialize clients
client = OpenAI(api_key=OPENAI_KEY)
claude_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def encode_image(image_path: str) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(base64_image: str, prompt: str, use_claude: bool = False) -> str:
    """Analyze image using GPT-4 Vision or Claude Vision"""
    try:
        if use_claude:
            response = claude_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                messages=[{
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }]
            )
            return response.content[0].text
        else:
            print(f"\nDebug - Sending request with API Key: {client.api_key}")
            response = client.chat.completions.create(
                model="gpt-4o",  # CORRECT MODEL NAME!
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )
            return response.choices[0].message.content
    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        return None

class LinkedInProcessor:
    def __init__(self):
        """Initialize LinkedIn profile analyzer"""
        self.claude = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    def analyze_profile(self, image_path: str = None) -> dict:
        """Analyze LinkedIn profile screenshot using GPT-4 Vision and Claude Vision"""
        results = {}

        # Get image from clipboard if no path provided
        if image_path is None:
            image = ImageGrab.grabclipboard()
            if not isinstance(image, Image.Image):
                print("No image found in clipboard. Please copy a LinkedIn profile screenshot first.")
                return {}
            # Save clipboard image temporarily
            image_path = "temp_linkedin.png"
            image.save(image_path)
            print("Successfully grabbed image from clipboard")
        
        # Encode image
        base64_image = encode_image(image_path)
        if not base64_image:
            print("Error: Could not process the image")
            return {}
            
        # GPT-4 Vision Analysis
        print("\n=== GPT-4 Vision Analysis ===")
        gpt4_result = analyze_image(base64_image, self.get_linkedin_profile_prompt(), use_claude=False)
        if gpt4_result:
            results["gpt4_vision"] = {"analysis": gpt4_result}
            print(gpt4_result)
        else:
            print("Error: GPT-4 Vision analysis failed")
        
        # Claude Vision Analysis
        print("\n=== Claude Vision Analysis ===")
        claude_result = analyze_image(base64_image, self.get_linkedin_profile_prompt(), use_claude=True)
        if claude_result:
            results["claude_vision"] = {"analysis": claude_result}
            print(claude_result)
        else:
            print("Error: Claude Vision analysis failed")
        
        # Optional Claude Narrative
        print("\nWould you like a narrative biography written by Claude? (y/n)")
        if input().lower() == 'y':
            print("\n=== Claude Narrative Biography ===")
            # Use both GPT-4 and Claude analysis for better narrative
            combined_analysis = f"GPT-4 Analysis:\n{gpt4_result}\n\nClaude Analysis:\n{claude_result}"
            narrative = self.generate_narrative(combined_analysis)
            results["claude_narrative"] = narrative
            print(narrative)

        # Cleanup temporary file if using clipboard
        if image_path == "temp_linkedin.png":
            try:
                os.remove(image_path)
            except:
                pass
        
        return results

    def get_linkedin_profile_prompt(self) -> str:
        """Return the prompt for analyzing LinkedIn profile"""
        return """Analyze this LinkedIn profile and extract key information, focusing on:
1. Professional Summary
2. Current Role and Company
3. Work Experience (chronological)
4. Education
5. Skills and Endorsements
6. Certifications
7. Languages
8. Volunteer Experience
9. Publications or Patents
10. Awards and Honors

Please be specific with dates, company names, and role titles."""

    def generate_narrative(self, profile_data: str) -> str:
        """Generate narrative biography using Claude"""
        prompt = f"""Based on this LinkedIn profile data, write a detailed narrative biography 
        in chronological order. Include all experiences, education, and skills. Write in 
        flowing paragraphs that tell the person's professional story:

        {profile_data}

        Make sure to:
        1. Start with current role and major achievements
        2. Flow chronologically through their career history
        3. Weave in education at appropriate points
        4. Highlight key skills and expertise
        5. Maintain a professional tone
        """

        try:
            response = self.claude.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error generating narrative: {str(e)}"

if __name__ == "__main__":
    print("\nLinkedIn Profile Analyzer")
    print("------------------------")
    print("Press Enter to analyze image from clipboard, or enter path to screenshot:")
    
    # Initialize processor
    processor = LinkedInProcessor()
    
    # Get image path from user or use clipboard
    image_path = input().strip()
    if not image_path:
        print("Checking clipboard for LinkedIn screenshot...")
        results = processor.analyze_profile()
    else:
        if not Path(image_path).exists():
            print(f"Error: File not found: {image_path}")
            sys.exit(1)
        results = processor.analyze_profile(image_path)