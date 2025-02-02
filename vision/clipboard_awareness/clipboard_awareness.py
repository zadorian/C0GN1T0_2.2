import io
from PIL import ImageGrab
import time
from datetime import datetime
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from social_media.linkedin_bio import LinkedInProcessor

class ImageAnalysisMonitor:
    def __init__(self):
        self.is_running = True
        self.processor = LinkedInProcessor()

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def process_clipboard_image(self):
        """Process image from clipboard using LinkedIn analyzer"""
        try:
            self.log("Analyzing clipboard contents...")
            results = self.processor.analyze_profile()
            if results:
                self.log("Analysis complete!")
            else:
                self.log("No results returned from analysis")

        except Exception as e:
            self.log(f"Error processing image: {str(e)}")

    def start_monitoring(self):
        """Start monitoring clipboard contents"""
        self.log("Monitoring clipboard... Press Enter to analyze clipboard contents")
        self.log("Type 'quit' to exit")
        
        while self.is_running:
            try:
                user_input = input().strip().lower()
                if user_input == 'quit':
                    break
                self.process_clipboard_image()
            except Exception as e:
                self.log(f"Error: {str(e)}")

def main():
    print("\nLinkedIn Profile Monitor")
    print("=======================")
    print("1. Copy LinkedIn profile screenshot to clipboard")
    print("2. Press Enter to analyze")
    print("\nType 'quit' to exit")
    
    monitor = ImageAnalysisMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main() 