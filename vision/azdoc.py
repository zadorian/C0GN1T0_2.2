from PyPDF2 import PdfReader, PdfWriter
import io
import os
import json
import asyncio
import requests
import uuid
from pathlib import Path
from typing import Union, List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import aiohttp

class AzureDocProcessor:
    def __init__(self):
        """Initialize Azure Document Intelligence and Translator services"""
        self.doc_key = "9ocssrr30J4DmVgyTGbJ9RakfxUfTQCdeMBofGH8ZKBgQp4aG069JQQJ99ALAC5RqLJXJ3w3AAALACOGiaBK"
        self.doc_endpoint = "https://sastredocintel.cognitiveservices.azure.com/"
        self.translator_key = "4AYFPSyb1zDnlB0GVYuGIgGnKcWKnlzQ0ozB3vH6w3iYsSlH8ekuJQQJ99ALAC5RqLJXJ3w3AAAbACOGBGGL"
        self.translator_location = "eastus"
        self.client = DocumentAnalysisClient(
            endpoint=self.doc_endpoint,
            credential=AzureKeyCredential(self.doc_key)
        )
        self.output_dir = Path("processed_documents")
        self.output_dir.mkdir(exist_ok=True)
        self.chunk_size = 20  # Number of pages per chunk

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def is_url(self, path: str) -> bool:
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except:
            return False

    def split_pdf_into_chunks(self, pdf_content: bytes) -> List[bytes]:
        """Split PDF into smaller chunks"""
        self.log("Splitting PDF into smaller chunks...")
        chunks = []
        reader = PdfReader(io.BytesIO(pdf_content))
        total_pages = len(reader.pages)
        
        for i in range(0, total_pages, self.chunk_size):
            writer = PdfWriter()
            end_page = min(i + self.chunk_size, total_pages)
            
            for page_num in range(i, end_page):
                writer.add_page(reader.pages[page_num])
            
            output = io.BytesIO()
            writer.write(output)
            chunks.append(output.getvalue())
            self.log(f"Created chunk {len(chunks)} ({i+1}-{end_page} of {total_pages} pages)")
            
        return chunks

    async def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        if not text.strip():
            return text
            
        url = "https://api.cognitive.microsofttranslator.com/translate"
        params = {
            'api-version': '3.0',
            'to': target_language
        }
        if source_language:
            params['from'] = source_language
            
        headers = {
            'Ocp-Apim-Subscription-Key': self.translator_key,
            'Ocp-Apim-Subscription-Region': self.translator_location,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    params=params,
                    headers=headers,
                    json=[{'text': text}]
                ) as response:
                    response.raise_for_status()
                    translation = await response.json()
                    return translation[0]['translations'][0]['text']
        except Exception as e:
            self.log(f"Translation error: {str(e)}")
            return text

    async def process_document(self, source: Union[str, bytes], translate_to: Optional[str] = None) -> Dict:
        try:
            # Get document content
            if isinstance(source, str):
                if self.is_url(source):
                    self.log("Downloading document from URL...")
                    response = requests.get(source)
                    response.raise_for_status()
                    content = response.content
                else:
                    self.log("Reading local document...")
                    with open(source, 'rb') as f:
                        content = f.read()
            else:
                content = source

            # Split into chunks if it's a PDF
            combined_results = {
                'pages': [],
                'tables': [],
                'metadata': {
                    'processed_datetime': datetime.now().isoformat(),
                    'source': str(source) if isinstance(source, str) else "bytes",
                }
            }

            try:
                chunks = self.split_pdf_into_chunks(content)
                self.log(f"Split document into {len(chunks)} chunks")
            except Exception as e:
                self.log(f"Not a PDF or error splitting: {e}. Processing as single document...")
                chunks = [content]

            total_pages = 0
            for i, chunk in enumerate(chunks, 1):
                max_retries = 3
                retry_delay = 2  # seconds
                
                for attempt in range(max_retries):
                    try:
                        self.log(f"Processing chunk {i} of {len(chunks)}... (attempt {attempt + 1})")
                        poller = self.client.begin_analyze_document("prebuilt-read", chunk)
                        result = poller.result()
                        
                        # Extract content from this chunk
                        pages = self.extract_text_with_layout(result)
                        tables = self.extract_tables(result)
                        
                        # Update page numbers
                        for page in pages:
                            page['number'] += total_pages
                        total_pages += len(pages)
                        
                        # Add to combined results
                        combined_results['pages'].extend(pages)
                        combined_results['tables'].extend(tables)
                        
                        # Success - break the retry loop
                        break
                        
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            wait_time = retry_delay * (attempt + 1)
                            self.log(f"Rate limit hit. Waiting {wait_time} seconds before retry...")
                            await asyncio.sleep(wait_time)
                        else:
                            raise
                
                # Add delay between chunks to avoid rate limits
                if i < len(chunks):
                    self.log("Waiting between chunks to avoid rate limits...")
                    await asyncio.sleep(1.5)

            combined_results['metadata']['page_count'] = total_pages

            # Translate if requested
            if translate_to:
                self.log(f"Translating content to {translate_to}...")
                for page in combined_results['pages']:
                    for line in page['lines']:
                        line['translated_text'] = await self.translate_text(
                            line['text'],
                            translate_to
                        )
                        # Add small delay between translations
                        await asyncio.sleep(0.1)
                
                for table in combined_results['tables']:
                    translated_data = []
                    for row in table['data']:
                        translated_row = []
                        for cell in row:
                            translated_cell = await self.translate_text(
                                cell,
                                translate_to
                            ) if cell.strip() else cell
                            translated_row.append(translated_cell)
                            # Add small delay between translations
                            await asyncio.sleep(0.1)
                        translated_data.append(translated_row)
                    table['translated_data'] = translated_data

            return combined_results

        except Exception as e:
            self.log(f"Error processing document: {str(e)}")
            raise

    def extract_text_with_layout(self, result) -> List[Dict]:
        pages = []
        for page_num, page in enumerate(result.pages, 1):
            page_content = {
                'number': page_num,
                'lines': [],
                'words': []
            }
            
            for line in page.lines:
                page_content['lines'].append({
                    'text': line.content,
                    'polygon': line.polygon
                })
            
            for word in page.words:
                word_data = {
                    'text': word.content,
                    'polygon': word.polygon
                }
                if hasattr(word, 'confidence'):
                    word_data['confidence'] = word.confidence
                page_content['words'].append(word_data)
            
            pages.append(page_content)
        return pages

    def extract_tables(self, result) -> List[Dict]:
        tables = []
        for table in result.tables:
            table_data = []
            for row in range(table.row_count):
                row_data = []
                for col in range(table.column_count):
                    cell = next((cell for cell in table.cells 
                               if cell.row_index == row 
                               and cell.column_index == col), None)
                    row_data.append(cell.content if cell else "")
                table_data.append(row_data)
            tables.append({
                'data': table_data,
                'row_count': table.row_count,
                'column_count': table.column_count
            })
        return tables

    def save_results(self, results: Dict, original_filename: str, translate_to: Optional[str] = None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(original_filename).stem
        outputs = {}

        try:
            # Save JSON
            json_path = self.output_dir / f"{base_name}_{timestamp}_full.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            outputs['json'] = str(json_path)

            # Save original text with section markers
            text_path = self.output_dir / f"{base_name}_{timestamp}_original.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                for page in results['pages']:
                    f.write(f"\n=== Page {page['number']} ===\n")
                    current_section = []
                    
                    for line in page['lines']:
                        current_section.append(line['text'])
                        
                        # Create a new section after accumulating several lines or on certain triggers
                        if len(current_section) >= 5 or line['text'].strip().endswith('.'):
                            if current_section:
                                f.write("<section>\n")
                                f.write("\n".join(current_section))
                                f.write("\n</section>\n\n")
                                current_section = []
                    
                    # Write any remaining lines in the current section
                    if current_section:
                        f.write("<section>\n")
                        f.write("\n".join(current_section))
                        f.write("\n</section>\n\n")
            
            outputs['original_text'] = str(text_path)

            # Save translated text if available
            if translate_to and any('translated_text' in line for page in results['pages'] for line in page['lines']):
                translated_path = self.output_dir / f"{base_name}_{timestamp}_{translate_to}.txt"
                with open(translated_path, 'w', encoding='utf-8') as f:
                    for page in results['pages']:
                        f.write(f"\n=== Page {page['number']} ===\n")
                        current_section = []
                        
                        for line in page['lines']:
                            if 'translated_text' in line:
                                current_section.append(line['translated_text'])
                                
                                if len(current_section) >= 5 or line['translated_text'].strip().endswith('.'):
                                    if current_section:
                                        f.write("<section>\n")
                                        f.write("\n".join(current_section))
                                        f.write("\n</section>\n\n")
                                        current_section = []
                        
                    if current_section:
                        f.write("<section>\n")
                        f.write("\n".join(current_section))
                        f.write("\n</section>\n\n")
            
                outputs['translated_text'] = str(translated_path)

            # Save combined view (original + translation) with aligned sections
            if translate_to:
                combined_path = self.output_dir / f"{base_name}_{timestamp}_combined.txt"
                with open(combined_path, 'w', encoding='utf-8') as f:
                    for page in results['pages']:
                        f.write(f"\n=== Page {page['number']} ===\n")
                        current_section_orig = []
                        current_section_trans = []
                        
                        for line in page['lines']:
                            current_section_orig.append(line['text'])
                            current_section_trans.append(line.get('translated_text', ''))
                            
                            if len(current_section_orig) >= 5 or line['text'].strip().endswith('.'):
                                if current_section_orig:
                                    f.write("<section-pair>\n")
                                    f.write("<original>\n")
                                    f.write("\n".join(current_section_orig))
                                    f.write("\n</original>\n")
                                    f.write("<translation>\n")
                                    f.write("\n".join(current_section_trans))
                                    f.write("\n</translation>\n")
                                    f.write("</section-pair>\n\n")
                                    current_section_orig = []
                                    current_section_trans = []
                        
                    if current_section_orig:
                        f.write("<section-pair>\n")
                        f.write("<original>\n")
                        f.write("\n".join(current_section_orig))
                        f.write("\n</original>\n")
                        f.write("<translation>\n")
                        f.write("\n".join(current_section_trans))
                        f.write("\n</translation>\n")
                        f.write("</section-pair>\n\n")
            
                outputs['combined_text'] = str(combined_path)

            # Save tables with similar section marking
            if results['tables']:
                tables_path = self.output_dir / f"{base_name}_{timestamp}_tables.txt"
                with open(tables_path, 'w', encoding='utf-8') as f:
                    for i, table in enumerate(results['tables'], 1):
                        f.write(f"\n=== Table {i} ===\n")
                        f.write("<table-pair>\n")
                        
                        f.write("<original>\n")
                        for row in table['data']:
                            f.write(" | ".join(row) + "\n")
                        f.write("</original>\n")
                        
                        if translate_to and 'translated_data' in table:
                            f.write("<translation>\n")
                            for row in table['translated_data']:
                                f.write(" | ".join(row) + "\n")
                            f.write("</translation>\n")
                        
                        f.write("</table-pair>\n\n")
                outputs['tables'] = str(tables_path)

            return outputs

        except Exception as e:
            self.log(f"Error saving results: {str(e)}")
            raise

async def main():
    processor = AzureDocProcessor()
    
    print("\nAzure Document Processor")
    print("=======================")
    print("Handles:")
    print("- PDFs (including large files)")
    print("- Images (PNG, JPG, TIFF, etc.)")
    print("- Translation to multiple languages")
    print("\nOptions:")
    print("1. Process single file")
    print("2. Process URL")
    print("3. Process all files in directory")
    
    choice = input("\nChoice (1-3): ")
    
    translate = input("Translate content? (y/n): ").lower() == 'y'
    target_language = None
    if translate:
        target_language = input("Enter target language code (e.g., en, es, fr): ").strip()
    
    try:
        if choice == "1":
            path = input("Enter file path: ").strip()
            results = await processor.process_document(path, target_language)
            saved_files = processor.save_results(results, path, target_language)
            print("\nProcessing complete!")
            print(f"Text output: {saved_files['text']}")
            if saved_files.get('tables'):
                print(f"Tables output: {saved_files['tables']}")
            
        elif choice == "2":
            url = input("Enter document URL: ").strip()
            results = await processor.process_document(url, target_language)
            saved_files = processor.save_results(results, url.split('/')[-1], target_language)
            print("\nProcessing complete!")
            print(f"Text output: {saved_files['text']}")
            if saved_files.get('tables'):
                print(f"Tables output: {saved_files['tables']}")
            
        elif choice == "3":
            directory = input("Enter directory path (or press Enter for current): ").strip() or "."
            files = [f for f in os.listdir(directory) 
                    if f.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'))]
            
            if not files:
                print("No supported files found!")
                return
            
            print(f"\nFound {len(files)} files")
            process_all = input("Process all files? (y/n): ").lower() == 'y'
            
            if not process_all:
                try:
                    num_files = int(input(f"How many files to process (1-{len(files)})? "))
                    files = files[:num_files]
                except ValueError:
                    print("Invalid number, processing all files")
            
            for file in files:
                print(f"\nProcessing: {file}")
                path = os.path.join(directory, file)
                results = await processor.process_document(path, target_language)
                saved_files = processor.save_results(results, file, target_language)
                print(f"Text output: {saved_files['text']}")
                if saved_files.get('tables'):
                    print(f"Tables output: {saved_files['tables']}")
        
        else:
            print("Invalid choice!")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())