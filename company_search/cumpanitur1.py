#!/usr/bin/env python3
"""
hybrid_company_api.py

A single Python file that merges both Companies House and OpenCorporates-based logic,
prioritizing Companies House (CH) but automatically falling back to OpenCorporates (OC)
whenever CH hits a rate limit/time-out.

The user-provided code from 'enhanced_ch_api.py' is adapted to 'EnhancedCompaniesHouseAPI'.
The user-provided code for OpenCorporates is adapted to 'EnhancedOpenCorporatesAPI'.

Then we define a 'HybridCompanyAPI' that tries CH first, and if it fails or is timed out,
falls back to OpenCorporates for a certain period.

For demonstration, we have a minimal "analyze_company_network" method in HybridCompanyAPI
that replicates the style of your examples (search by name, get details, search by director,
search by address, brand-based search, etc.), but chooses CH or OC under the hood.

You can adapt or expand the final BFS logic to match your needs.
"""

import os
import sys
import time
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass
from pathlib import Path

# Suppose we want generative AI calls for brand extraction, etc.
import google.generativeai as genai
from dotenv import load_dotenv

# This is from your code references
# We define the environment keys
load_dotenv()
CH_API_KEY = os.getenv("CH_API_KEY")
OC_API_KEY = os.getenv("OPENCORPORATES_API_KEY", "")  # if you have one
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# If you want brand extractions or final relationship analysis with Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-pro")


############################################
# 1) Data classes, utility
############################################
@dataclass
class CompanyInfo:
    name: str
    number: str
    address: str
    directors: List[str]
    incorporation_date: Optional[str] = None
    status: Optional[str] = None
    company_type: Optional[str] = None
    source: str = "CH"  # "CH" or "OC"
    # raw_data: optional, if you want to store it


def save_to_json(data, filename: str, company_name: str) -> str:
    """Save to JSON in a structured directory."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(f"company_data/{company_name.replace(' ','_')}_{ts}")
    base_dir.mkdir(parents=True, exist_ok=True)

    filepath = base_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return str(filepath)


############################################
# 2) EnhancedOpenCorporatesAPI (fallback)
############################################
class EnhancedOpenCorporatesAPI:
    """
    Minimal version of your "enhanced" OpenCorporates logic that can:
     - search_companies (by name)
     - get_company_details (by number & jurisdiction)
     - search_by_director
     - etc.

    We'll keep it short, focusing only on crucial methods.
    We'll just "pretend" there's no rate limit or it's higher,
    to be used as fallback.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.opencorporates.com/v0.4"
        # If you have authentication approach for OpenCorporates, implement here

    def search_companies(self, name: str, max_results: int = 20) -> List[Dict]:
        """
        Stub or partial: you would do something like:
        GET /companies/search?q=NAME, parse results
        but let's just return a dummy data structure or
        a minimal actual call if you have real code.
        For example:
        """
        # We'll just simulate some partial logic:
        print(f"[OC] Searching for companies: '{name}' (max={max_results}) - stub.")
        # Return some dummy structure or a real call
        # ...
        return []

    def get_company_details(self, company_number: str, jurisdiction: str="gb") -> Optional[CompanyInfo]:
        """
        Like your 'EnhancedOpenCorporatesAPI.get_company_details'
        Return a minimal CompanyInfo or None
        """
        print(f"[OC] Getting details for {company_number} / {jurisdiction} - stub.")
        # ...
        # Example minimal:
        # simulate a result:
        return CompanyInfo(
            name=f"OC Fake Co {company_number}",
            number=company_number,
            address="123 Fake Street, OpenCorps City",
            directors=["Fake Director A","Fake Director B"],
            source="OC"
        )

    def search_by_director(self, director_name: str, max_results: int=20) -> List[CompanyInfo]:
        print(f"[OC] Searching companies by director ~ {director_name}")
        return []

    def search_by_address(self, address: str, max_results: int=20) -> List[CompanyInfo]:
        print(f"[OC] Searching companies by address ~ {address}")
        return []


