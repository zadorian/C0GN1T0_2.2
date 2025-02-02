from PIL import ImageGrab, Image
import tempfile
import os
import base64
from AI_models.ai_vision import VisionAnalyzer
from extract_patterns import ExtractionPattern

def extract_text_from_clipboard(pattern_name: str = None):
    """
    Extracts and structures text from an image in the clipboard using Claude Vision.
    
    Args:
        pattern_name: Optional name of extraction pattern to use. If None, uses default pattern.
    Returns:
        The structured text or None if failed.
    """
    try:
        # Get image from clipboard
        clipboard_image = ImageGrab.grabclipboard()
        
        if not isinstance(clipboard_image, Image.Image):
            print("No image found in clipboard. Please copy an image first.")
            return None
            
        # Save to temporary file as JPEG
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            clipboard_image = clipboard_image.convert("RGB")  # Ensure it's in RGB mode
            clipboard_image.save(tmp_file.name, format='JPEG', quality=95)
            filename = tmp_file.name

        # Read and encode the image
        with open(filename, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Clean up the temporary file
        os.remove(filename)

        # Initialize VisionAnalyzer with Claude
        analyzer = VisionAnalyzer()
        
        # Get extraction pattern
        if pattern_name:
            pattern_manager = ExtractionPattern()
            pattern = pattern_manager.get_pattern(pattern_name)
            if not pattern:
                print(f"Pattern '{pattern_name}' not found. Using default pattern.")
                pattern = get_default_pattern()
        else:
            pattern = get_default_pattern()
        
        # Create extraction prompt using pattern
        extraction_prompt = f"""Extract and structure ALL text visible in this image according to this pattern:

{pattern}

Return ONLY the extracted and structured text, without any analysis or commentary."""

        # Get the structured text
        extracted_text = analyzer.analyze(
            image_data,
            extraction_prompt,
            model="claude"
        )
        
        return extracted_text

    except Exception as e:
        print(f"Error during text extraction: {e}")
        return None

def get_default_pattern():
    """Returns the default text extraction pattern"""
    return """Extract and structure text following these rules:
1. Preserve the exact text as written - do not paraphrase or summarize
2. Maintain the hierarchical structure if present (headings, subheadings, bullet points, etc.)
3. Format the output in a clean, readable way using:
   - Clear section breaks
   - Proper indentation for hierarchical content
   - Bullet points or numbering where appropriate
4. Include any visible:
   - Headers and titles
   - Main body text
   - Lists and enumerations
   - Labels and captions
   - Navigation elements
   - Button text
   - Form fields
   - Footer text
5. Preserve any important formatting like:
   - CAPITALIZATION
   - *emphasis*
   - Numerical formats
   - Special characters"""

if __name__ == "__main__":
    print("Extraction Pattern Manager Commands:")
    print("pattern list - Show available patterns")
    print("pattern use [name] - Use specific pattern")
    print("extract - Extract with default pattern")
    print("quit - Exit program")
    
    while True:
        cmd = input("\nEnter command: ").strip().lower()
        
        if cmd == "quit":
            break
        elif cmd == "pattern list":
            pattern_manager = ExtractionPattern()
            pattern_manager.list_patterns()
        elif cmd.startswith("pattern use "):
            pattern_name = cmd[11:].strip()
            print(f"Extracting text using pattern '{pattern_name}'...")
            result = extract_text_from_clipboard(pattern_name)
            if result:
                print("\nExtracted Text:")
                print("=" * 50)
                print(result)
                print("=" * 50)
        elif cmd == "extract":
            print("Extracting text with default pattern...")
            result = extract_text_from_clipboard()
            if result:
                print("\nExtracted Text:")
                print("=" * 50)
                print(result)
                print("=" * 50)
        else:
            print("Unknown command. Try: pattern list, pattern use [name], extract, or quit") 