import os
import aiohttp
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from claude_pdf_ocr import ClaudeProcessor  # Import your existing OCR code

# Load environment variables
load_dotenv()

class AlephPDFProcessor:
    def __init__(self):
        self.api_key = os.getenv('ALEPH_API_KEY')
        self.base_url = os.getenv('ALEPH_API_URL', 'https://aleph.occrp.org/api/2/')
        self.headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Accept': 'application/json'
        }
        self.claude_processor = ClaudeProcessor()
        
        # Set up directories
        self.root_dir = Path(__file__).parent
        self.download_dir = self.root_dir / "downloaded_pdfs"
        self.download_dir.mkdir(exist_ok=True)

    async def _make_request(self, endpoint: str, method: str = 'GET', params: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to the Aleph API"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            try:
                async with session.request(method, url, headers=self.headers, params=params) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                print(f"Error making request to {url}: {str(e)}")
                raise

    async def search_documents(self, query: str, file_types: List[str] = ['pdf']) -> List[Dict]:
        """Search for documents in Aleph"""
        try:
            params = {
                'q': query,
                'filter:schema': 'Document',
                'filter:extension': ','.join(file_types)
            }
            results = await self._make_request('documents', params=params)
            return results.get('results', [])
        except Exception as e:
            print(f"Error searching documents: {str(e)}")
            return []

    async def download_document(self, document_id: str) -> Optional[Path]:
        """Download a document from Aleph"""
        try:
            # Get document metadata first
            doc_info = await self._make_request(f'documents/{document_id}')
            
            # Get download URL
            file_url = doc_info.get('links', {}).get('file')
            if not file_url:
                print(f"No download URL found for document {document_id}")
                return None

            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{document_id}_{timestamp}.pdf"
            file_path = self.download_dir / filename

            # Download file
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url, headers=self.headers) as response:
                    response.raise_for_status()
                    with open(file_path, 'wb') as f:
                        f.write(await response.read())

            return file_path

        except Exception as e:
            print(f"Error downloading document {document_id}: {str(e)}")
            return None

    async def process_document(self, doc_path: Path) -> Dict:
        """Process a document using Claude"""
        try:
            return await self.claude_processor.process_document(str(doc_path))
        except Exception as e:
            print(f"Error processing document with Claude: {str(e)}")
            return {}

    async def process_search_results(self, query: str, max_docs: int = 5):
        """Search, download, and process documents"""
        # Search for documents
        documents = await self.search_documents(query)
        print(f"\nFound {len(documents)} matching documents")

        # Process up to max_docs
        for i, doc in enumerate(documents[:max_docs]):
            doc_id = doc.get('id')
            print(f"\nProcessing document {i+1}/{min(max_docs, len(documents))}: {doc_id}")

            # Download
            pdf_path = await self.download_document(doc_id)
            if not pdf_path:
                continue

            # Process with Claude
            results = await self.process_document(pdf_path)
            if results:
                self.claude_processor.save_results(results, pdf_path.name)

            # Clean up downloaded PDF
            pdf_path.unlink(missing_ok=True)

async def main():
    processor = AlephPDFProcessor()
    
    # Get search query from user
    query = input("\nEnter search query for documents: ").strip()
    max_docs = int(input("Maximum number of documents to process: ").strip())
    
    print(f"\nSearching for '{query}' in Aleph...")
    await processor.process_search_results(query, max_docs)
    print("\nProcessing complete!")

if __name__ == "__main__":
    asyncio.run(main())