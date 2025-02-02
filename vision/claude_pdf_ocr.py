import os
from anthropic import Anthropic
import base64
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Optional, Union

# Load environment variables from .env file
load_dotenv()

class ClaudeProcessor:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-5-sonnet-20241022"  # Updated to working model
        self.max_tokens = 4096
        
        # Set up output directory
        self.root_dir = Path(__file__).parent
        self.output_dir = self.root_dir / "processed_documents"
        self.output_dir.mkdir(exist_ok=True)

    async def process_document(self, file_path: Union[str, bytes]) -> Dict:
        """Process document using Claude"""
        try:
            # Read and encode the PDF
            if isinstance(file_path, str):
                with open(file_path, 'rb') as f:
                    pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
            else:
                pdf_base64 = base64.b64encode(file_path).decode('utf-8')

            print("\nProcessing with Claude...")
            message = self.client.beta.messages.create(
                model=self.model,
                betas=["pdfs-2024-09-25"],
                max_tokens=self.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": "Provide a complete transcription of ALL text content from this PDF document. You must transcribe the ENTIRE document from start to finish, maintaining the original formatting and structure. Do not summarize, do not ask for permission to continue, and do not skip any content. Include every single page and every piece of text exactly as it appears."
                            }
                        ]
                    }
                ]
            )

            # Structure the output
            output = {
                'metadata': {
                    'processed_datetime': datetime.now().isoformat(),
                    'source': str(file_path) if isinstance(file_path, str) else "bytes",
                    'model': message.model,
                    'usage': {
                        'input_tokens': message.usage.input_tokens,
                        'output_tokens': message.usage.output_tokens
                    }
                },
                'content': message.content[0].text if message.content else "",
                'raw_text': message.content[0].text if message.content else ""
            }

            return output

        except Exception as e:
            print(f"Error processing document with Claude: {str(e)}")
            raise

    def save_results(self, results: Dict, original_filename: str):
        """Save processing results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = Path(original_filename).stem
            outputs = {}

            # Save raw text
            raw_text_path = self.output_dir / f"{base_name}_{timestamp}_claude_raw.txt"
            with open(raw_text_path, 'w', encoding='utf-8') as f:
                f.write(results['raw_text'])
            outputs['raw'] = str(raw_text_path)

            # Save full JSON
            json_path = self.output_dir / f"{base_name}_{timestamp}_claude_full.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            outputs['json'] = str(json_path)

            print("\nSaved files in processed_documents/:")
            print(f"1. Raw text: {raw_text_path.name}")
            print(f"2. Full JSON: {json_path.name}")

            return outputs

        except Exception as e:
            print(f"Error saving results: {str(e)}")
            return {}

async def main():
    processor = ClaudeProcessor()
    
    # Get PDF file path from user
    while True:
        file_path = input("\nEnter the path to your PDF file: ").strip()
        if os.path.exists(file_path) and file_path.lower().endswith('.pdf'):
            break
        print("File not found or not a PDF. Please try again.")

    print(f"\nProcessing {file_path}...")
    result = await processor.process_document(file_path)
    processor.save_results(result, Path(file_path).name)
    print("Processing complete!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 