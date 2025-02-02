import os
import sys
import json
import time
import base64
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set, Optional

from dotenv import load_dotenv

# "ch_ownership" should contain:
#   - CH_API_KEY, GEMINI_API_KEY
#   - CompaniesHouseFilingFetcher
#   - ClaudeProcessor
#   - Possibly older is_relevant_for_ownership, but we override that below
from ch_ownership import (
    CH_API_KEY,
    GEMINI_API_KEY,
    CompaniesHouseFilingFetcher,
    ClaudeProcessor
)

##################################################
# 1) Our updated is_relevant_for_ownership function
##################################################
def is_relevant_for_ownership(filing_item: dict) -> bool:
    """
    Determine if a filing is relevant for ownership analysis based on Companies House document codes.
    """
    ftype = filing_item.get('type', '').upper()
    desc = filing_item.get('description', '').lower()

    # Core ownership documents
    ownership_docs = {
        # Incorporation
        'IN01',  # Application to register a company

        # PSC (Persons with Significant Control)
        'PSC01', 'PSC02', 'PSC03', 'PSC04', 'PSC05',
        'PSC06', 'PSC07', 'PSC08', 'PSC09',

        # Share Capital
        'SH01', 'SH02', 'SH03', 'SH04', 'SH05', 'SH06', 'SH07', 'SH08', 'SH09',

        # Annual/Confirmation
        'CS01', 'AR01',

        # Overseas Companies
        'OSIN01', 'OSAP01', 'OSCH03', 'OSAP03', 'OSCH05', 'OSAP05', 'OSCH07',

        # Societas Europaea (SE)
        'SEF01', 'SEF02', 'SEF03', 'SEF04', 'SEF05', 'SEF06', 'SEF07', 'SEF08',
        'SEF09', 'SEF10', 'SEF11', 'SEF12', 'SEF13', 'SEF14', 'SEF15', 'SEF16',
        'SEF17', 'SEF18', 'SEF19', 'SEF20', 'SECH01', 'SECH02', 'SECH03', 'SECH04',
        'SESH01', 'SESH02', 'SESH03', 'SESH04',
    }

    if ftype in ownership_docs:
        return True

    # Check description for relevant terms
    ownership_terms = {
        'person with significant control',
        'psc statement',
        'share',
        'shareholder',
        'ownership',
        'incorporation',
        'subsidiary',
        'holding company',
        'parent company',
        'group structure',
        'corporate group',
        'beneficial owner',
        'ultimate owner',
        'controlling interest',
        'voting rights',
        'members register',
        'transfer of business',
        'merger',
        'acquisition',
        'reorganisation',
        'restructure',
        'demerger',
        'joint venture',
    }
    return any(term in desc for term in ownership_terms)

# Gemini summarizer pieces
from AI_models.gemini_flash_1_5 import generate_with_retry
from prompts import (
    get_ownership_structure_prompt,
    get_ownership_chain_summary_prompt,
    get_psc_ownership_prompt
)

load_dotenv()

############################################
# 2) Extend the fetcher with get_company_profile if needed
############################################
def add_profile_method_if_missing():
    def get_company_profile(self, company_number: str) -> Optional[dict]:
        url = f"{self.base_url}/company/{company_number}"
        r = self.session.get(url)
        if r.status_code == 200:
            return r.json()
        return None

    if not hasattr(CompaniesHouseFilingFetcher, "get_company_profile"):
        setattr(CompaniesHouseFilingFetcher, 'get_company_profile', get_company_profile)

add_profile_method_if_missing()