############################################
# 3) EnhancedCompaniesHouseAPI (primary)
############################################
import requests
class EnhancedCompaniesHouseAPI:
    """
    A simplified CH logic that we can call. We add rate-limit handling, and if we get 429,
    we'll raise an exception or handle it so Hybrid can fallback to OC.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.company-information.service.gov.uk"
        self.session = requests.Session()
        auth_b64 = base64.b64encode(f"{api_key}:".encode()).decode()
        self.session.headers.update({"Authorization": f"Basic {auth_b64}"})

        self.min_interval = 1.0
        self.last_request_time = 0.0

    def _rate_limit_wait(self):
        """Ensure at least min_interval seconds between calls."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            if wait_time >= 0.2:
                print(f"[CH] Rate-limiting wait {wait_time:.1f}s")
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def search_companies(self, name: str, max_results: int = 20) -> List[Dict]:
        """Search companies by name in CH. Potentially raises an exception if 429 or error."""
        self._rate_limit_wait()
        # Build the URL
        url = f"{self.base_url}/search/companies?q={name}&items_per_page={max_results}"
        resp = self.session.get(url)
        if resp.status_code == 429:
            raise Exception("[CH] 429 Rate Limit")
        if resp.status_code != 200:
            print(f"[CH] Search failed with status {resp.status_code}")
            return []
        data = resp.json()
        items = data.get("items", [])
        # Convert to your standard structure
        results = []
        for it in items:
            results.append({
                "title": it.get("title",""),
                "company_number": it.get("company_number",""),
                "company_status": it.get("company_status","")
            })
        return results

    def get_company_profile(self, company_number: str) -> Optional[dict]:
        """Get profile. Might raise on 429."""
        self._rate_limit_wait()
        url = f"{self.base_url}/company/{company_number}"
        resp = self.session.get(url)
        if resp.status_code == 429:
            raise Exception("[CH] 429 Rate Limit")
        if resp.status_code == 200:
            return resp.json()
        return None

    def get_company_details(self, company_number: str) -> Optional[CompanyInfo]:
        """
        Returns a minimal CompanyInfo from CH. If 429, raise exception.
        Officers fetch could also be done. We'll keep it short for demonstration.
        """
        profile = self.get_company_profile(company_number)
        if not profile:
            return None

        name = profile.get("company_name","Unknown")
        inc_date = profile.get("date_of_creation")
        status = profile.get("company_status")
        ctype = profile.get("type","")
        # We won't do officers fully for brevity. Or do a partial:
        # ...
        address = profile.get("registered_office_address", {})
        address_full = ", ".join(str(x) for x in address.values() if x)

        # Minimal approach
        return CompanyInfo(
            name=name,
            number=company_number,
            address=address_full,
            directors=[],
            incorporation_date=inc_date,
            status=status,
            company_type=ctype,
            source="CH"
        )


