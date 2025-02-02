import io
from PIL import ImageGrab, Image
import pyperclip
import time
from datetime import datetime
import base64
import os
import sys
import traceback
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(current_dir))

# Load config
from config import config

# Debug prints to verify paths
print("\nDebug: Python Path Information")
print(f"Current directory: {current_dir}")
print(f"Project root: {project_root}")
print(f"Python path: {sys.path}")
print(f"Processors directory exists: {(current_dir / 'processors').exists()}")

try:
    from processors.gpt4_processor import analyze_image as gpt4_analyze
except ImportError as e:
    print(f"\nImport Error: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

class ClipboardAnalyzer:
    def __init__(self, mode='general'):
        self.mode = mode
        # Verify API keys are loaded
        if not config.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found in config")
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("Anthropic API key not found in config")
        
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def get_clipboard_image(self) -> Optional[Image.Image]:
        try:
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                return image
                
            if image is None:
                desktop_path = os.path.expanduser("~/Desktop")
                screenshots = sorted(
                    [f for f in os.listdir(desktop_path) 
                     if f.startswith("Screenshot ") and f.endswith((".png", ".jpg"))],
                    key=lambda x: os.path.getmtime(os.path.join(desktop_path, x)),
                    reverse=True
                )
                
                if screenshots:
                    latest_screenshot = os.path.join(desktop_path, screenshots[0])
                    if time.time() - os.path.getmtime(latest_screenshot) < 5:
                        self.log(f"Using latest screenshot: {screenshots[0]}")
                        return Image.open(latest_screenshot)
            return None
            
        except Exception as e:
            self.log(f"Error getting clipboard image: {e}")
            return None

    def process_image(self):
        try:
            image = self.get_clipboard_image()
            if not image:
                self.log("No image found in clipboard")
                return

            # Use config's CONTENT_DIR for temp files
            temp_path = config.CONTENT_DIR / "temp_clipboard.png"
            image.save(temp_path)
            
            if self.mode == 'linkedin':
                result = gpt4_analyze(str(temp_path))
                self.log("\nLinkedIn Analysis Results:")
                print(result['content'])
            else:
                self.log("\nProcessing with GPT-4o...")
                result = gpt4_analyze(str(temp_path))
                print("\nGPT-4o Analysis:")
                print("="*50)
                print(result['content'])
                print("="*50)

            # Clean up temp file
            if temp_path.exists():
                os.remove(temp_path)

        except Exception as e:
            self.log(f"Error processing image: {str(e)}")
            print(traceback.format_exc())

    def start(self):
        """Simple loop waiting for user input"""
        print("\nClipboard Analyzer")
        print("=================")
        print("1. Copy an image to clipboard")
        print("2. Press Enter to analyze")
        print("3. Type 'exit' to quit")
        print("\nReady to analyze clipboard contents...")
        
        while True:
            command = input("\nPress Enter to analyze clipboard (or type 'exit' to quit): ").lower()
            if command == 'exit':
                break
            self.process_image()

def main():
    mode = input("\nEnter mode (general/linkedin): ").lower()
    analyzer = ClipboardAnalyzer(mode=mode)
    analyzer.start()

if __name__ == "__main__":
    main() 