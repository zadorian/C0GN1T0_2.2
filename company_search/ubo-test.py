import os
import sys
import json
import time
import base64
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set, Optional, Tuple
from collections import deque

from dotenv import load_dotenv

# "ch_ownership" should contain:
#   CH_API_KEY, GEMINI_API_KEY
#   CompaniesHouseFilingFetcher, ClaudeProcessor
from ch_ownership import (TF?!
                          
    CH_API_KEY,
    GEMINI_API_KEY,
    CompaniesHouseFilingFetcher,
    ClaudeProcessor
)

# We'll use your existing Gemini function and prompt
from AI_models.gemini_flash_1_5 import generate_with_retry
from prompts import get_ownership_chain_summary_prompt

load_dotenv()

############################################
# 1) is_relevant_for_ownership
############################################
def is_relevant_for_ownership(filing_item: dict) -> bool:
    ftype = filing_item.get('type', '').upper()
    desc = filing_item.get('description', '').lower()

    ownership_docs = {
        'IN01',
        'PSC01','PSC02','PSC03','PSC04','PSC05','PSC06','PSC07','PSC08','PSC09',
        'SH01','SH02','SH03','SH04','SH05','SH06','SH07','SH08','SH09',
        'CS01','AR01',
        'OSIN01','OSAP01','OSCH03','OSAP03','OSCH05','OSAP05','OSCH07',
        'SEF01','SEF02','SEF03','SEF04','SEF05','SEF06','SEF07','SEF08','SEF09',
        'SEF10','SEF11','SEF12','SEF13','SEF14','SEF15','SEF16','SEF17','SEF18',
        'SEF19','SEF20','SECH01','SECH02','SECH03','SECH04','SESH01','SESH02',
        'SESH03','SESH04',
    }
    if ftype in ownership_docs:
        return True

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

############################################
# 2) Patch ClaudeProcessor to enforce JSON-only
############################################
def patch_claude_processor():
    async def process_document_strict_json(self, file_path: str, second_attempt: bool=False) -> str:
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

############################################
# 3) Extend fetcher with get_company_profile if missing
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

############################################
# 4) Document parser
############################################
async def parse_filing_document(
    fetcher: CompaniesHouseFilingFetcher,
    claude: ClaudeProcessor,
    cnum: str,
    filing: dict,
    output_dir: Path
) -> Optional[dict]:
    doc_date = filing.get("date","unknown-date")
    doc_type = filing.get("type","unknown")
    desc = filing.get("description","no-description").replace("/", "-")
    doc_link = filing.get('links',{}).get('document_metadata')
    if not doc_link:
        return None

    doc_id = doc_link.split('/')[-1]
    pdf_path = output_dir / f"{cnum}_{doc_id}.pdf"

    if not fetcher.download_document(doc_id, str(pdf_path)):
        return None

    owners_json = await get_claude_json(claude, pdf_path)
    if owners_json is None:
        return None

    return {
        "doc_date": doc_date,
        "doc_type": doc_type,
        "owners": owners_json.get("owners", [])
    }

async def get_claude_json(claude: ClaudeProcessor, pdf_path: Path) -> Optional[dict]:
    t1 = await claude.process_document_strict_json(str(pdf_path), second_attempt=False)
    d1 = try_parse_json(t1)
    if d1 is not None:
        return d1

    print("[CLAUDE] First parse failed, attempting stricter prompt...")
    t2 = await claude.process_document_strict_json(str(pdf_path), second_attempt=True)
    d2 = try_parse_json(t2)
    if d2 is not None:
        return d2

    print("[ERROR] Failed to get valid JSON from Claude")
    return None

