from PIL import ImageGrab, Image
import tempfile
import os
import base64
import json
from pathlib import Path
from AI_models.ai_vision import VisionAnalyzer

class ExtractionPattern:
    def __init__(self):
        self.patterns = {}
        self.pattern_file = "extraction_patterns.json"
        self._load_patterns()
    
    def _load_patterns(self):
        """Load saved patterns from JSON file"""
        try:
            if os.path.exists(self.pattern_file):
                with open(self.pattern_file, 'r') as f:
                    self.patterns = json.load(f)
        except Exception as e:
            print(f"Error loading patterns: {e}")
            self.patterns = {}

    def _save_patterns(self):
        """Save patterns to JSON file"""
        try:
            with open(self.pattern_file, 'w') as f:
                json.dump(self.patterns, f, indent=2)
        except Exception as e:
            print(f"Error saving patterns: {e}")

    def add_pattern_from_text(self, name: str, pattern_text: str):
        """Add a new extraction pattern from text description"""
        self.patterns[name] = {
            "type": "text",
            "pattern": pattern_text
        }
        self._save_patterns()
        print(f"Added pattern '{name}' successfully")

    def add_pattern_from_clipboard(self, name: str):
        """Add a new extraction pattern from a screenshot in clipboard"""
        try:
            # Get image from clipboard
            clipboard_image = ImageGrab.grabclipboard()
            
            if not isinstance(clipboard_image, Image.Image):
                print("No image found in clipboard. Please copy a pattern image first.")
                return
                
            # Save to temporary file as JPEG
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                clipboard_image = clipboard_image.convert("RGB")
                clipboard_image.save(tmp_file.name, format='JPEG', quality=95)
                filename = tmp_file.name

            # Read and encode the image
            with open(filename, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Clean up the temporary file
            os.remove(filename)

            # Use Claude to analyze the pattern
            analyzer = VisionAnalyzer()
            pattern_prompt = """Look at this image showing a text extraction pattern/template.
            Describe the exact structure and format of how text should be extracted.
            Focus on:
            1. The hierarchical structure
            2. Formatting rules
            3. Special markers or delimiters
            4. Any specific instructions shown
            
            Return ONLY the pattern description in a clear, structured format."""
            
            pattern_description = analyzer.analyze(
                image_data,
                pattern_prompt,
                model="claude"
            )

            self.patterns[name] = {
                "type": "screenshot",
                "pattern": pattern_description
            }
            self._save_patterns()
            print(f"Added pattern '{name}' from screenshot successfully")

        except Exception as e:
            print(f"Error adding pattern from clipboard: {e}")

    def get_pattern(self, name: str) -> str:
        """Get a specific pattern by name"""
        return self.patterns.get(name, {}).get("pattern")

    def list_patterns(self):
        """List all available patterns"""
        print("\nAvailable Extraction Patterns:")
        print("=" * 30)
        for name, data in self.patterns.items():
            print(f"\nPattern: {name}")
            print(f"Type: {data['type']}")
            print("-" * 20)
            print(data['pattern'])

    def delete_pattern(self, name: str):
        """Delete a pattern by name"""
        if name in self.patterns:
            del self.patterns[name]
            self._save_patterns()
            print(f"Deleted pattern '{name}'")
        else:
            print(f"Pattern '{name}' not found")

def main():
    pattern_manager = ExtractionPattern()
    
    while True:
        print("\nExtraction Pattern Manager")
        print("1. Add text pattern")
        print("2. Add pattern from clipboard screenshot")
        print("3. List all patterns")
        print("4. Delete pattern")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            name = input("Enter pattern name: ")
            print("Enter pattern text (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            pattern_manager.add_pattern_from_text(name, "\n".join(lines))
        
        elif choice == "2":
            name = input("Enter pattern name: ")
            print("Copy pattern screenshot to clipboard and press Enter...")
            input()
            pattern_manager.add_pattern_from_clipboard(name)
        
        elif choice == "3":
            pattern_manager.list_patterns()
        
        elif choice == "4":
            name = input("Enter pattern name to delete: ")
            pattern_manager.delete_pattern(name)
        
        elif choice == "5":
            break

if __name__ == "__main__":
    main() 