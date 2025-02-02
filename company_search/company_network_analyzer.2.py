#!/usr/bin/env python3
"""
company_network_analyzer.py

Demonstration of a single-file "Hybrid" approach that:
1) Tries Companies House (CH) first
2) Falls back to OpenCorporates (OC)
3) Resets usage daily
4) Once we find the exact target company among the top 5 results, we do:
   - brand extraction via Gemini
   - brand-based search (with threshold of 12)
   - address-based search (with threshold of 12)
   - director-based search (with threshold of 20)
   - highlight companies overlapping 2+ attributes with the target
   - show live logs at each step
"""

import os
import sys
import time
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set
from dataclasses import dataclass

import requests

# If brand extraction uses Gemini:
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
CH_API_KEY = os.getenv("CH_API_KEY", "")
OC_API_KEY = os.getenv("OPENCORPORATES_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

################################
# Minimal data structures
################################

@dataclass
class CompanyInfo:
    name: str
    number: str
    address: str
    directors: List[str]
    incorporation_date: Optional[str] = None
    status: Optional[str] = None
    company_type: Optional[str] = None
    source: str = "CH"  # or "OC"

###############################
# STUB or minimal EnhancedCompaniesHouseAPI
###############################
class EnhancedCompaniesHouseAPI:
    """
    Minimal approach for CH usage. 
    Daily usage, rate-limit simulation, etc.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.company-information.service.gov.uk"
        self.session = requests.Session()
        auth_b64 = base64.b64encode(f"{api_key}:".encode()).decode()
        self.session.headers.update({"Authorization": f"Basic {auth_b64}"})
        # daily usage
        self.daily_limit = 600
        self.calls_today = 0
        self.day_marker = datetime.now().strftime("%Y-%m-%d")

    def _check_new_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.day_marker:
            self.calls_today = 0
            self.day_marker = today

    def _make_request(self, url: str):
        self._check_new_day()
        if self.calls_today >= self.daily_limit:
            raise Exception("[CH] daily usage exceeded")

        print(f"[CH] calling {url} (calls_today={self.calls_today}/{self.daily_limit})")
        self.calls_today += 1
        resp = self.session.get(url)
        if resp.status_code == 429:
            raise Exception("[CH] 429 Rate Limit")
        if resp.status_code == 200:
            return resp.json()
        return None

    def search_companies(self, name: str, max_results: int=20) -> List[Dict]:
        """Search for companies by name."""
        name = name.lower()
        url = f"{self.base_url}/search/companies?q={name}&items_per_page={max_results}"
        data = self._make_request(url)
        if not data or "items" not in data:
            return []
        out = []
        for it in data["items"]:
            out.append({
                "company_number": it.get("company_number",""),
                "title": it.get("title","")
            })
        return out

    def get_company_profile(self, number: str) -> Optional[dict]:
        number = number.upper()
        url = f"{self.base_url}/company/{number}"
        return self._make_request(url)

    def get_company_details(self, number: str) -> Optional[CompanyInfo]:
        number = number.upper()
        prof = self.get_company_profile(number)
        if not prof:
            return None
        
        name = prof.get("company_name", "Unknown")
        inc_date = prof.get("date_of_creation")
        status = prof.get("company_status")
        ctype = prof.get("type", "")
        addr = prof.get("registered_office_address", {})
        line = ", ".join(str(x) for x in addr.values() if x)
        # Directors:
        directors = []
        try:
            officers_url = f"{self.base_url}/company/{number}/officers"
            officers_data = self._make_request(officers_url)
            if officers_data and "items" in officers_data:
                for officer in officers_data["items"]:
                    if officer.get("officer_role","") == "director":
                        nm = officer.get("name","")
                        if nm:
                            directors.append(nm)
        except Exception as e:
            print(f"[CH] Warning: Could not fetch directors: {e}")
        
        return CompanyInfo(
            name=name, number=number, address=line, directors=directors,
            incorporation_date=inc_date, status=status, company_type=ctype,
            source="CH"
        )

###############################
# STUB or minimal EnhancedOpenCorporatesAPI
###############################
class EnhancedOpenCorporatesAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.daily_limit = 1000
        self.calls_today = 0
        self.day_marker = datetime.now().strftime("%Y-%m-%d")

    def _check_new_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.day_marker:
            self.calls_today = 0
            self.day_marker = today

    def _maybe_429(self):
        self._check_new_day()
        if self.calls_today >= self.daily_limit:
            raise Exception("[OC] daily usage exceeded")

    def search_companies(self, name: str, max_results: int=20) -> List[Dict]:
        self._maybe_429()
        self.calls_today += 1
        print(f"[OC] Searching '{name}' (calls_today={self.calls_today}/{self.daily_limit})")
        return [
            {"company_number": f"OC-{i}", "title": f"FakeOC Co {i}"}
            for i in range(min(3,max_results))
        ]

    def get_company_details(self, company_number: str, jurisdiction: str="gb") -> Optional[CompanyInfo]:
        self._maybe_429()
        self.calls_today += 1
        print(f"[OC] get_company_details {company_number} (calls_today={self.calls_today}/{self.daily_limit})")
        return CompanyInfo(
            name=f"OC_{company_number}",
            number=company_number,
            address=f"OC Address for {company_number}",
            directors=["OC Dir A", "OC Dir B"],
            source="OC"
        )

###############################
# HYBRID
###############################
class HybridCompanyAPI:
    def __init__(self, ch_key: str, oc_key: str):
        self.ch_api = EnhancedCompaniesHouseAPI(ch_key)
        self.oc_api = EnhancedOpenCorporatesAPI(oc_key)

    def search_companies(self, name: str, max_results: int=20) -> List[CompanyInfo]:
        # Just do CH first, fallback to OC if CH fails
        try:
            raw = self.ch_api.search_companies(name, max_results)
            out = []
            for r in raw:
                cinfo = self.ch_api.get_company_details(r["company_number"])
                if cinfo:
                    out.append(cinfo)
            return out
        except Exception as e:
            print(f"[HYBRID] CH error => {e}, fallback to OC.")
            # fallback to OC
            try:
                raw = self.oc_api.search_companies(name, max_results)
                out = []
                for r in raw:
                    cinfo = self.oc_api.get_company_details(r["company_number"])
                    if cinfo:
                        out.append(cinfo)
                return out
            except Exception as e2:
                print(f"[HYBRID] OC error => {e2}.")
                raise Exception("[HYBRID] Both CH + OC failed")

    def get_company_details(self, number: str) -> CompanyInfo:
        try:
            cinfo = self.ch_api.get_company_details(number)
            if not cinfo:
                raise Exception("[CH] Not found")
            return cinfo
        except Exception as e:
            print(f"[HYBRID] CH error => {e}, fallback to OC.")
            try:
                cinfo = self.oc_api.get_company_details(number)
                if not cinfo:
                    raise Exception("[OC] Not found")
                return cinfo
            except Exception as e2:
                print(f"[HYBRID] OC error => {e2}")
                raise Exception("[HYBRID] Both CH + OC failed")


    ###########################################################
    # BFS approach with new logic
    ###########################################################
    def analyze_company_network(self, company_name: str):
        """
        0) search for top 5 in CH
         - pick the EXACT match as target
        1) brand extraction with Gemini
         - brand search => if <12 => get addresses+directors, else only names
        2) address search => if <12 => get addresses+directors, else only names
        3) director search => if name has comma => also reversed
           if <20 => addresses+directors, else only names
        4) highlight overlap >=2 with target
        5) show logs
        """
        print("\n=== Phase 0: Searching in CH for top 5 ===")
        raw_results = self.ch_api.search_companies(company_name, 5)
        detailed_results = []
        for r in raw_results:
            # r is CompanyInfo
            # We already have addresses, directors from get_company_details => so r is complete
            print(f"  => {r.name} ({r.number}), address={r.address}, directors={len(r.directors)}")
            detailed_results.append(r)

        # find EXACT match
        def _clean(s: str) -> str:
            return s.replace('"','').strip().lower()

        target = None
        for comp in detailed_results:
            if _clean(comp.name) == _clean(company_name):
                target = comp
                break

        if not target:
            print("No EXACT target found among top 5. Exiting.")
            return

        print(f"\n=== EXACT target found: {target.name} ({target.number}) ===")
        print(f"Address: {target.address}")
        print(f"Directors: {', '.join(target.directors)}")

        # 1) Brand extraction
        print("\n=== Phase 1: Brand extraction via Gemini ===")
        brand_prompt = get_brand_analysis_prompt(target.name)
        brand = generate_with_retry(brand_prompt)
        if not brand:
            brand = "None"
        brand_clean = brand.strip().lower()
        print(f"Extracted brand: {brand}")

        # 1b) brand-based search
        brand_companies = []
        if brand_clean != "none" and brand_clean != "":
            print(f"\n=== Phase 1b: Searching brand '{brand}' in CH ===")
            bc_raw = self.search_companies(brand, 20)  # up to 20
            print(f"  => Found {len(bc_raw)} brand-based results.")
            if len(bc_raw) < 12:
                # fetch addresses+directors is already done in search_companies
                for bc in bc_raw:
                    print(f"  => {bc.name} ({bc.number}), address={bc.address}, directors={len(bc.directors)}")
                    brand_companies.append(bc)
            else:
                # only names
                for bc in bc_raw:
                    print(f"  => {bc.name} ({bc.number})  [Directors/Addresses not shown: too many results]")
                    brand_companies.append(CompanyInfo(
                        name=bc.name, number=bc.number, address="", directors=[], source=bc.source
                    ))

        # 2) address-based
        address_companies = []
        addr_clean = target.address.strip()
        if addr_clean:
            print(f"\n=== Phase 2: Searching by same address ===")
            ac_raw = self.search_companies(addr_clean, 20)
            print(f"  => Found {len(ac_raw)} address-based results.")
            if len(ac_raw) < 12:
                for ac in ac_raw:
                    print(f"  => {ac.name} ({ac.number}), address={ac.address}, dirs={len(ac.directors)}")
                    address_companies.append(ac)
            else:
                # only names
                for ac in ac_raw:
                    print(f"  => {ac.name} ({ac.number})  [Directors/Addresses not shown: too many results]")
                    address_companies.append(CompanyInfo(
                        name=ac.name, number=ac.number, address="", directors=[], source=ac.source
                    ))

        # 3) directors
        director_companies = []
        def _director_variations(dnm: str) -> List[str]:
            out = [dnm]
            if "," in dnm:
                # e.g. "Szabo, Domonkos" => also "Domonkos Szabo"
                parts = [p.strip() for p in dnm.split(",")]
                if len(parts) == 2 and parts[0] and parts[1]:
                    out.append(f"{parts[1]} {parts[0]}")
            return out

        print("\n=== Phase 3: Searching by directors ===")
        for dnm in target.directors:
            variations = _director_variations(dnm)
            for var_name in variations:
                # do search
                print(f"  => Searching director name: {var_name}")
                # We'll do up to 20
                dir_results = self.search_companies(var_name, 20)
                count_dir = len(dir_results)
                print(f"     Found {count_dir} companies for {var_name}")
                if count_dir < 20:
                    # we have addresses + directors
                    for dr in dir_results:
                        # skip if it's the target itself
                        if dr.number != target.number:
                            print(f"     => {dr.name} ({dr.number}), address={dr.address}, dirs={len(dr.directors)}")
                            director_companies.append(dr)
                else:
                    # only names
                    for dr in dir_results:
                        if dr.number != target.number:
                            print(f"     => {dr.name} ({dr.number}) [Skipping addresses/dirs, too many results]")
                            director_companies.append(CompanyInfo(
                                name=dr.name, number=dr.number, address="", directors=[], source=dr.source
                            ))

        # 4) Overlap highlighting
        # We want: if a company shares 2+ overlaps with target => "PRIORITY"
        # Overlaps can be: brand? address? directors? 
        # For brand, we check if the brand is in the name or exactly brand == ...
        # The user said "2 or more attributes" => 
        #  We'll consider these possible attributes:
        #   - same address
        #   - each director in common
        #   - brand match => if the brand is in the name
        # We'll define a small function that counts the overlaps

        def count_overlaps(c: CompanyInfo, t: CompanyInfo, brand_keyword: str) -> int:
            overlap_count = 0
            # address
            if c.address.strip().lower() == t.address.strip().lower() and c.address.strip():
                overlap_count += 1
            # directors in common
            set_tdirs = set(d.strip().lower() for d in t.directors)
            set_cdirs = set(d.strip().lower() for d in c.directors)
            dir_intersection = set_tdirs.intersection(set_cdirs)
            if len(dir_intersection) >= 1:
                # each shared director counts as 1 overlap
                overlap_count += len(dir_intersection)
            # brand
            if brand_keyword and brand_keyword != "none":
                # if brand is in c.name
                if brand_keyword.lower() in c.name.lower():
                    overlap_count += 1
            return overlap_count

        # We'll check brand_clean as the brand keyword
        brand_keyword = brand_clean
        # We'll collect them all in one place to highlight
        combined_list = [
            ("Brand-based", bc) for bc in brand_companies
        ] + [
            ("Address-based", ac) for ac in address_companies
        ] + [
            ("Director-based", dc) for dc in director_companies
        ]
        # Deduplicate them in a naive way
        seen = set()
        final_list = []
        for cat, co in combined_list:
            key_ = (cat, co.name, co.number)
            if key_ not in seen:
                seen.add(key_)
                final_list.append((cat, co))

        print("\n=== Phase 4: Overlap Analysis ===")
        for cat, co in final_list:
            ocount = count_overlaps(co, target, brand_keyword)
            is_priority = (ocount >= 2)
            priority_mark = " [PRIORITY]" if is_priority else ""
            print(f"From {cat}: {co.name} ({co.number}) => Overlap = {ocount}{priority_mark}")

        print("\n=== DONE. ===")

#######################
# Prompts + Gemini stubs
#######################
def get_brand_analysis_prompt(company_name: str) -> str:
    return f"Extract a brand name from the company name '{company_name}'. If no brand found, say 'None'."

def generate_with_retry(prompt: str) -> str:
    # This is a stub simulating Gemini calls
    # In your real code, you'd do `genai.generate_text(model, prompt=prompt, ...)`
    # For demonstration, let's just do:
    print(f"[Gemini] Prompt: {prompt}")
    # We'll pretend it yields "MagicBrand"
    if "None" in prompt.lower():
        return "None"
    return "MagicBrand"

#######################
# MAIN CLI
#######################
@click.command()
def main():
    if not CH_API_KEY:
        print("Missing CH_API_KEY. Exiting.")
        sys.exit(1)

    h = HybridCompanyAPI(CH_API_KEY, OC_API_KEY)
    name = input("Enter a company name to analyze: ").strip()
    if not name:
        return
    h.analyze_company_network(name)

if __name__ == "__main__":
    main()