def try_parse_json(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

############################################
# 5) Listing all docs if no prefix
############################################
def list_all_documents(fetcher: CompaniesHouseFilingFetcher, query: str) -> None:
    cnum, cname = resolve_company_interactive(fetcher, query)
    if not cnum:
        return
    print(f"\nListing all filings for {cname} ({cnum}):\n")
    hist = fetcher.get_company_filing_history(cnum)
    if not hist or not hist.get("items"):
        print("No filings found.")
        return

    items = hist["items"]
    items.sort(key=lambda x: x.get('date',''), reverse=True)
    for idx, f in enumerate(items,1):
        date = f.get("date","unknown-date")
        ftype = f.get("type","??")
        desc = f.get("description","no description")
        print(f"{idx:3d}. [{date}] {ftype} - {desc}")

############################################
# 6) Prompt-based company resolution
############################################
def resolve_company_interactive(fetcher: CompaniesHouseFilingFetcher, query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    1) If digits, look up exact cnum
    2) Else, do name-based search, ignoring 'ltd'
    3) If multiple possible matches found, user picks
    4) If an exact ignoring-ltd match is found, we pick it automatically only if it's the *only* exact match.
       Otherwise we show the user a list to pick from.
    """
    if query.isdigit():
        prof = fetcher.get_company_profile(query)
        if prof:
            return query, prof.get("company_name","UNKNOWN")
        else:
            print(f"[ERROR] No profile found for {query}")
            return None, None

    # else search by name
    base_name = query.lower().replace("limited","").replace("ltd","").strip()
    results = fetcher.search_company_by_name(base_name, max_results=10)
    if not results:
        print(f"[ERROR] No results for {query}")
        return None, None

    # gather exact ignoring-ltd matches
    exact_matches = [
        r for r in results 
        if r["title"].lower().replace("limited","").replace("ltd","").strip() == base_name
    ]
    if len(exact_matches) == 1:
        # single exact match, use it
        pick = exact_matches[0]
        return pick["company_number"], pick["title"]
    elif len(exact_matches) > 1:
        # multiple exact matches -> user picks
        print(f"\nMultiple exact matches for '{query}':")
        for i, r in enumerate(exact_matches,1):
            print(f"{i}. {r['title']} ({r['company_number']})")
        c = input(f"\nPick a number (1..{len(exact_matches)}) or 'q' to cancel: ").strip().lower()
        if c == 'q':
            return None, None
        try:
            ci = int(c)-1
            if 0 <= ci < len(exact_matches):
                return (exact_matches[ci]["company_number"], exact_matches[ci]["title"])
            else:
                print("Invalid selection.")
                return None, None
        except ValueError:
            print("Invalid selection.")
            return None, None
    else:
        # no exact matches -> we show all partial results
        print("\nPossible matches:")
        for i, r in enumerate(results,1):
            print(f"{i}. {r['title']} ({r['company_number']})")
        c = input(f"\nPick a number (1..{len(results)}) or 'q' to cancel: ").strip().lower()
        if c == 'q':
            return None, None
        try:
            ci = int(c)-1
            if 0 <= ci < len(results):
                return (results[ci]["company_number"], results[ci]["title"])
            else:
                print("Invalid selection.")
                return None, None
        except ValueError:
            print("Invalid selection.")
            return None, None


############################################
# 7) FullAutoBFSTracer => "Full BFS" (all docs)
############################################
class FullAutoBFSTracer:
    def __init__(self, fetcher: CompaniesHouseFilingFetcher, claude: ClaudeProcessor):
        self.fetcher = fetcher
        self.claude = claude
        self.output_dir = Path(__file__).parent / "company_documents"
        self.output_dir.mkdir(exist_ok=True)

        self.visited: Set[str] = set()
        self.chain_data = {
            "target_company": None,
            "ownership": {}
        }

    async def trace_ownership_all_docs(self, query: str, depth: int=0, max_depth: int=5):
        norm = query.strip().lower()
        if norm in self.visited:
            print(f"[SKIP] Already processed: {query}")
            return
        if depth > max_depth:
            print(f"[DEPTH] Reached max depth ({max_depth}) at: {query}")
            return

        cnum, cname = resolve_company_interactive(self.fetcher, query)
        if not cnum:
            return

        print(f"\n[TRACE] (all docs) {cname} ({cnum}), depth={depth}")
        self.visited.add(norm)

        if depth == 0 and not self.chain_data["target_company"]:
            self.chain_data["target_company"] = cname

        hist = self.fetcher.get_company_filing_history(cnum)
        if not hist or not hist.get("items"):
            print(f"No filings for {cname} ({cnum}).")
            return
        items = hist["items"]
        items.sort(key=lambda x: x.get('date',''), reverse=True)
        relevant = [f for f in items if is_relevant_for_ownership(f)]
        if not relevant:
            print(f"No relevant docs for {cname} ({cnum}).")
            return

        if cname not in self.chain_data["ownership"]:
            self.chain_data["ownership"][cname] = {
                "company_number": cnum,
                "filings": []
            }

        all_owners: List[dict] = []

        for filing in relevant:
            doc_info = await parse_filing_document(self.fetcher, self.claude, cnum, filing, self.output_dir)
            if doc_info:
                self.chain_data["ownership"][cname]["filings"].append(doc_info)
                all_owners.extend(doc_info["owners"])

        if all_owners:
            print(f"[FOUND] {cname} has {len(all_owners)} owners total.")
        else:
            print(f"[INFO] No owners found for {cname}.")

        corp_owners = [o for o in all_owners if o.get("type") == "corporate"]
        for co in corp_owners:
            sub_num = co.get("details",{}).get("company_number")
            if sub_num and sub_num.isdigit():
                await self.trace_ownership_all_docs(sub_num, depth+1, max_depth)
            else:
                oname = co.get("name","").strip()
                if oname:
                    await self.trace_ownership_all_docs(oname, depth+1, max_depth)


############################################
# 8) OwnershipAnalyzer => "Newest BFS", "Immediate, "History"
############################################
class OwnershipAnalyzer:
    def __init__(self, fetcher: CompaniesHouseFilingFetcher, claude: ClaudeProcessor):
        self.fetcher = fetcher
        self.claude = claude
        self.output_dir = Path(__file__).parent / "company_documents"
        self.output_dir.mkdir(exist_ok=True)

    def get_relevant_docs_descending(self, cnum: str) -> List[dict]:
        """
        Return all relevant docs for cnum in descending date order.
        """
        hist = self.fetcher.get_company_filing_history(cnum)
        if not hist or not hist.get("items"):
            return []
        items = hist["items"]
        items.sort(key=lambda x: x.get('date',''), reverse=True)
        return [f for f in items if is_relevant_for_ownership(f)]

    async def parse_document(self, cnum: str, filing: dict) -> Optional[dict]:
        return await parse_filing_document(self.fetcher, self.claude, cnum, filing, self.output_dir)

    # (A) newest-only BFS
    async def find_current_beneficial_ownership(self, query: str) -> dict:
        visited: Set[str] = set()
        chain_data: Dict[str, Any] = {}
        queue = [query]

        while queue:
            q = queue.pop(0)
            norm = q.lower().strip()
            if norm in visited:
                continue
            visited.add(norm)

            cnum, cname = resolve_company_interactive(self.fetcher, q)
            if not cnum:
                continue

            if cnum not in chain_data:
                chain_data[cnum] = {
                    "company_name": cname,
                    "filings": []
                }

            docs = self.get_relevant_docs_descending(cnum)
            if not docs:
                continue
            # pick the newest doc
            newest_doc = docs[0]
            doc_info = await self.parse_document(cnum, newest_doc)
            if doc_info:
                chain_data[cnum]["filings"].append(doc_info)
                # BFS expansions
                for o in doc_info["owners"]:
                    if o.get("type") == "corporate":
                        sub_num = o.get("details",{}).get("company_number")
                        if sub_num and sub_num.isdigit():
                            queue.append(sub_num)
                        else:
                            queue.append(o["name"])

        return chain_data

    # (B) immediate current ownership => keep going older if no owners
    async def find_current_immediate_ownership(self, query: str) -> dict:
        """
        We want the "most recent doc that actually has owners."
        We'll parse from newest -> older until we find owners.
        Then we stop. If none have owners, we end up with the last attempt.
        """
        cnum, cname = resolve_company_interactive(self.fetcher, query)
        if not cnum:
            return {}

        chain_data = {
            "company_number": cnum,
            "company_name": cname,
            "filings": []
        }

        docs = self.get_relevant_docs_descending(cnum)
        for filing in docs:
            doc_info = await self.parse_document(cnum, filing)
            if doc_info:
                chain_data["filings"].append(doc_info)
                owners = doc_info.get("owners",[])
                if owners:
                    # As soon as we find owners, we stop
                    return chain_data
        # If we got here, we never found any owners in relevant docs
        return chain_data

    # (C) immediate ownership history => parse all relevant docs for target, newest->oldest
    async def find_immediate_ownership_history(self, query: str) -> dict:
        cnum, cname = resolve_company_interactive(self.fetcher, query)
        if not cnum:
            return {}

        chain_data = {
            "company_number": cnum,
            "company_name": cname,
            "filings": []
        }

        docs = self.get_relevant_docs_descending(cnum)
        for filing in docs:
            doc_info = await self.parse_document(cnum, filing)
            if doc_info:
                chain_data["filings"].append(doc_info)

        return chain_data


############################################
# 9) InteractiveModes => doc! or BFS expansions if needed
############################################
class InteractiveModes:
    def __init__(self, fetcher: CompaniesHouseFilingFetcher, claude: ClaudeProcessor):
        self.fetcher = fetcher
        self.claude = claude
        self.output_dir = Path(__file__).parent / "company_documents"
        self.output_dir.mkdir(exist_ok=True)
        self.chain_data = {
            "target_company": None,
            "ownership": {}
        }

    async def interactive_target_only(self, query: str):
        cnum, cname = resolve_company_interactive(self.fetcher, query)
        if not cnum:
            return
        self.chain_data["target_company"] = cname
        self.chain_data["ownership"][cname] = {
            "company_number": cnum,
            "filings": []
        }

        doc_infos = await self.pick_docs_for_company(cnum, cname)
        self.chain_data["ownership"][cname]["filings"].extend(doc_infos)

    async def interactive_bfs(self, query: str):
        queue = deque([query])
        visited = set()

        while queue:
            cur = queue.popleft()
            norm = cur.lower().strip()
            if norm in visited:
                continue
            visited.add(norm)

            cnum, cname = resolve_company_interactive(self.fetcher, cur)
            if not cnum:
                continue

            if not self.chain_data["target_company"]:
                self.chain_data["target_company"] = cname

            if cname not in self.chain_data["ownership"]:
                self.chain_data["ownership"][cname] = {
                    "company_number": cnum,
                    "filings": []
                }

            print(f"\n=== Now examining {cname} ({cnum}) ===")
            doc_infos = await self.pick_docs_for_company(cnum, cname)
            self.chain_data["ownership"][cname]["filings"].extend(doc_infos)

            all_owners = []
            for info in doc_infos:
                all_owners.extend(info["owners"])
            corp_owners = [o for o in all_owners if o.get("type") == "corporate"]

            if corp_owners:
                print(f"\nCorporate owners discovered for {cname}:")
                for idx, co in enumerate(corp_owners,1):
                    oname = co.get("name","???").strip()
                    sub_num = co.get("details",{}).get("company_number")
                    print(f"{idx:2d}. {oname} (Company # {sub_num})")

                while True:
                    expand_choice = input("\nEnter corporate owner # to BFS expand, or 'q' to skip: ").strip().lower()
                    if expand_choice == 'q':
                        break
                    try:
                        cidx = int(expand_choice)-1
                        if 0 <= cidx < len(corp_owners):
                            sub_co = corp_owners[cidx]
                            sub_num = sub_co["details"].get("company_number")
                            if sub_num and sub_num.isdigit():
                                queue.append(sub_num)
                            else:
                                queue.append(sub_co["name"])
                            print("BFS expansion queued.")
                        else:
                            print("Invalid index.")
                    except ValueError:
                        print("Please enter a valid number or 'q'.")

    async def pick_docs_for_company(self, cnum: str, cname: str) -> List[dict]:
        doc_infos = []
        hist = self.fetcher.get_company_filing_history(cnum)
        if not hist or not hist.get("items"):
            print(f"No filings for {cname} ({cnum}).")
            return doc_infos

        items = hist["items"]
        items.sort(key=lambda x: x.get('date',''), reverse=True)
        relevant = [f for f in items if is_relevant_for_ownership(f)]
        if not relevant:
            print(f"No relevant docs for {cname} ({cnum}).")
            return doc_infos

        print(f"\nRelevant documents for {cname} ({cnum}):")
        for idx, f in enumerate(relevant,1):
            d = f.get("date","???")
            t = f.get("type","???")
            desc = f.get("description","").lower()
            print(f"{idx:3d}. {d} | {t} | {desc}")

        while True:
            choice = input("\nEnter doc number to parse or 'q' to finish: ").strip().lower()
            if choice == 'q':
                break
            try:
                pick_idx = int(choice)-1
                if 0 <= pick_idx < len(relevant):
                    doc_info = await parse_filing_document(self.fetcher, self.claude, cnum, relevant[pick_idx], self.output_dir)
                    if doc_info:
                        doc_infos.append(doc_info)
                        owners = doc_info.get("owners",[])
                        if owners:
                            print("Owners found in doc:")
                            for o in owners:
                                print(f"  - {o.get('name')} ({o.get('type')}, {o.get('percentage','?')}%)")
                        else:
                            print("No owners in this document.")
                else:
                    print("Invalid doc number.")
            except ValueError:
                print("Please enter a valid number.")
        return doc_infos

############################################
# 10) Main => parse prefix
############################################
async def main():
    add_profile_method_if_missing()
    patch_claude_processor()

    line = input("Enter a command: ").strip()
    if not line:
        print("No input; exiting.")
        return

    # same prefix logic as before, but with improved "immediate current ownership"
    prefix = None
    target = line
    if line.startswith('!%'):
        prefix = '!%'
        target = line[2:].strip()
    elif line.startswith('%!'):
        prefix = '%!'
        target = line[2:].strip()
    elif line.startswith('<-%!'):
        prefix = '<-%!'
        target = line[4:].strip()
    elif line.startswith('doc!'):
        prefix = 'doc!'
        target = line[4:].strip()

    fetcher = CompaniesHouseFilingFetcher(CH_API_KEY)
    claude = ClaudeProcessor()
    analyzer = OwnershipAnalyzer(fetcher, claude)
    interactive = InteractiveModes(fetcher, claude)
    auto_bfs_tracer = FullAutoBFSTracer(fetcher, claude)

    if prefix is None:
        # no prefix => just list docs
        list_all_documents(fetcher, target)
        return

    elif prefix == '!%':
        # immediate current ownership => parse from newest->older until owners
        print(f"\nImmediate current ownership => {target}")
        chain_data = await analyzer.find_current_immediate_ownership(target)
        chain_text = json.dumps(chain_data, indent=2)
        prompt = get_ownership_chain_summary_prompt(chain_text)
        summary = generate_with_retry(prompt)
        if summary:
            print("\n=== Immediate Ownership Summary ===\n")
            print(summary)

    elif prefix == '%!':
        # newest-only BFS => current UBO check
        print(f"\nNewest-only BFS => {target}")
        chain_data = await analyzer.find_current_beneficial_ownership(target)
        chain_text = json.dumps(chain_data, indent=2)
        prompt = get_ownership_chain_summary_prompt(chain_text)
        summary = generate_with_retry(prompt)
        if summary:
            print("\n=== Current UBO Summary (Newest BFS) ===\n")
            print(summary)

    elif prefix == '<-%!':
        # ownership history => all relevant docs, no BFS
        print(f"\nOwnership history => {target}")
        chain_data = await analyzer.find_immediate_ownership_history(target)
        chain_text = json.dumps(chain_data, indent=2)
        prompt = get_ownership_chain_summary_prompt(chain_text)
        summary = generate_with_retry(prompt)
        if summary:
            print("\n=== Ownership History Summary ===\n")
            print(summary)

    elif prefix == 'doc!':
        # Interactive doc retrieval => target only
        print(f"\nInteractive doc retrieval => {target}")
        await interactive.interactive_target_only(target)
        chain_text = json.dumps(interactive.chain_data, indent=2)
        prompt = get_ownership_chain_summary_prompt(chain_text)
        summary = generate_with_retry(prompt)
        if summary:
            print("\n=== Interactive Doc Retrieval Summary ===\n")
            print(summary)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())