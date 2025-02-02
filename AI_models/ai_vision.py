# ===== IMPORTS & INITIALIZATION =====
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
from pydantic import BaseModel
from typing import List, Optional, Union, Dict, Any
from enum import Enum
import json
import time
import sys
from pathlib import Path
import base64
from PIL import Image, ImageGrab
import io

# Initialize OpenAI client
chatgpt_client = OpenAI(api_key='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')

# Initialize Claude client
claude_client = Anthropic(api_key='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')

# Initialize Gemini
genai.configure(api_key='AIzaSyApYgmp9_2wNr4txTcRhEoyYALQ6cTlmgQ')

def ensure_valid_png(image_path):
    """Ensure the image is in a valid PNG format."""
    try:
        with Image.open(image_path) as img:
            with io.BytesIO() as output:
                img.save(output, format="PNG")
                valid_png_content = output.getvalue()
        return valid_png_content
    except Exception as e:
        print(f"Error ensuring valid PNG format: {e}")
        return None

def encode_image_to_base64(image_path):
    """Encode image to base64, ensuring it's a valid PNG."""
    image_data = ensure_valid_png(image_path)
    if image_data:
        return base64.b64encode(image_data).decode('utf-8')
    else:
        return None

# ===== VISION ANALYSIS =====
class VisionAnalyzer:
    """Unified vision analysis across multiple models with specialized capabilities"""
    
    def __init__(self):
        self.models = {
            'gpt4': self._analyze_with_gpt4v,
            'claude': self._analyze_with_claude,
            'gemini': self._analyze_with_gemini
        }
    
    def _analyze_with_gpt4v(self, image_data: str, prompt: str, max_tokens: int = 500):
        """GPT-4 Vision analysis"""
        try:
            response = chatgpt_client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }}
                    ]
                }],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error with GPT-4V: {str(e)}"

    def _analyze_with_claude(self, image_data: str, prompt: str, max_tokens: int = 1000):
        """Claude Vision analysis"""
        try:
            response = claude_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=max_tokens,
                messages=[{
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data
                            }
                        }
                    ]
                }]
            )
            return response.content
        except Exception as e:
            return f"Error analyzing image with Claude Vision: {str(e)}"

    def _analyze_with_gemini(self, image_data: str, prompt: str, max_tokens: int = 500):
        """Gemini Vision analysis"""
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(
                [prompt, {
                    'inline_data': {
                        'mime_type': 'image/jpeg',
                        'data': image_data
                    }
                }],
                generation_config={
                    'max_output_tokens': max_tokens,
                    'temperature': 0.0
                }
            )
            return response.text
        except Exception as e:
            return f"Error analyzing image with Gemini: {str(e)}"

    def analyze(self, file_path: str, prompt: str, model: str = 'claude', max_tokens: int = 1000) -> str:
        """Analyze an image or PDF file using the specified model"""
        try:
            # Encode the file
            encoded_data = encode_image_to_base64(file_path)
            if not encoded_data:
                raise ValueError("Failed to encode file")
            
            # Get the appropriate model function
            if model not in self.models:
                raise ValueError(f"Unknown model: {model}")
            analyze_func = self.models[model]
            
            # Run analysis
            return analyze_func(encoded_data, prompt, max_tokens)
            
        except Exception as e:
            return f"Error in vision analysis: {str(e)}"