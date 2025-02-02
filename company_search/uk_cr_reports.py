# financial_reports.py

import os
import json
import base64
from pathlib import Path
from typing import Optional

# We'll assume your environment has these
from ch_ownership import CompaniesHouseFilingFetcher, ClaudeProcessor
from prompts import get_financial_report_prompt

# A set of "AA" type codes to identify annual accounts
FINANCIAL_CODES = {
    # Main 'AA' prefix
    'AA', 'AA01','AA02','AA03','AA04','AA05','AA06','AA07','AA08','AA09','AA10',
    'AA11','AA12','AA13','AA14','AA15','AA16','AA17','AA18','AA19','AA20','AA21',
    'AA22','AA23','AA24','AA25','AA26','AA27','AA28','AA29','AA30','AA31','AA32',
    'AA33','AA34','AA35','AA36','AA37','AA38','AA39','AA40','AA41','AA42','AA43',
    'AA44','AA45','AA46','AA47','AA48','AA49','AA50','AA51','AA52','AA53','AA54',
    'AA55','AA56','AA57','AA58'
}

def is_financial_report(filing_item: dict) -> bool:
    """
    Check if a filing is likely a financial report by:
     - The type code is in FINANCIAL_CODES, or
     - Description includes 'accounts'
    """
    ftype = filing_item.get('type','').upper()
    desc = filing_item.get('description','').lower()
    
    if ftype in FINANCIAL_CODES:
        return True

    # Additional check if 'accounts' is in description
    if 'account' in desc:
        return True

    return False

async def summarize_financial_report(
    fetcher: CompaniesHouseFilingFetcher,
    claude: ClaudeProcessor,
    company_number: str,
    filing: dict,
    output_dir: Path
) -> Optional[str]:
    """
    Download a financial report PDF, then pass it to Claude with a specialized prompt.
    Return the summarized text or None if something fails.
    """
    doc_link = filing.get('links',{}).get('document_metadata')
    if not doc_link:
        return None

    doc_id = doc_link.split('/')[-1]
    pdf_path = output_dir / f"{company_number}_{doc_id}.pdf"

    # Attempt download
    if not fetcher.download_document(doc_id, str(pdf_path)):
        return None

    try:
        # Read the PDF file as binary data
        with open(pdf_path, 'rb') as f:
            pdf_data = base64.b64encode(f.read()).decode('utf-8')

        # Process the document using Claude's document API
        message_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_data
                }
            },
            {
                "type": "text",
                "text": """Analyze this Companies House financial report focusing on:
1) Key financial figures (turnover, profits, net assets, liabilities, etc.)
2) Any individuals mentioned (directors, auditors, etc.) and the context
3) Any companies mentioned, especially if there's a group relationship or intercompany dealings
4) Any references to legal proceedings or potential adverse info

Return a concise textual summary. Do NOT provide disclaimers."""
            }
        ]
        
        resp = claude.client.beta.messages.create(
            model=claude.model,
            betas=["pdfs-2024-09-25"],
            max_tokens=claude.max_tokens,
            messages=[{"role": "user", "content": message_content}]
        )
        if resp and resp.content:
            return resp.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] Summarizing financial report: {e}")

    return None