############################################
# 3) Patch ClaudeProcessor to enforce JSON-only
############################################
def patch_claude_processor():
    async def process_document_strict_json(self, file_path: str, second_attempt: bool=False) -> str:
        """
        Forces Claude to return ONLY JSON. If attempt fails, we try second_attempt = True
        with an even more strict prompt.
        """
        with open(file_path, 'rb') as f:
            pdf_b64 = base64.b64encode(f.read()).decode('utf-8')

        instructions = (
            "Analyze this Companies House filing focusing on PSC/shareholding data.\n"
            "Return ONLY a valid JSON object with the structure:\n\n"
            "{\n"
            "  \"owners\": [\n"
            "    {\n"
            "      \"name\": \"string\",\n"
            "      \"type\": \"individual|corporate|other\",\n"
            "      \"percentage\": number|null,\n"
            "      \"shares\": \"string or null\",\n"
            "      \"nature_of_control\": [\"...\"],\n"
            "      \"details\": {\n"
            "         \"company_number\": \"string or null\",\n"
            "         \"nationality\": \"string or null\",\n"
            "         \"country_of_residence\": \"string or null\"\n"
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "No extra commentary or text. If no data, return {\"owners\": []}.\n"
        )
        if second_attempt:
            instructions += "\nSTOP. Return ONLY JSON. Nothing else."

        message_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_b64
                }
            },
            {
                "type": "text",
                "text": instructions
            }
        ]
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                betas=["pdfs-2024-09-25"],
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": message_content}]
            )
            if resp and resp.content:
                return resp.content[0].text
            return ""
        except Exception as e:
            print(f"Claude JSON prompt error: {e}")
            return ""

    ClaudeProcessor.process_document_strict_json = process_document_strict_json

patch_claude_processor()

############################################
# 3) BFS Ownership Tracer
#    * Process ALL relevant docs for each company
#    * Merge discovered owners
#    * BFS corporate owners
############################################
class OwnershipTracer:
    def __init__(self):
        self.fetcher = CompaniesHouseFilingFetcher(CH_API_KEY)
        self.claude = ClaudeProcessor()
        self.output_dir = Path(__file__).parent / "company_documents"
        self.output_dir.mkdir(exist_ok=True)
        
        # BFS tracking
        self.visited: Set[str] = set()
        self.chain_data = {
            "target_company": None,
            "ownership": {}
        }

    def _strip_ltd(self, name: str) -> str:
        return (
            name.lower()
            .replace("limited","")
            .replace("ltd","")
            .strip()
        )

    async def trace_ownership(self, query: str, depth: int=0, max_depth: int=5):
        norm = query.strip().lower()
        if norm in self.visited:
            print(f"[SKIP] Already processed: {query}")
            return
        if depth > max_depth:
            print(f"[DEPTH] Reached max depth ({max_depth}) at: {query}")
            return

        print(f"\n[TRACE] Processing {query} at depth {depth}")
        self.visited.add(norm)

        # 1) Identify company_number + official_name
        cnum, cname = None, None
        if query.isdigit():
            prof = self.fetcher.get_company_profile(query)
            if not prof:
                print(f"[ERROR] No profile found: {query}")
                return
            cnum = query
            cname = prof.get("company_name","UNKNOWN")
        else:
            base_name = self._strip_ltd(query)
            results = self.fetcher.search_company_by_name(base_name, max_results=5)
            if not results:
                print(f"[ERROR] No results found: {query}")
                return
            for r in results:
                if self._strip_ltd(r['title']) == base_name:
                    cnum = r['company_number']
                    cname = r['title']
                    break
            if not cnum:
                print(f"[ERROR] No exact match found: {query}")
                return

        # For the top-level
        if depth == 0 and not self.chain_data["target_company"]:
            self.chain_data["target_company"] = cname

        # 2) Get only newest relevant doc
        hist = self.fetcher.get_company_filing_history(cnum)
        if not hist or not hist.get("items"):
            print(f"No filings for {cname} ({cnum}).")
            return

        items = hist["items"]
        items.sort(key=lambda x: x.get('date',''), reverse=True)
        
        print("\nChecking newest documents for ownership information:")
        newest_relevant = None
        
        # Find newest relevant doc
        for filing in items:
            if is_relevant_for_ownership(filing):
                newest_relevant = filing
                ftype = filing.get('type', '').upper()
                date = filing.get('date', 'unknown')
                print(f"  → Found newest relevant doc: {date} | {ftype}")
                break
        
        if not newest_relevant:
            print(f"No relevant ownership docs for {cname} ({cnum}).")
            return

        # Process only newest doc
        company_dir = self.output_dir / cnum
        company_dir.mkdir(exist_ok=True)

        doc_date = newest_relevant.get('date')
        doc_type = newest_relevant.get('type')
        doc_id = newest_relevant['links']['document_metadata'].split('/')[-1]
        pdf_path = company_dir / f"{doc_type}_{doc_date}.pdf"

        print(f"  [DOC] Processing: {doc_type} ({doc_date})")
        if not self.fetcher.download_document(doc_id, str(pdf_path)):
            print(f"  [SKIP] Failed to download document")
            return

        owners_data = await self.get_claude_json(pdf_path)
        if owners_data is None:
            print(f"  [SKIP] Failed to parse document")
            return

        # Store in chain data
        if cname not in self.chain_data["ownership"]:
            self.chain_data["ownership"][cname] = {
                "company_number": cnum,
                "filings": []
            }

        doc_info = {
            "doc_date": doc_date,
            "doc_type": doc_type,
            "owners": owners_data.get("owners", [])
        }
        self.chain_data["ownership"][cname]["filings"].append(doc_info)

        # Log found owners
        all_owners = owners_data.get("owners", [])
        if all_owners:
            print(f"[FOUND] {cname} ({cnum}) has {len(all_owners)} owners:")
            for o in all_owners:
                owner_type = o.get("type", "unknown")
                owner_name = o.get("name", "unnamed")
                pct = o.get("percentage", "unknown %")
                print(f"  → {owner_name} ({owner_type}, {pct}%)")
        else:
            print(f"[INFO] No ownership data found in newest doc")

        # BFS expansion for corporate owners
        corporate_owners = [o for o in all_owners if o.get("type") == "corporate"]
        if corporate_owners:
            print(f"\n[BFS] Expanding {len(corporate_owners)} corporate owners...")

        for owner in corporate_owners:
            csub = owner.get("details", {}).get("company_number")
            if csub and csub.isdigit():
                await self.trace_ownership(csub, depth + 1, max_depth)
            else:
                oname = owner.get("name", "").strip()
                if oname:
                    await self.trace_ownership(oname, depth + 1, max_depth)

    async def get_claude_json(self, pdf_path: Path) -> Optional[dict]:
        """Process document with Claude and ensure JSON output"""
        t1 = await self.claude.process_document_strict_json(str(pdf_path), second_attempt=False)
        d1 = self.try_parse_json(t1)
        if d1 is not None:
            return d1
        print("[CLAUDE] First parse failed, attempting stricter prompt...")
        t2 = await self.claude.process_document_strict_json(str(pdf_path), second_attempt=True)
        d2 = self.try_parse_json(t2)
        if d2 is not None:
            return d2
        print("[ERROR] Failed to get valid JSON from Claude")
        return None

    def try_parse_json(self, text: str) -> Optional[dict]:
        """Helper to safely parse JSON"""
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

