import base64
import os
from PIL import Image, ImageGrab
import tempfile
from AI_models.ai_vision import VisionAnalyzer
from prompts import MAIN_SYSTEM_PROMPT

def compress_image(image, max_size_bytes=4*1024*1024):  # 4MB target to be safe
    """Compress image until it's under max_size_bytes"""
    quality = 95
    temp_buffer = tempfile.BytesIO()
    
    while quality > 5:  # Don't go below quality=5
        temp_buffer.seek(0)
        temp_buffer.truncate()
        image.save(temp_buffer, format='JPEG', quality=quality)
        if temp_buffer.tell() <= max_size_bytes:
            break
        quality -= 5
    
    temp_buffer.seek(0)
    return temp_buffer

def analyze_screen_silently(model="claude", conversation_history=None):
    """
    Quietly captures and analyzes the current screen content.
    Returns the analysis text or None if failed.
    """
    try:
        # Capture the screen
        screenshot = ImageGrab.grab()
        screenshot = screenshot.convert("RGB")  # Ensure it's in RGB mode
        
        # Compress the image
        compressed_buffer = compress_image(screenshot)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_file.write(compressed_buffer.getvalue())
            filename = tmp_file.name

        # Format conversation history if provided
        conversation_context = ""
        if conversation_history:
            conversation_context = "\nPrevious conversation:\n" + "\n".join(
                f"{'User' if i%2==0 else 'Assistant'}: {msg}" 
                for i, msg in enumerate(conversation_history[-10:])
            ) + "\n"

        # Initialize and use the VisionAnalyzer
        analyzer = VisionAnalyzer()
        description = analyzer.analyze(
            filename,  # Pass the file path instead of base64 data
            f"{MAIN_SYSTEM_PROMPT}\n{conversation_context}\nDescribe what is currently visible on the screen.",
            model=model
        )
        
        # Clean up the temporary file
        os.remove(filename)
        return description

    except Exception as e:
        print(f"Error during screen capture or analysis: {e}")
        return None