############################################
# 4) The Hybrid approach
############################################
class HybridCompanyAPI:
    """
    A single class that holds both the EnhancedCompaniesHouseAPI (CH) and
    EnhancedOpenCorporatesAPI (OC). By default, it tries CH. If CH hits 429 or times out,
    we set a 'ch_unavailable_until' to some future time, and fallback to OC until that time passes.
    Then we try CH again on next calls.
    """

    def __init__(self):
        # Set up the two clients
        self.ch_api = EnhancedCompaniesHouseAPI(CH_API_KEY)
        self.oc_api = EnhancedOpenCorporatesAPI(OC_API_KEY)

        # If we do get a CH 429 or big failure, we set an unavailable window:
        self.ch_unavailable_until = None  # type: Optional[datetime]

    def _can_use_ch(self) -> bool:
        """Return True if CH is available (not in a forced cool-down)."""
        if not self.ch_unavailable_until:
            return True
        now = datetime.now()
        return now >= self.ch_unavailable_until

    def _fail_ch(self):
        """Mark CH as unavailable for some duration, say 60s."""
        cooldown_seconds = 60
        self.ch_unavailable_until = datetime.now() + timedelta(seconds=cooldown_seconds)
        print(f"[HYBRID] Companies House unavailable until {self.ch_unavailable_until}")

    #-------------- Searching by name -------------
    def search_companies(self, name: str, max_results: int=20) -> List[CompanyInfo]:
        """
        1) If CH is available, try CH. If we get 429 or error, fallback to OC (and mark CH as unavailable).
        2) If CH is not available, do OC.
        Return a list of CompanyInfo.
        """
        # Attempt CH if allowed
        if self._can_use_ch():
            try:
                print("[HYBRID] Using CH for search_companies")
                ch_results = self.ch_api.search_companies(name, max_results=max_results)
                out = []
                for r in ch_results:
                    # Convert to CompanyInfo
                    cinfo = self.ch_api.get_company_details(r["company_number"])
                    if cinfo:
                        out.append(cinfo)
                return out
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate limit" in msg:
                    print("[HYBRID] CH rate limit -> fallback to OC")
                    self._fail_ch()
                else:
                    print(f"[HYBRID] CH error => {e}, fallback to OC")

        # If we get here, do OC
        print("[HYBRID] Using OC for search_companies")
        oc_results = self.oc_api.search_companies(name, max_results=max_results)
        # Convert to CompanyInfo if you want a consistent approach:
        # We'll just pretend each has .number, .name, etc., or call get_company_details
        final_list = []
        for oc in oc_results:
            # in your code, you might have a jurisdiction or something
            cinfo = self.oc_api.get_company_details(oc.get("company_number",""), "gb")
            if cinfo:
                final_list.append(cinfo)
        return final_list

    #-------------- get company details -------------
    def get_company_details(self, company_number: str) -> Optional[CompanyInfo]:
        """Same logic: prefer CH, fallback to OC if rate-limited or error."""
        if self._can_use_ch():
            try:
                print("[HYBRID] Using CH for get_company_details")
                return self.ch_api.get_company_details(company_number)
            except Exception as e:
                if "429" in str(e).lower():
                    print("[HYBRID] CH rate limit => fallback to OC")
                    self._fail_ch()
                else:
                    print(f"[HYBRID] CH error => {e}, fallback to OC")

        # fallback
        print("[HYBRID] Using OC for get_company_details")
        # you may need a separate jurisdiction code
        return self.oc_api.get_company_details(company_number, "gb")

    #-------------- search by director -------------
    def search_by_director(self, director_name: str, max_results: int=20) -> List[CompanyInfo]:
        """
        1) There's no official CH 'search by director' (we typically do a name search).
           We'll approximate for CH by search_companies(director_name).
        2) If CH is rate-limited or fails, fallback to OC's search_by_director.
        """
        if self._can_use_ch():
            try:
                print("[HYBRID] Using CH (approx) for search_by_director")
                # We'll just do name search, then filter
                # or do a direct function if you had one.
                # Approx approach:
                ch_companies = self.search_companies(director_name, max_results=max_results)
                # Then filter if the 'director_name' is actually among the cinfo.directors if known
                # But for now, let's just return them as is, or you'd do more logic
                return ch_companies
            except Exception as e:
                if "429" in str(e).lower():
                    print("[HYBRID] CH rate limit => fallback to OC")
                    self._fail_ch()
                else:
                    print(f"[HYBRID] CH error => {e}, fallback to OC")

        # fallback
        print("[HYBRID] Using OC for search_by_director")
        return self.oc_api.search_by_director(director_name, max_results)

    #-------------- search by address -------------
    def search_by_address(self, address: str, max_results: int=20) -> List[CompanyInfo]:
        """
        CH has no direct address search. We can do an approximate approach with name search if you want.
        Or fallback to OC if not feasible.
        """
        if self._can_use_ch():
            try:
                print("[HYBRID] Using CH approximate for search_by_address")
                # For CH, we might do search_companies(address, max_results) as an approximate approach
                approx = self.search_companies(address, max_results)
                # We might filter results whose address contains the text, etc.
                # We'll skip that detail for brevity
                return approx
            except Exception as e:
                if "429" in str(e).lower():
                    print("[HYBRID] CH rate limit => fallback to OC")
                    self._fail_ch()
                else:
                    print(f"[HYBRID] CH error => {e}, fallback to OC")

        # fallback
        print("[HYBRID] Using OC for search_by_address")
        return self.oc_api.search_by_address(address, max_results)

    #-------------- brand-based name search -------------
    def search_by_name(self, name: str, max_results: int=20) -> List[CompanyInfo]:
        """Essentially same as search_companies, but we keep the name separate for clarity."""
        # same logic
        return self.search_companies(name, max_results)

    #-------------- Example BFS or analysis -------------
    def analyze_company_network(self, company_name: str) -> Dict:
        """
        Simple demonstration:
         1) search for the target
         2) pick best match
         3) get details
         4) search by directors
         5) search by address
         6) (optionally brand search)
         7) combine results
        """
        print(f"[HYBRID] Analyzing network for '{company_name}'...")

        # 1) search
        results = self.search_companies(company_name, max_results=10)
        if not results:
            print("No companies found.")
            return {}

        # pick first
        target = results[0]
        target_number = target.number

        # 2) get details
        if not target.directors:
            # maybe we re-get details if it doesn't have directors
            detail = self.get_company_details(target_number)
            if detail:
                target = detail

        print(f"[HYBRID] Target => {target.name} ({target.number}) from {target.source}")
        # 3) director search
        related = []
        for d in target.directors:
            sub_res = self.search_by_director(d)
            for sr in sub_res:
                if sr.number != target.number:
                    related.append(sr)

        # 4) address
        if target.address and target.address != "Not available":
            addr_res = self.search_by_address(target.address)
            for ar in addr_res:
                if ar.number != target.number:
                    related.append(ar)

        # 5) brand
        brand = None
        if GEMINI_API_KEY:
            brand_prompt = f"Extract the brand from '{target.name}'. If none, return 'NONE'."
            print("[HYBRID] Attempting brand extraction via Gemini...")
            try:
                resp = gemini_model.generate_content(brand_prompt)
                brand = resp.text.strip()
                print(f"[HYBRID] brand => {brand}")
                if brand.lower() != "none":
                    brand_results = self.search_companies(brand, max_results=10)
                    for br in brand_results:
                        if br.number != target.number:
                            related.append(br)
            except Exception as e:
                print(f"[HYBRID] brand extraction error => {e}")

        # remove duplicates
        seen_nums = set()
        final_related = []
        for c in related:
            if c.number not in seen_nums:
                seen_nums.add(c.number)
                final_related.append(c)

        # Return a small summary
        out = {
            "target_company": {
                "name": target.name,
                "number": target.number,
                "source": target.source,
                "address": target.address,
                "directors": target.directors
            },
            "related_companies": [
                {
                    "name": x.name,
                    "number": x.number,
                    "source": x.source,
                    "address": x.address,
                    "directors": x.directors
                }
                for x in final_related
            ],
            "brand": brand or ""
        }

        # Save
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"hybrid_analysis_{company_name.replace(' ','_')}_{now}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"[HYBRID] Analysis complete, saved => {fname}")
        return out


############################################
# 5) MAIN
############################################
def main():
    print("=== Hybrid Company API Demo ===")
    company_name = input("Enter company name to analyze: ").strip()
    if not company_name:
        print("No input, exiting.")
        return

    # Create the Hybrid
    hybrid = HybridCompanyAPI()

    # Analyze
    network_result = hybrid.analyze_company_network(company_name)

    print("\nDone.")
    # optionally print summary
    if network_result:
        print(json.dumps(network_result, indent=2))


if __name__ == "__main__":
    main()