############################################
# Helper methods for doc retrieval/analysis
############################################
class OwnershipAnalyzer:
    def __init__(self):
        self.fetcher = CompaniesHouseFilingFetcher(CH_API_KEY)
        self.claude = ClaudeProcessor()
        self.output_dir = Path(__file__).parent / "company_documents"
        self.output_dir.mkdir(exist_ok=True)
        
        # BFS tracking
        self.visited: Set[str] = set()
        self.chain_data = {
            "target_company": None,
            "ownership": {}
        }

    def _strip_ltd(self, name: str) -> str:
        """Helper to normalize company names by removing Ltd/Limited"""
        return (
            name.lower()
            .replace("limited", "")
            .replace("ltd", "")
            .strip()
        )

    async def find_current_beneficial_ownership(self, company_number: str) -> dict:
        """
        BFS implementation to trace beneficial ownership through corporate chains.
        """
        # Reset BFS tracking
        self.visited = set()
        self.chain_data = {
            "target_company": None,
            "ownership": {}
        }
        
        # Start BFS trace
        await self.trace_ownership(company_number)
        
        # Format output
        output = {
            "mode": "current_beneficial_ownership",
            "target_company_number": company_number,
            "chain": self.chain_data
        }
        
        # Save results
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        company_dir = self.output_dir / company_number
        company_dir.mkdir(exist_ok=True)
        
        out_json = company_dir / f"bfs_ownership_{now}.json"
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved BFS chain => {out_json}")

        # Generate summary with Gemini
        chain_text = json.dumps(output, indent=2)
        prompt = get_ownership_chain_summary_prompt(chain_text)
        summary = generate_with_retry(prompt)
        if summary:
            print("\n=== Ownership Chain Summary ===\n")
            print(summary)
            sum_file = company_dir / f"bfs_summary_{now}.txt"
            with open(sum_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"\nSaved summary => {sum_file}")

        return output

    async def trace_ownership(self, query: str, depth: int = 0, max_depth: int = 5):
        """
        Recursive BFS helper to trace ownership through corporate chains
        """
        norm = query.strip().lower()
        if norm in self.visited:
            print(f"[SKIP] Already processed: {query}")
            return
        if depth > max_depth:
            print(f"[DEPTH] Reached max depth ({max_depth}) at: {query}")
            return

        print(f"\n[TRACE] Processing {query} at depth {depth}")
        self.visited.add(norm)

        # 1) Identify company_number + official_name
        cnum, cname = None, None
        if query.isdigit():
            prof = self.fetcher.get_company_profile(query)
            if not prof:
                print(f"[ERROR] No profile found: {query}")
                return
            cnum = query
            cname = prof.get("company_name", "UNKNOWN")
        else:
            base_name = self._strip_ltd(query)
            results = self.fetcher.search_company_by_name(base_name, max_results=5)
            if not results:
                print(f"[ERROR] No results found: {query}")
                return
            for r in results:
                if self._strip_ltd(r['title']) == base_name:
                    cnum = r['company_number']
                    cname = r['title']
                    break
            if not cnum:
                print(f"[ERROR] No exact match found: {query}")
                return

        # For the top-level company
        if depth == 0 and not self.chain_data["target_company"]:
            self.chain_data["target_company"] = cname

        # 2) Get filing history
        hist = self.fetcher.get_company_filing_history(cnum)
        if not hist or not hist.get("items"):
            print(f"No filings for {cname} ({cnum}).")
            return

        items = hist["items"]
        items.sort(key=lambda x: x.get('date', ''), reverse=True)

        print("\nChecking documents for ownership information:")
        relevant = []
        for filing in items:
            if is_relevant_for_ownership(filing):
                relevant.append(filing)
                ftype = filing.get('type', '').upper()
                desc = filing.get('description', '').lower()
                date = filing.get('date', 'unknown')
                
                if "PSC" in ftype:
                    print(f"  → {date} | {ftype} (PSC filing)")
                elif any(ftype.startswith(x) for x in ["SH"]):
                    print(f"  → {date} | {ftype} (Share capital)")
                elif ftype.startswith("IN") or "incorporation" in desc:
                    print(f"  → {date} | {ftype} (Incorporation)")
                elif ftype.startswith("AA"):
                    print(f"  → {date} | {ftype} (Annual accounts)")
                elif ftype.startswith(("CS", "AR")):
                    print(f"  → {date} | {ftype} (Confirmation/Annual return)")
                else:
                    print(f"  → {date} | {ftype} ({desc})")

        if not relevant:
            print(f"No relevant ownership docs for {cname} ({cnum}).")
            return

        # Create company directory
        company_dir = self.output_dir / cnum
        company_dir.mkdir(exist_ok=True)

        # Initialize in chain_data
        if cname not in self.chain_data["ownership"]:
            self.chain_data["ownership"][cname] = {
                "company_number": cnum,
                "filings": []
            }

        all_owners = []
        # Process newest relevant document
        for filing in relevant[:1]:  # Only process the newest document
            doc_date = filing.get("date", "unknown-date")
            doc_type = filing.get("type", "unknown")
            doc_title = filing.get("description", "unknown-title").replace("/", "-")
            doc_link = filing.get('links', {}).get('document_metadata')
            
            if not doc_link:
                continue
                
            doc_id = doc_link.split('/')[-1]
            pdf_path = company_dir / f"{doc_title}_{doc_date}.pdf"

            print(f"  [DOC] Processing: {doc_type} ({doc_date})")

            if not self.fetcher.download_document(doc_id, str(pdf_path)):
                print(f"  [SKIP] Failed to download document")
                continue

            owners_data = await self.get_claude_json(pdf_path)
            if owners_data is None:
                print(f"  [SKIP] Failed to parse document")
                continue

            doc_info = {
                "doc_date": doc_date,
                "doc_type": doc_type,
                "owners": owners_data.get("owners", [])
            }
            
            # Store in chain data
            self.chain_data["ownership"][cname]["filings"].append(doc_info)
            all_owners.extend(owners_data.get("owners", []))

        # After processing owners, log what was found
        if all_owners:
            print(f"[FOUND] {cname} ({cnum}) has {len(all_owners)} owners:")
            for o in all_owners:
                owner_type = o.get("type", "unknown")
                owner_name = o.get("name", "unnamed")
                pct = o.get("percentage", "unknown %")
                print(f"  → {owner_name} ({owner_type}, {pct}%)")
        else:
            print(f"[INFO] No ownership data found for {cname}")

        # BFS expansion for corporate owners
        corporate_owners = [o for o in all_owners if o.get("type") == "corporate"]
        if corporate_owners:
            print(f"\n[BFS] Expanding {len(corporate_owners)} corporate owners...")

        for owner in corporate_owners:
            csub = owner.get("details", {}).get("company_number")
            if csub and csub.isdigit():
                await self.trace_ownership(csub, depth + 1, max_depth)
            else:
                oname = owner.get("name", "").strip()
                if oname:
                    await self.trace_ownership(oname, depth + 1, max_depth)

    async def parse_document(self, company_number: str, filing: dict) -> Optional[dict]:
        """
        Download + parse a single relevant filing into JSON. Returns the parsed 'owners' structure or None.
        """
        doc_date = filing.get("date", "unknown-date")
        doc_type = filing.get("type", "unknown")
        doc_title = filing.get("description", "unknown-title").replace("/", "-")  # Replace slashes for safe filenames
        doc_link = filing.get('links', {}).get('document_metadata')
        if not doc_link:
            return None

        # Create company-specific directory
        company_dir = self.output_dir / company_number
        company_dir.mkdir(exist_ok=True)

        doc_id = doc_link.split('/')[-1]
        # Use Companies House title and date in filename
        pdf_path = company_dir / f"{doc_title}_{doc_date}.pdf"

        # Attempt to download
        if not self.fetcher.download_document(doc_id, str(pdf_path)):
            return None

        owners_data = await self.get_claude_json(pdf_path)
        if owners_data is None:
            return None

        return {
            "doc_date": doc_date,
            "doc_type": doc_type,
            "owners": owners_data.get("owners", [])
        }

    async def get_claude_json(self, pdf_path: Path) -> Optional[dict]:
        """Process document with Claude and ensure JSON output"""
        t1 = await self.claude.process_document_strict_json(str(pdf_path), second_attempt=False)
        d1 = self.try_parse_json(t1)
        if d1 is not None:
            return d1
        print("[CLAUDE] First parse failed, attempting stricter prompt...")
        t2 = await self.claude.process_document_strict_json(str(pdf_path), second_attempt=True)
        d2 = self.try_parse_json(t2)
        if d2 is not None:
            return d2
        print("[ERROR] Failed to get valid JSON from Claude")
        return None

    def try_parse_json(self, text: str) -> Optional[dict]:
        """Helper to safely parse JSON"""
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    ####################################################
    # (A) Current Beneficial Ownership: BFS with newest doc only
    ####################################################
    async def find_current_beneficial_ownership(self, company_number: str) -> dict:
        """
        Finds the 'current beneficial ownership' by:
        1) For each company in the chain, parse ONLY its newest relevant doc.
        2) For each corporate owner discovered, recursively do the same.
        Returns a chain structure with each company's single newest doc + owners.
        """
        # We'll keep a visited set so we don't re-parse the same company multiple times
        visited: Set[str] = set()
        chain_data: Dict[str, Any] = {}
        queue = [company_number]

        while queue:
            cnum = queue.pop(0)
            if cnum in visited:
                continue
            visited.add(cnum)

            # Get profile
            prof = self.fetcher.get_company_profile(cnum)
            cname = prof.get("company_name", cnum) if prof else cnum

            # For logging in chain
            chain_data[cnum] = {
                "company_name": cname,
                "filings": []
            }

            # Find newest relevant doc
            doc = self.get_newest_relevant_doc(cnum)
            if not doc:
                # No relevant doc found
                chain_data[cnum]["filings"] = []
                continue

            # Parse newest doc
            doc_info = await self.parse_document(cnum, doc)
            if doc_info:
                chain_data[cnum]["filings"].append(doc_info)
                # Look for corporate owners => BFS them
                for o in doc_info.get("owners", []):
                    if o.get("type") == "corporate":
                        sub_num = o.get("details", {}).get("company_number")
                        if sub_num and sub_num.isdigit():
                            queue.append(sub_num)

        return chain_data

    def get_newest_relevant_doc(self, cnum: str) -> Optional[dict]:
        """
        Return the newest relevant filing for the given company (or None if none).
        """
        hist = self.fetcher.get_company_filing_history(cnum)
        if not hist or not hist.get("items"):
            return None
        items = hist["items"]
        # newest first
        items.sort(key=lambda x: x.get('date', ''), reverse=True)
        for filing in items:
            if is_relevant_for_ownership(filing):
                return filing
        return None

    ####################################################
    # (B) Current Immediate Ownership: single newest doc, no BFS
    ####################################################
    async def find_current_immediate_ownership(self, company_number: str) -> dict:
        """
        Parse only the newest relevant document for the target company,
        return its owners, do NOT follow corporate owners further.
        """
        prof = self.fetcher.get_company_profile(company_number)
        cname = prof.get("company_name", company_number) if prof else company_number

        chain_data = {
            "company_number": company_number,
            "company_name": cname,
            "filings": []
        }

        doc = self.get_newest_relevant_doc(company_number)
        if not doc:
            # No relevant doc
            return chain_data

        doc_info = await self.parse_document(company_number, doc)
        if doc_info:
            chain_data["filings"].append(doc_info)
        return chain_data

    ####################################################
    # (C) Immediate Ownership History: all docs for target only
    ####################################################
    async def find_immediate_ownership_history(self, company_number: str) -> dict:
        """
        Parse ALL relevant documents for the target company, sorted newest->oldest,
        to create a reverse chronological timeline of ownership changes.
        Does NOT expand corporate owners.
        """
        prof = self.fetcher.get_company_profile(company_number)
        cname = prof.get("company_name", company_number) if prof else company_number

        chain_data = {
            "company_number": company_number,
            "company_name": cname,
            "filings": []
        }

        hist = self.fetcher.get_company_filing_history(company_number)
        if not hist or not hist.get("items"):
            return chain_data

        items = hist["items"]
        # Sort newest first (reverse chronological)
        items.sort(key=lambda x: x.get('date', ''), reverse=True)

        for filing in items:
            if is_relevant_for_ownership(filing):
                doc_info = await self.parse_document(company_number, filing)
                if doc_info:
                    chain_data["filings"].append(doc_info)

        return chain_data

    def format_ownership_timeline(self, chain_data: dict) -> str:
        """
        Format ownership data into a clear chronological timeline.
        """
        timeline = []
        
        for filing in chain_data.get("filings", []):
            try:
                # Convert date string to datetime for better formatting
                date_obj = datetime.strptime(filing["doc_date"], "%Y-%m-%d")
                date_str = date_obj.strftime("%-d %B %Y")  # e.g., "22 November 2024"
            except:
                date_str = filing["doc_date"]
            
            # Format each owner's information
            for owner in filing.get("owners", []):
                owner_info = []
                
                # Name and type
                name = owner.get("name", "Unknown")
                
                # Percentage
                percentage = owner.get("percentage")
                if percentage is not None:
                    owner_info.append(f"{percentage}% ownership")
                
                # Shares info if available
                shares = owner.get("shares")
                if shares:
                    owner_info.append(f"shares: {shares}")
                
                # Nature of control
                control = owner.get("nature_of_control", [])
                if control:
                    owner_info.append(f"control: {', '.join(control)}")
                
                # Additional details
                details = owner.get("details", {})
                if details.get("company_number"):
                    owner_info.append(f"company number: {details['company_number']}")
                if details.get("nationality"):
                    owner_info.append(f"nationality: {details['nationality']}")
                
                # Combine all info
                info_str = f"{name} " + " | ".join(owner_info)
                timeline.append(f"-{date_str}: {info_str}")
        
        return "\n\n".join(timeline)


