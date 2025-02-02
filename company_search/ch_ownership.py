import os
import requests
import base64
from datetime import datetime
import json
from anthropic import Anthropic
from dotenv import load_dotenv
import sys
from pathlib import Path
from claude_pdf_ocr import ClaudeProcessor  # Changed to use your working file
from typing import Dict, List, Optional
import google.generativeai as genai  # Add Gemini import
import asyncio
import time  # Add this import

# Import prompts from the same directory
from prompts import get_ownership_analysis_prompt, get_ownership_history_prompt

# Load environment variables
load_dotenv()

###############################################
# Replace this with your own config or environment
CH_API_KEY = os.getenv('CH_API_KEY', 'YOUR_COMPANIES_HOUSE_API_KEY')
###############################################

# Configure APIs
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class ClaudeProcessor:
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = "claude-3-5-sonnet-20241022"  # Updated to working model
        self.max_tokens = 4096
        
        # Set up output directory
        self.root_dir = Path(__file__).parent
        self.output_dir = self.root_dir / "company_documents"  # Changed to company_documents
        self.output_dir.mkdir(exist_ok=True)

    async def process_document(self, file_path: str) -> dict:
        """Process a document file and return the extracted information"""
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
                                "text": "Please analyze this Companies House filing document and extract all key information about ownership, shareholding, or person of significant control changes. Include specific details about ownership percentages, share classes, and dates of changes where available."
                            }
                        ]
                    }
                ]
            )

            # Structure the output exactly like the working code
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

class CompaniesHouseFilingFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.base_url = "https://api.company-information.service.gov.uk"
        self.document_url = "https://document-api.company-information.service.gov.uk"
        self.session = requests.Session()
        self.session.auth = (self.api_key, '')

    def search_company_by_name(self, company_name: str, max_results: int = 5):
        """Search for a company by name and return up to max_results items."""
        url = f"{self.base_url}/search/companies"
        params = {"q": company_name, "items_per_page": max_results}
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    def get_company_filing_history(self, company_number: str):
        """Fetch the entire filing history for a given company_number."""
        url = f"{self.base_url}/company/{company_number}/filing-history"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def download_document(self, document_id: str, output_path: str) -> bool:
        """
        Download a specific Companies House filing PDF by its document_id.
        Save it to output_path. Return True if successful.
        """
        doc_url = f"{self.document_url}/document/{document_id}/content"
        try:
            r = self.session.get(doc_url)
            r.raise_for_status()
            
            # Debug print
            print(f"Download status: {r.status_code}")
            print(f"Content type: {r.headers.get('content-type')}")
            print(f"Content length: {len(r.content)} bytes")
            
            with open(output_path, 'wb') as f:
                f.write(r.content)
            
            # Verify file exists and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"Successfully downloaded to {output_path}")
                return True
            else:
                print(f"File download failed - empty or missing file")
                return False
                
        except Exception as e:
            print(f"Error downloading document {document_id}: {e}")
            return False

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file and return it as a string."""
        # This method needs to be implemented based on the actual implementation
        # of the Companies House document API. For now, it's a placeholder.
        return None

def is_relevant_for_ownership(filing_item: dict) -> bool:
    """
    Determine if a filing is relevant for ownership analysis.
    """
    ftype = filing_item.get('type', '').upper()
    desc = filing_item.get('description', '').lower()
    
    # PSC-related filings
    if any(psc in ftype for psc in ['PSC', 'PSC01', 'PSC02', 'PSC03', 'PSC04']):
        return True
        
    # Share capital and allotment filings
    if any(share in ftype for share in ['SH01', 'SH02', 'SH03', 'SH04', 'SH05']):
        return True
        
    # Confirmation statements and annual returns (only if they mention shares/shareholders)
    if ftype in ['CS01', 'AR01'] and any(term in desc for term in [
        'statement of capital',
        'shareholders',
        'shareholding',
        'share capital',
        'ownership'
    ]):
        return True
        
    # Additional ownership-related terms in description
    ownership_terms = [
        'person with significant control',
        'psc statement',
        'share allotment',
        'transfer of shares',
        'change in ownership'
    ]
    
    return any(term in desc for term in ownership_terms)

class GeminiSummarizer:
    def __init__(self, gemini_api_key: str):
        genai.configure(api_key=gemini_api_key)
        self.genai = genai
        self.model = 'gemini-2.0-flash-exp'

    def generate_content(self, prompt: str, max_retries: int = 3, delay: float = 1.0) -> Optional[str]:
        """Generate content using Gemini with retry logic"""
        model = self.genai.GenerativeModel(self.model)
        
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text.strip()
                else:
                    print(f"Empty response on attempt {attempt + 1}")
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    print("Max retries reached")
                    return None
                    
        return None

    def summarize_most_recent(self, doc_text: str, company_name: str, doc_date: str, doc_type: str) -> str:
        """Mode 1: Get current ownership from most recent document"""
        prompt = get_ownership_analysis_prompt(doc_text, company_name, doc_date, doc_type)
        result = self.generate_content(prompt)
        return result if result else "Error: Could not analyze ownership information"

    def summarize_full_history(self, doc_list: List[Dict]) -> str:
        """Mode 2: Build chronological ownership history"""
        combined_text = ""
        for doc in doc_list:
            combined_text += f"\n\n=== Document from {doc['date']} ===\n{doc['raw_text']}"
        
        prompt = get_ownership_history_prompt(combined_text)
        result = self.generate_content(prompt)
        return result if result else "Error: Could not analyze ownership history"

async def main():
    print("\nChoose analysis mode:")
    print("1) Current ownership status (most recent only)")
    print("2) Full ownership history chronology")
    mode = input("\nEnter 1 or 2: ").strip()

    if mode not in ["1", "2"]:
        print("Invalid mode selected. Exiting.")
        return

    # Initialize processors
    claude = ClaudeProcessor()  # Changed to use ClaudeProcessor
    gemini_summarizer = GeminiSummarizer(GEMINI_API_KEY)  # Initialize GeminiSummarizer
    
    company_number_or_name = input("Enter a company number (or name) to check filings: ").strip()
    if not company_number_or_name:
        print("No input provided; exiting.")
        return
    
    fetcher = CompaniesHouseFilingFetcher(CH_API_KEY)
    
    # Create output directory for documents
    output_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'company_documents'  # Changed to company_documents
    output_dir.mkdir(exist_ok=True)

    # Search logic
    if not company_number_or_name.isdigit():
        results = fetcher.search_company_by_name(company_number_or_name, max_results=5)
        if not results:
            print(f"No companies found matching name: {company_number_or_name}")
            return
            
        # Check for exact name match first
        exact_matches = [company for company in results 
                        if company['title'].lower() == company_number_or_name.lower()]
        
        if len(exact_matches) == 1:
            # Single exact match - use it directly
            company = exact_matches[0]
            company_number = company['company_number']
            company_name = company['title']
        elif len(exact_matches) > 1:
            # Multiple exact matches - let user choose
            print("\nMultiple companies found with exact name:")
            for idx, company in enumerate(exact_matches, 1):
                print(f"{idx}. {company['title']} ({company['company_number']})")
            choice = input(f"\nEnter number to select company (1-{len(exact_matches)}): ")
            try:
                company = exact_matches[int(choice) - 1]
                company_number = company['company_number']
                company_name = company['title']
            except (ValueError, IndexError):
                print("Invalid selection")
                return
        else:
            # No exact match - show all similar results
            print("\nFound companies:")
            for idx, company in enumerate(results, 1):
                print(f"{idx}. {company['title']} ({company['company_number']})")
            choice = input(f"\nEnter number to select company (1-{len(results)}): ")
            try:
                company = results[int(choice) - 1]
                company_number = company['company_number']
                company_name = company['title']
            except (ValueError, IndexError):
                print("Invalid selection")
                return
    else:
        company_number = company_number_or_name

    # Get and sort filings by date
    hist = fetcher.get_company_filing_history(company_number)
    items = hist.get("items", [])
    if not items:
        print("No filings found.")
        return

    # Filter relevant ownership documents
    relevant = [f for f in items if is_relevant_for_ownership(f)]
    if not relevant:
        print("No ownership-related filings found.")
        return

    # Process documents based on selected mode
    if mode == "1":
        # MODE 1: Only process most recent document
        print("\n=== CURRENT OWNERSHIP STATUS ===")
        most_recent = relevant[0]  # Already sorted newest first
        doc_id = most_recent['links']['document_metadata'].split('/')[-1]
        out_file = output_dir / f"{company_number}_{doc_id}.pdf"
        
        if fetcher.download_document(doc_id, str(out_file)):
            doc_text = await claude.process_document(str(out_file))
            if doc_text:
                result = gemini_summarizer.summarize_most_recent(doc_text['raw_text'], company_name, most_recent.get("date"), most_recent.get("type"))
                print("\nCurrent Ownership Structure:")
                print(result)
                
                # Save results
                final_json = {
                    "company_number": company_number,
                    "company_name": company_name,
                    "mode": "current_ownership",
                    "analysis_date": datetime.now().isoformat(),
                    "most_recent_filing": {
                        "date": most_recent.get("date"),
                        "type": most_recent.get("type"),
                        "description": most_recent.get("description"),
                        "file_path": str(out_file),
                        "raw_text": doc_text.get("raw_text"),
                        "ownership_summary": result
                    }
                }
    else:
        # MODE 2: Process all documents chronologically
        print("\n=== OWNERSHIP HISTORY CHRONOLOGY ===")
        doc_list = []
        
        # Process from oldest to newest
        for filing in sorted(relevant, key=lambda x: x.get('date', '')):
            doc_id = filing['links']['document_metadata'].split('/')[-1]
            out_file = output_dir / f"{company_number}_{doc_id}.pdf"
            
            if fetcher.download_document(doc_id, str(out_file)):
                doc_text = await claude.process_document(str(out_file))
                if doc_text:
                    doc_list.append({
                        "date": filing.get("date"),
                        "raw_text": doc_text.get("raw_text")
                    })
        
        if doc_list:
            result = gemini_summarizer.summarize_full_history(doc_list)
            print("\nOwnership Timeline:")
            print(result)
            
            # Save results
            final_json = {
                "company_number": company_number,
                "company_name": company_name,
                "mode": "ownership_history",
                "analysis_date": datetime.now().isoformat(),
                "documents": doc_list,
                "timeline_summary": result
            }

    # Save final JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = output_dir / f"{company_number}_ownership_{mode}_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2)
    print(f"\nFull analysis saved to: {out_path}")

if __name__ == "__main__":
    asyncio.run(main())