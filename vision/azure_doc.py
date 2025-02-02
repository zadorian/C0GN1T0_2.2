import sys
import site
print("Python version:", sys.version)
print("Python path:", sys.path)
print("Site packages:", site.getsitepackages())

# Try to import each package and print its version/location
try:
    import azure.ai.formrecognizer
    print("Azure Form Recognizer location:", azure.ai.formrecognizer.__file__)
except ImportError as e:
    print("Failed to import azure.ai.formrecognizer:", e)

try:
    import reportlab
    print("ReportLab location:", reportlab.__file__)
except ImportError as e:
    print("Failed to import reportlab:", e)

try:
    import PyPDF2
    print("PyPDF2 location:", PyPDF2.__file__)
except ImportError as e:
    print("Failed to import PyPDF2:", e)

import os
import asyncio
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import Union, List, Dict
import json
from datetime import datetime
from urllib.parse import urlparse
import requests
import tempfile
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import io

# Add company_search to Python path
sys.path.append(str(Path(__file__).parent.parent / 'company_search'))

from azure_doctrans import DocumentTranslator

class AzureOCRProcessor:
    def __init__(self):
        """Initialize Azure Document Intelligence client"""
        self.key = "9ocssrr30J4DmVgyTGbJ9RakfxUfTQCdeMBofGH8ZKBgQp4aG069JQQJ99ALAC5RqLJXJ3w3AAALACOGiaBK"
        self.endpoint = "https://sastredocintel.cognitiveservices.azure.com/"  # Hardcoded endpoint
        
        self.client = DocumentAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )
        
        # Set up output directory
        self.output_dir = Path("processed_documents")
        self.output_dir.mkdir(exist_ok=True)

    def log(self, message: str):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def is_url(self, path: str) -> bool:
        """Check if string is URL"""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except:
            return False

    def reduce_pdf_resolution(self, input_pdf_path: str, output_pdf_path: str, dpi: int = 150):
        """Reduce the resolution of a PDF"""
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.drawImage(ImageReader(page), 0, 0, width=letter[0], height=letter[1], preserveAspectRatio=True, mask='auto')
            can.save()

            packet.seek(0)
            new_page = PdfReader(packet).pages[0]
            writer.add_page(new_page)

        with open(output_pdf_path, 'wb') as output_pdf:
            writer.write(output_pdf)

    async def download_and_reduce_pdf(self, url: str) -> str:
        """Download PDF and reduce its resolution"""
        self.log(f"Downloading: {url}")
        response = requests.get(url)
        response.raise_for_status()

        # Save original PDF to temp file
        original_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        with open(original_temp.name, 'wb') as f:
            f.write(response.content)

        # Reduce resolution
        reduced_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        self.reduce_pdf_resolution(original_temp.name, reduced_temp.name)

        # Clean up original temp file
        os.unlink(original_temp.name)

        return reduced_temp.name

    async def download_and_process_pdf(self, url: str) -> str:
        """Download PDF from URL"""
        self.log(f"Downloading: {url}")
        response = requests.get(url)
        response.raise_for_status()

        # Save to temp file
        temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        with open(temp.name, 'wb') as f:
            f.write(response.content)
        
        self.log(f"Saved temporary file: {temp.name}")
        return temp.name

    def extract_tables(self, result) -> List[Dict]:
        """Extract tables from document"""
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

    def extract_text_with_layout(self, result) -> Dict:
        """Extract text while preserving layout"""
        pages = []
        for page_num, page in enumerate(result.pages, 1):
            page_content = {
                'number': page_num,
                'lines': [],
                'words': []
            }
            
            # Extract lines with positions (removed confidence as it's not available)
            for line in page.lines:
                page_content['lines'].append({
                    'text': line.content,
                    'bbox': line.polygon
                })
            
            # Extract individual words with positions
            for word in page.words:
                page_content['words'].append({
                    'text': word.content,
                    'bbox': word.polygon,
                    # Only include confidence if available
                    **({"confidence": word.confidence} if hasattr(word, "confidence") else {})
                })
            
            pages.append(page_content)
        
        return pages

    async def process_pdf_in_chunks(self, pdf_path: str) -> List[Dict]:
        """Process PDF one page at a time"""
        self.log("Splitting PDF into pages...")
        reader = PdfReader(pdf_path)
        results = []
        
        # Create a subdirectory for this document
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(pdf_path).stem if not self.is_url(pdf_path) else "document"
        doc_dir = self.output_dir / f"{base_name}_{timestamp}"
        doc_dir.mkdir(exist_ok=True)
        self.log(f"Saving pages to: {doc_dir}")
        
        for page_num in range(len(reader.pages)):
            self.log(f"Processing page {page_num + 1} of {len(reader.pages)}")
            # Create a new PDF with just this page
            writer = PdfWriter()
            writer.add_page(reader.pages[page_num])
            
            # Save single page to temp file
            temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            with open(temp.name, 'wb') as output_file:
                writer.write(output_file)
            
            try:
                # Process single page
                with open(temp.name, 'rb') as f:
                    poller = self.client.begin_analyze_document("prebuilt-read", f)
                    result = poller.result()
                    results.append(result)
                    
                    # Save this page's results immediately
                    page_result = {
                        'metadata': {
                            'page_number': page_num + 1,
                            'processed_datetime': datetime.now().isoformat(),
                        },
                        'pages': self.extract_text_with_layout(result),
                        'tables': self.extract_tables(result)
                    }
                    
                    # Save JSON result
                    json_path = doc_dir / f"page_{page_num + 1:03d}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(page_result, f, ensure_ascii=False, indent=2)
                    
                    # Save text
                    text_path = doc_dir / f"page_{page_num + 1:03d}.txt"
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(f"=== Page {page_num + 1} ===\n")
                        for line in page_result['pages'][0]['lines']:
                            f.write(f"{line['text']}\n")
                    
                    # Save tables if any
                    if page_result['tables']:
                        tables_path = doc_dir / f"page_{page_num + 1:03d}_tables.txt"
                        with open(tables_path, 'w', encoding='utf-8') as f:
                            for i, table in enumerate(page_result['tables'], 1):
                                f.write(f"\n=== Table {i} ===\n")
                                for row in table['data']:
                                    f.write(" | ".join(row) + "\n")
                    
                    self.log(f"Saved page {page_num + 1} results to {doc_dir}")
                    
            finally:
                os.unlink(temp.name)
        
        return results

    async def process_document(self, source: Union[str, bytes]) -> Dict:
        """Process document with OCR"""
        try:
            temp_file = None
            
            if isinstance(source, str):
                if self.is_url(source):
                    self.log("Processing URL document")
                    temp_file = await self.download_and_process_pdf(source)
                    results = await self.process_pdf_in_chunks(temp_file)
                else:
                    self.log("Processing local document")
                    results = await self.process_pdf_in_chunks(source)
            else:
                self.log("Processing bytes data")
                # Save bytes to temp file first
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                with open(temp_file.name, 'wb') as f:
                    f.write(source)
                results = await self.process_pdf_in_chunks(temp_file.name)

            # Combine results from all pages
            combined_output = {
                'metadata': {
                    'page_count': len(results),
                    'processed_datetime': datetime.now().isoformat(),
                    'source': str(source) if isinstance(source, str) else "bytes",
                },
                'pages': [],
                'tables': []
            }
            
            # Combine pages and tables from all results
            for result in results:
                combined_output['pages'].extend(self.extract_text_with_layout(result))
                combined_output['tables'].extend(self.extract_tables(result))
            
            return combined_output

        except Exception as e:
            self.log(f"Error processing document: {str(e)}")
            raise
        finally:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

    def save_results(self, results: Dict, original_filename: str):
        """Save processing results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(original_filename).stem
        
        # Save full results as JSON
        json_path = self.output_dir / f"{base_name}_{timestamp}_full.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Save extracted text (with layout info preserved)
        text_path = self.output_dir / f"{base_name}_{timestamp}_text.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            for page in results['pages']:
                f.write(f"\n=== Page {page['number']} ===\n")
                for line in page['lines']:
                    f.write(f"{line['text']}\n")
        
        # Save tables if any
        tables_path = None
        if results['tables']:
            tables_path = self.output_dir / f"{base_name}_{timestamp}_tables.txt"
            with open(tables_path, 'w', encoding='utf-8') as f:
                for i, table in enumerate(results['tables'], 1):
                    f.write(f"\n=== Table {i} ===\n")
                    for row in table['data']:
                        f.write(" | ".join(row) + "\n")
                    f.write("\n")

        # Create unified file combining all pages and tables
        unified_path = self.output_dir / f"{base_name}_{timestamp}_unified.txt"
        with open(unified_path, 'w', encoding='utf-8') as f:
            # Add document header
            f.write(f"Document: {base_name}\n")
            f.write(f"Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            # Add continuous text from all pages
            f.write("DOCUMENT TEXT\n")
            f.write("=" * 50 + "\n\n")
            for page in results['pages']:
                for line in page['lines']:
                    f.write(f"{line['text']}\n")
            
            # Add tables if present
            if results['tables']:
                f.write("\n\nDOCUMENT TABLES\n")
                f.write("=" * 50 + "\n\n")
                for i, table in enumerate(results['tables'], 1):
                    f.write(f"Table {i}\n")
                    f.write("-" * 20 + "\n")
                    for row in table['data']:
                        f.write(" | ".join(row) + "\n")
                    f.write("\n")
        
        return {
            'json': str(json_path),
            'text': str(text_path),
            'tables': str(tables_path) if tables_path else None,
            'unified': str(unified_path)
        }

async def main():
    processor = AzureOCRProcessor()
    
    print("\nAzure OCR Processor")
    print("Handles:")
    print("- Non-selectable PDFs")
    print("- Scanned documents")
    print("- Image-only PDFs")
    print("- Images (PNG, JPG, TIFF, etc.)")
    print("\nOptions:")
    print("1. Process single file")
    print("2. Process URL")
    print("3. Process all files in directory")
    print("4. Process files in a specific folder")
    print("5. Translate processed documents")
    
    choice = input("\nChoice (1-5): ")
    
    try:
        if choice == "1":
            path = input("Enter file path: ").strip()
            results = await processor.process_document(path)
            saved_files = processor.save_results(results, path)
            print("\nProcessing complete!")
            print(f"Text output: {saved_files['text']}")
            print(f"Unified output: {saved_files['unified']}")
            if saved_files['tables']:
                print(f"Tables output: {saved_files['tables']}")
            
        elif choice == "2":
            url = input("Enter document URL: ").strip()
            results = await processor.process_document(url)
            saved_files = processor.save_results(results, url.split('/')[-1])
            print("\nProcessing complete!")
            print(f"Text output: {saved_files['text']}")
            print(f"Unified output: {saved_files['unified']}")
            if saved_files['tables']:
                print(f"Tables output: {saved_files['tables']}")
            
        elif choice == "3":
            directory = input("Enter directory path (or press Enter for current): ").strip() or "."
            files = [f for f in os.listdir(directory) 
                    if f.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'))]
            
            if not files:
                print("No supported files found!")
                return
                
            print(f"\nFound {len(files)} files to process")
            for file in files:
                print(f"\nProcessing: {file}")
                path = os.path.join(directory, file)
                results = await processor.process_document(path)
                saved_files = processor.save_results(results, file)
                print(f"Text output: {saved_files['text']}")
                print(f"Unified output: {saved_files['unified']}")
                if saved_files['tables']:
                    print(f"Tables output: {saved_files['tables']}")
        
        elif choice == "4":
            specific_folder = Path.home() / "Documents" / "to_process"
            specific_folder.mkdir(parents=True, exist_ok=True)
            print(f"Place documents in the folder: {specific_folder}")
            
            files = [f for f in os.listdir(specific_folder) 
                    if f.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'))]
            
            if not files:
                print("No supported files found in the specific folder!")
                return
                
            print(f"\nFound {len(files)} files to process in the specific folder")
            for file in files:
                print(f"\nProcessing: {file}")
                path = specific_folder / file
                results = await processor.process_document(str(path))
                saved_files = processor.save_results(results, file)
                print(f"Text output: {saved_files['text']}")
                print(f"Unified output: {saved_files['unified']}")
                if saved_files['tables']:
                    print(f"Tables output: {saved_files['tables']}")
                
        elif choice == "5":
            translator = DocumentTranslator()
            print("\nTranslate processed documents")
            print("============================")
            
            input_dir = input("Enter directory with processed documents (press Enter for 'processed_documents'): ").strip() or "processed_documents"
            
            if not os.path.exists(input_dir):
                print(f"Directory not found: {input_dir}")
                return
                
            translator_main = __import__('azure_doctrans').main
            translator_main()
                
        else:
            print("Invalid choice!")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