#######################################
# 4) Main => pick mode => run
#######################################
async def main():
    company_number_or_name = input("Enter a company name or number: ").strip()
    
    # Search/validation logic
    fetcher = CompaniesHouseFilingFetcher(CH_API_KEY)
    if not company_number_or_name.isdigit():
        results = fetcher.search_company_by_name(company_number_or_name, max_results=5)
        if not results:
            print(f"No companies found matching name: {company_number_or_name}")
            return
            
        # Check for exact name match first
        exact_matches = [company for company in results 
                        if company['title'].lower() == company_number_or_name.lower()]
        
        if len(exact_matches) == 1:
            company = exact_matches[0]
            company_number = company['company_number']
            company_name = company['title']
            print(f"\nFound: {company_name} ({company_number})")
        elif len(exact_matches) > 1:
            print("\nMultiple companies found with exact name:")
            for idx, company in enumerate(exact_matches, 1):
                print(f"{idx}. {company['title']} ({company['company_number']})")
            choice = input(f"\nEnter number (1-{len(exact_matches)}): ")
            try:
                company = exact_matches[int(choice) - 1]
                company_number = company['company_number']
                company_name = company['title']
            except (ValueError, IndexError):
                print("Invalid selection")
                return
        else:
            print("\nFound companies:")
            for idx, company in enumerate(results, 1):
                print(f"{idx}. {company['title']} ({company['company_number']})")
            choice = input(f"\nEnter number (1-{len(results)}): ")
            try:
                company = results[int(choice) - 1]
                company_number = company['company_number']
                company_name = company['title']
            except (ValueError, IndexError):
                print("Invalid selection")
                return
    else:
        company_number = company_number_or_name
        prof = fetcher.get_company_profile(company_number)
        if not prof:
            print(f"Company {company_number} not found")
            return
        company_name = prof.get("company_name")

    print("\n--- Choose Mode ---")
    print("1) Current Beneficial Ownership (follows corporate owners via BFS; newest doc for each)")
    print("2) Current Immediate Ownership (target only; single newest doc, no BFS)")
    print("3) Immediate Ownership History (target only; all docs from newest to oldest)")
    mode = input("Enter 1, 2, or 3: ").strip()

    if mode == "1":
        print("\nGathering current beneficial ownership via BFS of newest docs...")
        tracer = OwnershipTracer()
        await tracer.trace_ownership(company_number, depth=0, max_depth=5)
        
        # Save BFS chain
        chain = tracer.chain_data
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        company_dir = tracer.output_dir / company_number
        company_dir.mkdir(exist_ok=True)
        
        out_json = company_dir / f"bfs_ownership_{now}.json"
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(chain, f, indent=2)
        print(f"\nFull BFS chain saved => {out_json}")

        # Summarize with Gemini
        chain_text = json.dumps(chain, indent=2)
        prompt = get_ownership_chain_summary_prompt(chain_text)
        summary = generate_with_retry(prompt)
        if summary:
            print("\n=== Final Ownership Chain Summary ===\n")
            print(summary)
            sum_file = company_dir / f"bfs_summary_{now}.txt"
            with open(sum_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"\nSaved summary => {sum_file}")
        
    elif mode == "2":
        analyzer = OwnershipAnalyzer()
        await analyzer.find_current_immediate_ownership(company_number)
    
    elif mode == "3":
        analyzer = OwnershipAnalyzer()
        await analyzer.find_immediate_ownership_history(company_number)
    
    else:
        print("Invalid mode selected")
        return

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())