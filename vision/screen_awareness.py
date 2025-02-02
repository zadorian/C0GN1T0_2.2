import os
import io
import tempfile
from PIL import ImageGrab
import base64
from AI_models.processors.gpt4_processor import GPT4VisionProcessor

class ScreenAnalyzer:
    def __init__(self):
        self.vision_processor = GPT4VisionProcessor()

    def capture_screen(self):
        """Capture the current screen"""
        try:
            # Capture the screen
            screenshot = ImageGrab.grab()
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file.write(img_byte_arr)
                return temp_file.name
                
        except Exception as e:
            print(f"Error capturing screen: {str(e)}")
            return None

    def analyze_screen(self, question="What's on this screen?"):
        """Analyze the current screen content"""
        try:
            # Capture screen
            temp_path = self.capture_screen()
            if not temp_path:
                return None
                
            # Encode image
            base64_image = self.vision_processor.encode_image(temp_path)
            if not base64_image:
                return None
                
            # Analyze with GPT-4 Vision
            result = self.vision_processor.analyze_image(base64_image, question)
            
            # Cleanup temp file
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            print(f"Error during screen capture or analysis: {str(e)}")
            return None

def test_screen_analysis():
    """Test the screen analysis functionality"""
    try:
        print("Testing screen analysis...")
        analyzer = ScreenAnalyzer()
        
        # Test screen analysis
        result = analyzer.analyze_screen()
        print("\nScreen Analysis Result:")
        print(result)
        
        # Test direct vision analysis
        print("\nTesting direct vision analysis...")
        temp_path = analyzer.capture_screen()
        if temp_path:
            base64_image = analyzer.vision_processor.encode_image(temp_path)
            result = analyzer.vision_processor.analyze_image(base64_image, "What do you see in this image?")
            os.unlink(temp_path)
            print("\nDirect Vision Analysis Result:")
            print(result)
        
    except Exception as e:
        print(f"Error during screen capture or analysis: {str(e)}")
        return None

if __name__ == "__main__":
    test_screen_analysis() 