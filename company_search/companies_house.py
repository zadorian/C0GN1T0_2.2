import requests
import json
import PyPDF2
import os
import re
from typing import Optional, Dict, List, Any
import base64
from AI_models.gemini_flash_1_5 import generate_with_retry

class CompaniesHouseAPI:
    def __init__(self, ch_api_key):
        """Initialize with Companies House API key"""
        self.ch_api_key = ch_api_key
        self.base_url = "https://api.company-information.service.gov.uk"
        self.session = requests.Session()
        # Properly encode the API key for Basic Auth
        auth = base64.b64encode(f"{self.ch_api_key}:".encode('utf-8')).decode('utf-8')
        self.session.headers.update({'Authorization': f'Basic {auth}'})
        self.document_url = "https://document-api.company-information.service.gov.uk"
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'company_documents')
        os.makedirs(self.output_dir, exist_ok=True)

    def test_api_key(self):
        """Test if the API key is valid"""
        url = f"{self.base_url}/search/companies"
        params = {'q': 'test'}
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

    def search_company(self, company_name, items_per_page=100, advanced=False):
        """Search for a company using either basic or advanced search"""
        try:
            if advanced:
                # Use advanced search endpoint
                url = f"{self.base_url}/advanced-search/companies"
                params = {
                    'company_name_includes': company_name,
                    'size': items_per_page
                }
            else:
                # Use basic search endpoint
                url = f"{self.base_url}/search/companies"
                params = {
                    'q': company_name,
                    'items_per_page': items_per_page
                }
                
            response = self.session.get(url, params=params)
            response.raise_for_status()
            search_results = response.json()
            
            if search_results.get('items'):
                return search_results['items']
                
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching for company: {e}")
            return None

    def get_filing_history(self, company_number, category=None, items_per_page=100):
        """Get filing history for a company with optional filtering"""
        try:
            url = f"{self.base_url}/company/{company_number}/filing-history"
            params = {
                'items_per_page': items_per_page,
                'start_index': 0
            }
            if category:
                params['category'] = category
                
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting filing history: {e}")
            return None

    def download_document(self, document_id, output_file):
        """Download a document using the document API"""
        try:
            # First get document metadata
            metadata_url = f"{self.document_url}/document/{document_id}"
            metadata_response = self.session.get(metadata_url)
            metadata_response.raise_for_status()
            metadata = metadata_response.json()

            # Get document content URL
            if metadata.get('links', {}).get('document'):
                content_url = metadata['links']['document']
                
                # Request document content with PDF accept header
                headers = {'Accept': 'application/pdf'}
                content_response = self.session.get(
                    content_url, 
                    headers=headers, 
                    allow_redirects=True
                )
                content_response.raise_for_status()

                # Save the PDF
                output_path = os.path.join(self.output_dir, output_file)
                with open(output_path, 'wb') as f:
                    f.write(content_response.content)
                return output_path

            return None
        except requests.exceptions.RequestException as e:
            print(f"Error downloading document: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path):
        """Extract text content from a PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                # Create PDF reader object
                reader = PyPDF2.PdfReader(file)
                text = ""
                
                # Extract text from each page
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                    
                return text.strip()
                
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None

    def analyze_pdf_with_claude(self, pdf_path: str, prompt: str) -> Optional[str]:
        """Analyze PDF content using Gemini"""
        try:
            # Extract text from PDF first
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                return None
                
            # Use Gemini to analyze the text
            analysis_prompt = f"{prompt}\n\nDocument text:\n{text}"
            return generate_with_retry(analysis_prompt)
            
        except Exception as e:
            print(f"Error analyzing PDF with Gemini: {e}")
            return None

    def get_company_officers(self, company_number: str) -> List[Dict]:
        """Get officers (directors, secretaries etc) for a company"""
        endpoint = f"{self.base_url}/company/{company_number}/officers"
        response = self.session.get(endpoint)
        if response.status_code == 200:
            data = response.json()
            return data.get('items', [])
        return []

    def get_company_details(self, company_number: str) -> Dict:
        """Get detailed information about a specific company"""
        endpoint = f"{self.base_url}/company/{company_number}"
        response = self.session.get(endpoint)
        if response.status_code == 200:
            return response.json()
        return {} 