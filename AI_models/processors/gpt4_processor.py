import base64
import os
from openai import OpenAI
from PIL import Image
import io
from dotenv import load_dotenv
from config import config  # Import the Config singleton

# Load environment variables
load_dotenv()

class GPT4VisionProcessor:
    def __init__(self):
        print(f"\nDebug - Using API key from environment: {os.getenv('OPENAI_API_KEY')[:20]}...")
        
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),  # Use ONLY the environment key
            organization='org-ATN9LuhPklzEu1L8tM0pxWyG'
        )

    def ensure_valid_png(self, image_path):
        """Ensure the image is in a valid PNG format."""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = bg
                
                with io.BytesIO() as output:
                    img.save(output, format="JPEG", quality=95)  # Save as JPEG
                    valid_image = output.getvalue()
            return valid_image
        except Exception as e:
            print(f"Error ensuring valid image format: {e}")
            return None

    def encode_image(self, image_path):
        """Encode image to base64."""
        image_data = self.ensure_valid_png(image_path)
        if image_data:
            return base64.b64encode(image_data).decode('utf-8')
        return None

    def analyze_image(self, base64_image, question):
        """Analyze image using GPT-4O"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": question
                }]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error analyzing image: {str(e)}")
            return None 