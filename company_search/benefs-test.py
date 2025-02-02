import os
import sys
import json
import time
import base64
import asyncio
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
import google.generativeai as genai

# Your local imports:
from claude_pdf_ocr import ClaudeProcessor
from prompts import get_ownership_analysis_prompt, get_ownership_history_prompt

# Load .env if present
load_dotenv()

#######################################
# 1) Get CH_API_KEY + optional GEMINI_API_KEY
#######################################
CH_API_KEY = os.getenv('CH_API_KEY', 'YOUR_COMPANIES_HOUSE_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# If Gemini key is set, configure it
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

#######################################
# 2) Your CompaniesHouseFilingFetcher code
#######################################
class CompaniesHouseFilingFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.base_url = "https://api.company-information.service.gov.uk"
        self.document_url = "https://document-api.company-information.service.gov.uk"
        self.session = requests.Session()
        self.session.auth = (self.api_key, '')

    def search_company_by_name(self, company_name: str, max_results: int = 5):
        url = f"{self.base_url}/search/companies"
        params = {"q": company_name, "items_per_page": max_results}
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    def get_company_filing_history(self, company_number: str):
        url = f"{self.base_url}/company/{company_number}/filing-history"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def download_document(self, document_id: str, output_path: str) -> bool:
        doc_url = f"{self.document_url}/document/{document_id}/content"
        try:
            r = self.session.get(doc_url)
            r.raise_for_status()
            with open(output_path, 'wb') as f:
                f.write(r.content)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"Successfully downloaded to {output_path}")
                return True
            else:
                print("Empty or missing file after download.")
                return False
        except Exception as e:
            print(f"Error downloading document {document_id}: {e}")
            return False

    # If you want to consider the company's basic profile:
    def get_company_profile(self, company_number: str) -> Optional[dict]:
        url = f"{self.base_url}/company/{company_number}"
        resp = self.session.get(url)
        if resp.status_code == 200:
            return resp.json()
        return None


#######################################
# 3) Check if a filing is relevant
#######################################
def is_relevant_for_ownership(filing_item: dict) -> bool:
    """
    We treat certain codes or keywords as "ownership-related," including incorporation.
    """
    ftype = filing_item.get('type', '').upper()
    desc = (filing_item.get('description','')).lower()

    # Incorporation references
    if "incorporation" in desc or "incorporation" in ftype:
        return True
    if any(code in ftype for code in ["NEWINC","IN01","CERTINC"]):
        return True

    # PSC docs
    if any(psc in ftype for psc in ['PSC', 'PSC01', 'PSC02', 'PSC03', 'PSC04']):
        return True

    # SHxx
    if any(share in ftype for share in ['SH01','SH02','SH03','SH04','SH05']):
        return True

    # Confirmation statements referencing shares
    if ftype in ['CS01','AR01'] and any(k in desc for k in ['statement of capital','shareholders','share capital','ownership']):
        return True

    # Additional keywords
    ownership_terms = [
        'person with significant control',
        'psc statement',
        'share allotment',
        'transfer of shares',
        'change in ownership'
    ]
    if any(o in desc for o in ownership_terms):
        return True

    return False

#######################################
# 4) Simple Gemini Summarizer
#######################################
class GeminiSummarizer:
    def __init__(self, gemini_api_key: str):
        # If we haven't already configured, do so
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
        self.genai = genai
        self.model = 'gemini-2.0-flash-exp'

    def generate_content(self, prompt: str, max_retries: int = 3, delay: float = 1.0) -> Optional[str]:
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
        prompt = get_ownership_analysis_prompt(doc_text, company_name, doc_date, doc_type)
        result = self.generate_content(prompt)
        return result if result else "Error: Could not analyze ownership info"

    def summarize_full_history(self, doc_list: List[Dict]) -> str:
        combined = ""
        for d in doc_list:
            combined += f"\n\n=== Document from {d['date']} ===\n{d['raw_text']}"
        prompt = get_ownership_history_prompt(combined)
        result = self.generate_content(prompt)
        return result if result else "Error: Could not produce full history"

