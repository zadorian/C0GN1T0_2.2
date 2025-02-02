from typing import Dict, Optional
import base64
from openai import OpenAI
from PIL import Image
from io import BytesIO
import os
import traceback
from config import config

# Initialize the OpenAI client with API key from config
client = OpenAI(api_key=config.OPENAI_API_KEY)

def encode_image(image_path: str) -> str:
    """Encode image to base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(image_path: str) -> Dict:
    """Analyze image using GPT-4 Vision"""
    try:
        # Debug print
        print(f"\nAnalyzing image: {image_path}")
        print(f"Image exists: {os.path.exists(image_path)}")
        
        # Load and encode image
        with Image.open(image_path) as img:
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            print(f"Image size: {img.size}")
            print(f"Image mode: {img.mode}")
        
        # Create message with image
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please analyze this image and describe what you see in detail."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_str}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "role": response.choices[0].message.role
        }
    except Exception as e:
        print(f"\nError analyzing image: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        return {
            "content": f"Error analyzing image: {str(e)}",
            "model": "gpt-4o",
            "role": "assistant"
        } 