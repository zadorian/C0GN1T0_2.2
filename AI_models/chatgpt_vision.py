import base64
import os
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client with API key from environment
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")
client = OpenAI(
    api_key=api_key,
    organization='org-ATN9LuhPklzEu1L8tM0pxWyG'
)

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

def encode_image(image_path):
    """Encode image to base64, ensuring it's a valid PNG."""
    image_data = ensure_valid_png(image_path)
    if image_data:
        return base64.b64encode(image_data).decode('utf-8')
    return None

def analyze_image(base64_image, question):
    """Analyze image using GPT-4 Vision"""
    try:
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        return None

# Get the current directory of this script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Find the first image file in the current directory
image_files = [f for f in os.listdir(current_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
if image_files:
    image_path = os.path.join(current_dir, image_files[0])
    base64_image = encode_image(image_path)
    
    # Initial analysis
    print("Initial image summary:")
    result = analyze_image(base64_image, "What's in this image?")
    print(result)
    
    # Follow-up questions loop
    while True:
        follow_up = input("\nEnter a follow-up question (or 'quit' to exit): ")
        if follow_up.lower() == 'quit':
            break
        result = analyze_image(base64_image, follow_up)
        print(result)
else:
    print("No image files found in the current directory.")
