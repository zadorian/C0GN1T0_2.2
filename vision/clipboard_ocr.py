import io
import pyperclip
from PIL import ImageGrab, Image
import time
from typing import Optional
from processors.gpt4_processor import analyze_image
from processors.chatgpt_vision import ChatGPTVisionAnalyzer
from processors.linkedin_processor import LinkedInProcessor
from utils import save_result
from pynput import keyboard
import os
import traceback

class ClipboardOCR:
    def __init__(self, mode='general'):
        self.running = True
        self.mode = mode
        self.vision_analyzer = ChatGPTVisionAnalyzer()
        self.linkedin_analyzer = LinkedInProcessor()
    
    def get_clipboard_image(self) -> Optional[Image.Image]:
        """Get image from clipboard"""
        try:
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                return image
            return None
        except Exception as e:
            print(f"Error getting clipboard image: {e}")
            return None
    
    def start_monitoring(self):
        """Start monitoring clipboard for images"""
        print("\nMonitoring clipboard for images...")
        if self.mode == 'linkedin':
            print("LinkedIn Profile Mode Active")
        
        print("\nHotkey: Ctrl+Shift+V")
        print("Press ESC to exit")
        print("\n>>> Monitoring active... <<<\n")
        
        def on_press(key):
            try:
                if key == keyboard.Key.esc:
                    print("\nStopping monitor...")
                    self.running = False
                    return False
                elif key == keyboard.KeyCode.from_char('v'):
                    # Add key to current keys
                    self.current_keys.add(key)
                    # Check if ctrl and shift are pressed
                    if keyboard.Key.ctrl in self.current_keys and keyboard.Key.shift in self.current_keys:
                        print("\nHotkey detected! Processing clipboard...")
                        self.process_clipboard()
                else:
                    # Track modifier keys
                    self.current_keys.add(key)
            except AttributeError:
                pass

        def on_release(key):
            try:
                if key in self.current_keys:
                    self.current_keys.remove(key)
            except KeyError:
                pass

        self.current_keys = set()
        print("Starting keyboard listener...")
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    
    def process_clipboard(self):
        """Process image from clipboard"""
        image = self.get_clipboard_image()
        if image:
            # Save image temporarily
            temp_path = "temp_image.png"
            print(f"\nSaving image to: {temp_path}")
            print(f"Image size: {image.size}")
            print(f"Image mode: {image.mode}")
            
            image.save(temp_path)
            print(f"Image saved successfully: {os.path.exists(temp_path)}")
            
            try:
                if self.mode == 'linkedin':
                    result = self.linkedin_analyzer.analyze_profile(temp_path)
                    print(result)
                else:
                    print("\nCalling GPT-4 Vision analysis...")
                    gpt4_result = analyze_image(temp_path)
                    print("\nGPT-4 Analysis:")
                    print("="*50)
                    print(gpt4_result['content'])
                    print("="*50)

                    print("\nCalling ChatGPT Vision analysis...")
                    vision_result = self.vision_analyzer.analyze_image(temp_path)
                    print("\nChatGPT Vision Analysis:")
                    print("="*50)
                    print(vision_result['content'])
                    print("="*50)

                    result = {
                        "gpt4": gpt4_result,
                        "vision": vision_result,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_result(result)
                    print("\nResults saved to JSON file")
                
            except Exception as e:
                print(f"Error processing image: {e}")
                print(f"Stack trace: {traceback.format_exc()}")
        else:
            print("No image found in clipboard") 