#######################################
# 5) The main script
#######################################
async def main():
    print("\nChoose analysis mode:")
    print("1) Current ownership status (Earliest doc fallback if no changes)")
    print("2) Full ownership history chronology")
    mode = input("\nEnter 1 or 2: ").strip()

    if mode not in ["1","2"]:
        print("Invalid mode. Exiting.")
        return

    claude = ClaudeProcessor()
    gemini_summarizer = GeminiSummarizer(GEMINI_API_KEY)
    fetcher = CompaniesHouseFilingFetcher(CH_API_KEY)

    company_name_or_number = input("Enter a company number (or name) to check filings: ").strip()
    if not company_name_or_number:
        print("No input. Exiting.")
        return

    # 1) Identify a company
    if company_name_or_number.isdigit():
        cnum = company_name_or_number
        prof = fetcher.get_company_profile(cnum)
        cname = prof["company_name"] if prof else company_name_or_number
    else:
        results = fetcher.search_company_by_name(company_name_or_number, max_results=5)
        if not results:
            print(f"No results found for {company_name_or_number}")
            return
            
        # Show all results
        print("\nFound companies:")
        for idx, company in enumerate(results, 1):
            print(f"{idx}. {company['title']} ({company['company_number']})")
        choice = input(f"\nEnter number to select company (1-{len(results)}): ")
        try:
            company = results[int(choice) - 1]
            cnum = company['company_number']
            cname = company['title']
        except (ValueError, IndexError):
            print("Invalid selection")
            return

    # 2) Get filing history
    hist = fetcher.get_company_filing_history(cnum)
    items = hist.get("items", [])
    if not items:
        print("No filings found for that company. Exiting.")
        return

    # Filter relevant
    relevant = [f for f in items if is_relevant_for_ownership(f)]
    if not relevant:
        items_sorted = sorted(items, key=lambda x: x.get('date',''))
        earliest = items_sorted[0]
        relevant = [earliest]
        print("No recognized ownership docs. Will parse earliest doc (incorporation) anyway.")
    else:
        print(f"Found {len(relevant)} relevant (or incorporation) doc(s).")

    # 3) Output folder
    out_dir = Path(__file__).parent / "company_documents"
    out_dir.mkdir(exist_ok=True)

    # Process based on mode
    if mode == "1":
        print("\n=== CURRENT OWNERSHIP ===")
        # Get most recent relevant document
        most_recent = sorted(relevant, key=lambda x: x.get('date',''), reverse=True)[0]
        doc_id = most_recent['links']['document_metadata'].split('/')[-1]
        out_file = out_dir / f"{cnum}_{doc_id}.pdf"
        
        if fetcher.download_document(doc_id, str(out_file)):
            print("\nProcessing most recent document...")
            doc_text = await claude.process_document(str(out_file))
            if doc_text:
                result = gemini_summarizer.summarize_most_recent(
                    doc_text['raw_text'], 
                    cname,
                    most_recent.get("date"), 
                    most_recent.get("type")
                )
                print("\nCurrent Ownership Structure:")
                print(result)
                
                final_json = {
                    "company_number": cnum,
                    "company_name": cname,
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
                
                # Save results
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                outp = out_dir / f"{cnum}_ownership_1_{ts}.json"
                with open(outp, 'w', encoding='utf-8') as f:
                    json.dump(final_json, f, indent=2)
                print(f"\nResults saved to: {outp}")
            else:
                print("Error: Could not process document text")
        else:
            print("Error: Could not download document")
    else:
        # Full History (mode=2) logic remains the same
        print("\n=== FULL OWNERSHIP HISTORY ===")
        relevant_sorted = sorted(relevant, key=lambda x: x.get('date',''))
        doc_list = []
        for filing in relevant_sorted:
            doc_id = filing['links']['document_metadata'].split('/')[-1]
            out_pdf = out_dir / f"{cnum}_{doc_id}.pdf"
            if fetcher.download_document(doc_id, str(out_pdf)):
                doc_text = await claude.process_document(str(out_pdf))
                if doc_text:
                    doc_list.append({
                        "date": filing.get("date"),
                        "raw_text": doc_text.get("raw_text","")
                    })
        if not doc_list:
            print("No parseable docs for full history. Exiting.")
            return
        timeline = gemini_summarizer.summarize_full_history(doc_list)
        print("\nOwnership Timeline:\n")
        print(timeline)
        final_json = {
            "company_number": cnum,
            "company_name": cname,
            "mode": "ownership_history",
            "analysis_date": datetime.now().isoformat(),
            "documents": doc_list,
            "timeline_summary": timeline
        }
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        outp = out_dir / f"{cnum}_ownership_2_{ts}.json"
        with open(outp, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=2)
        print(f"\nFull history saved => {outp}")


if __name__ == "__main__":
    asyncio.run(main())