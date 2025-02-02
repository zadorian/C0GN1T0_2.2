import os
import sys
from pathlib import Path
import json

# Add the social_media directory to Python path
sys.path.append(str(Path(__file__).parent.parent / "social_media"))

from azure_doc import AzureOCRProcessor
from claude_pdf_ocr import ClaudeProcessor
import aiohttp
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from dotenv import load_dotenv
import re
import PyPDF2

load_dotenv()

class AlephPDFProcessor:
    def __init__(self):
        self.api_key = "1c0971afa4804c2aafabb125c79b275e"
        self.base_url = "https://aleph.occrp.org/api/2"
        self.headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Accept': 'application/json'
        }
        self.claude_processor = ClaudeProcessor()
        self.azure_processor = AzureOCRProcessor()
        
        self.root_dir = Path(__file__).parent
        self.companies_dir = self.root_dir / "company_documents"
        self.companies_dir.mkdir(exist_ok=True)

    def get_safe_filename(self, text: str) -> str:
        """Convert text to safe filename"""
        safe = re.sub(r'[<>:"/\\|?*]', '', text)
        safe = re.sub(r'\s+', '_', safe.strip())
        return safe[:100]

    async def _make_request(self, endpoint: str, method: str = 'GET', params: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to the Aleph API"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            try:
                print(f"\nMaking request to: {url}")
                print(f"With params: {params}")
                
                async with session.request(method, url, headers=self.headers, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    print(f"Response status: {response.status}")
                    return data
            except aiohttp.ClientError as e:
                print(f"Error making request to {url}: {str(e)}")
                raise

    async def search_documents(self, query: str) -> List[Dict]:
        """Search for documents in Aleph"""
        search_url = f"{self.base_url}/entities"
        all_documents = []
        offset = 0
        limit = 50  # Keep at 50 as in working version

        while True:
            params = {
                'q': query,
                'filter:schema': 'Document',
                'limit': limit,
                'offset': offset
            }

            try:
                print(f"\nSearching with offset: {offset}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=self.headers, params=params) as response:
                        response.raise_for_status()
                        search_results = await response.json()
                        
                        results = search_results.get('results', [])
                        if not results:
                            break

                        print(f"Found {len(results)} documents in this batch")
                        for doc in results:
                            links = doc.get('links', {})
                            if links.get('file') or links.get('pdf'):
                                print(f"Found document with content: {doc.get('properties', {}).get('title', ['Untitled'])[0]}")
                                all_documents.append(doc)

                        # Use exact pagination check from working code
                        if 'next' not in search_results.get('links', {}):
                            break
                        
                        offset += limit

            except Exception as e:
                print(f"Error during search: {str(e)}")
                break

        print(f"\nTotal documents with downloadable content: {len(all_documents)}")
        return all_documents

    async def download_document(self, document: Dict) -> Optional[Dict]:
        """Download a document from Aleph and return content info"""
        try:
            # First try to get text content directly from properties
            properties = document.get('properties', {})
            text_content = properties.get('bodyText', [None])[0] or properties.get('text', [None])[0]
            
            if text_content:
                print("Found text content in document properties")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                title = properties.get('title', ['document'])[0]
                safe_title = self.get_safe_filename(title)
                
                filename = f"{timestamp}_{safe_title}.txt"
                file_path = self.companies_dir / filename
                
                # Save the text content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                print(f"Successfully saved text content to: {file_path}")
                
                return {
                    'path': file_path,
                    'type': 'text',
                    'size': len(text_content)
                }
            
            # If no text in properties, try downloading from URL
            links = document.get('links', {})
            file_url = links.get('file') or links.get('pdf') or links.get('archive')
            if not file_url:
                print(f"No download URL found for document")
                return None

            # Get filename from title
            title = properties.get('title', ['document'])[0]
            safe_title = self.get_safe_filename(title)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            print(f"\nDownloading: {title}")
            print(f"From URL: {file_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url, headers=self.headers, allow_redirects=True) as response:
                    response.raise_for_status()
                    content = await response.read()
                    
                    if not content:
                        print("Warning: Empty response from URL")
                        return None
                        
                    content_type = response.headers.get('Content-Type', '').lower()
                    print(f"Content type from headers: {content_type}")
                    print(f"Content length: {len(content)} bytes")
                    
                    # Process based on content type
                    if 'html' in content_type or content.startswith(b'<!DOCTYPE') or content.startswith(b'<html'):
                        text_content = content.decode('utf-8', errors='ignore')
                        print(f"Raw HTML length: {len(text_content)} chars")
                        
                        # Get the actual content from the response
                        if '<body' in text_content:
                            body_match = re.search(r'<body[^>]*>(.*?)</body>', text_content, re.DOTALL)
                            if body_match:
                                text_content = body_match.group(1)
                        
                        # Process HTML as before...
                        text_content = re.sub(r'<script.*?</script>', '', text_content, flags=re.DOTALL)
                        text_content = re.sub(r'<style.*?</style>', '', text_content, flags=re.DOTALL)
                        text_content = re.sub(r'&nbsp;', ' ', text_content)
                        text_content = re.sub(r'&amp;', '&', text_content)
                        text_content = re.sub(r'&lt;', '<', text_content)
                        text_content = re.sub(r'&gt;', '>', text_content)
                        text_content = re.sub(r'&quot;', '"', text_content)
                        text_content = re.sub(r'&#39;', "'", text_content)
                        text_content = re.sub(r'<br[^>]*>', '\n', text_content)
                        text_content = re.sub(r'<p[^>]*>', '\n\n', text_content)
                        text_content = re.sub(r'<div[^>]*>', '\n', text_content)
                        text_content = re.sub(r'<li[^>]*>', '\n- ', text_content)
                        text_content = re.sub(r'<h\d[^>]*>', '\n\n', text_content)
                        text_content = re.sub(r'</h\d>', '\n', text_content)
                        text_content = re.sub(r'<[^>]+>', ' ', text_content)
                        text_content = re.sub(r'\s+', ' ', text_content)
                        text_content = re.sub(r'\n\s+\n', '\n\n', text_content)
                        text_content = text_content.strip()
                        
                        paragraphs = [p.strip() for p in text_content.split('\n') if p.strip()]
                        text_content = '\n\n'.join(paragraphs)
                        
                        if not text_content.strip():
                            print("Warning: No text content extracted from HTML")
                            return None
                            
                        processed_content = text_content.encode('utf-8')
                        ext = '.txt'
                        
                    elif content.startswith(b'%PDF'):
                        ext = '.pdf'
                        processed_content = content
                    else:
                        try:
                            text_content = content.decode('utf-8', errors='ignore').strip()
                            if not text_content:
                                print("Warning: Empty text content")
                                return None
                            ext = '.txt'
                            processed_content = text_content.encode('utf-8')
                        except UnicodeDecodeError:
                            print(f"Unable to determine content type")
                            return None
                    
                    filename = f"{timestamp}_{safe_title}{ext}"
                    file_path = self.companies_dir / filename
                    
                    with open(file_path, 'wb') as f:
                        f.write(processed_content)
                        print(f"Successfully downloaded to: {file_path}")
                    
                    return {
                        'path': file_path,
                        'type': 'pdf' if ext == '.pdf' else 'text',
                        'size': len(processed_content)
                    }

        except Exception as e:
            print(f"Error downloading document: {str(e)}")
            return None

    def is_image_pdf(self, pdf_path: str) -> bool:
        """Check if PDF contains only images/scanned content"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf = PyPDF2.PdfReader(file)
                page = pdf.pages[0]  # Check first page
                if '/Font' not in page['/Resources']:
                    return True  # No fonts found, likely an image PDF
                return False
        except:
            return True  # If we can't determine, better to use Claude

    async def process_document(self, file_path: str) -> None:
        """Process document - directly read text files, use Azure for PDFs"""
        print(f"Processing: {file_path}")
        
        try:
            if file_path.endswith('.txt'):
                # For text files, just read and display content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    
                if not content:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Empty file")
                    return
                
                print("\nDocument Content:")
                print("=" * 80)
                print(content)
                print("=" * 80)
                
            else:
                # For PDFs and other files, use Azure Form Recognizer
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing with Azure Form Recognizer")
                async with self.form_recognizer_client:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    poller = await self.form_recognizer_client.begin_analyze_document(
                        "prebuilt-document", document=content
                    )
                    result = await poller.result()
                    
                    # Process and save results
                    output_path = file_path.replace('.pdf', '_analysis.json')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(result.to_dict(), f, indent=2)
                        
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Analysis saved to: {output_path}")
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error processing document: {str(e)}")
            return

    async def process_search_results(self, query: str, max_docs: int = 5):
        """Process search results"""
        documents = await self.search_documents(query)
        if not documents:
            print("\nNo documents found matching the search criteria")
            return

        print(f"\nProcessing up to {max_docs} documents out of {len(documents)} found")

        for i, doc in enumerate(documents[:max_docs]):
            print(f"\n{'='*50}")
            print(f"Processing document {i+1}/{min(max_docs, len(documents))}")
            
            properties = doc.get('properties', {})
            title = properties.get('title', ['Untitled'])[0]
            company_name = properties.get('parent', {}).get('name', [None])[0] or \
                         properties.get('company', [None])[0] or \
                         query
            
            print(f"Title: {title}")
            print(f"Company: {company_name}")
            print(f"Collection: {doc.get('collection', {}).get('label', 'Unknown')}")
            print(f"{'='*50}")

            doc_info = await self.download_document(doc)
            if doc_info:
                await self.process_document(doc_info['path'])

async def main():
    processor = AlephPDFProcessor()
    
    try:
        query = input("\nEnter search query for documents: ").strip()
        # Wrap query in quotes for exact matching
        query = f'"{query}"'
        
        print(f"\nSearching for {query} in Aleph...")
        await processor.process_search_results(query, max_docs=5)  # Default to 5 documents
        print("\nProcessing complete!")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())