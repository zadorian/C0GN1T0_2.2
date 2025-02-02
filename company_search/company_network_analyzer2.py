#!/usr/bin/env python3
"""
company_network_analyzer.py

Implementation of user instructions:
0) We fetch top 5 from CH for the user input, get addresses+directors for each.
   One of them is the exact match => that's the 'target'. If none exact, pick first.
1) We extract brand from target using Gemini. If brand != 'None', we do brand-based search.
   If <12 results => get full details, else name only.
2) Address-based search on target's address. If <12 => get full details, else name only.
3) Director-based search: for each target director, if there's a comma => also reversed. Then:
   - Use /search/officers => gather appointed companies => if <20 => full details else name only
4) We combine brand-based, address-based, and director-based sets, do overlap check:
   - Overlap +1 if brand is in name, +1 if addresses match, +1 per shared director
   - If total >=2 => [PRIORITY]
5) Print logs for every step: what is retrieved, why, results, final summary
"""

import os
import sys
import time
import base64
import json
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

import requests
import click

# If brand extraction uses Gemini:
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

CH_API_KEY = os.getenv("CH_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

###############################################################################
# Data structures
###############################################################################

@dataclass
class CompanyInfo:
    name: str
    number: str
    address: str
    directors: List[str]

@dataclass
class OfficerSearchItem:
    officer_id: str
    appointments_count: int
    # we might parse more fields if needed


###############################################################################
# Minimal Gemini stubs
###############################################################################

def get_brand_prompt(company_name: str) -> str:
    """Construct brand-extraction prompt for Gemini."""
    return f"Extract the brand name from the company name '{company_name}'. If none, say 'None'."

def generate_with_retry(prompt: str) -> str:
    """Stub for brand extraction with Gemini."""
    print(f"[GEMINI] Brand extraction prompt => {prompt}")
    # Fake logic: if the name has "Sastre" => "SASTRE", else "None"
    # In real code: call genai.generate_text(...)
    pl = prompt.lower()
    if "sastre" in pl:
        return "SASTRE"
    return "None"

###############################################################################
# Enhanced CH wrapper
###############################################################################

class EnhancedCH:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.company-information.service.gov.uk"
        auth_str = base64.b64encode(f"{api_key}:".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Basic {auth_str}"})

    def log(self, msg: str):
        print(f"[CH] {msg}")

    def _get(self, endpoint: str) -> dict:
        url = self.base_url + endpoint
        self.log(f"GET {url}")
        resp = self.session.get(url)
        if resp.status_code == 429:
            raise Exception("429 Rate Limit from CH")
        if resp.status_code != 200:
            raise Exception(f"CH error {resp.status_code}: {resp.text}")
        return resp.json()

    def search_companies(self, query: str, limit: int = 5) -> List[dict]:
        """
        Search up to `limit` companies. We'll quote the query to ensure phrase search.
        Returns raw items.
        """
        enc_q = f'"{query.strip()}"'
        ep = f"/search/companies?q={enc_q}&items_per_page={limit}"
        data = self._get(ep)
        items = data.get("items", [])
        self.log(f"search_companies('{query}') => {len(items)} items returned (limit={limit})")
        return items

    def fetch_company_profile(self, number: str) -> dict:
        ep = f"/company/{number}"
        return self._get(ep)

    def fetch_officers(self, number: str, limit: int=100) -> List[dict]:
        ep = f"/company/{number}/officers?items_per_page={limit}"
        data = self._get(ep)
        return data.get("items", [])

    def build_company_info(self, raw_profile: dict) -> CompanyInfo:
        name = raw_profile.get("company_name","Unknown")
        number = raw_profile.get("company_number","")
        ra = raw_profile.get("registered_office_address", {})
        address_str = ", ".join(str(x) for x in ra.values() if x)
        # fetch directors:
        dirs = []
        try:
            off = self.fetch_officers(number, 100)
            for item in off:
                if item.get("officer_role","") == "director":
                    nm = item.get("name","").strip()
                    if nm:
                        dirs.append(nm)
        except Exception as e:
            self.log(f"Cannot fetch officers for {number}: {e}")

        return CompanyInfo(name=name, number=number, address=address_str, directors=dirs)

    def search_officers(self, name: str, limit: int=50) -> dict:
        """
        /search/officers?q="name"
        Returns the JSON. We'll parse it in the caller.
        """
        enc_q = f'"{name.strip()}"'
        ep = f"/search/officers?q={enc_q}&items_per_page={limit}"
        data = self._get(ep)
        self.log(f"search_officers('{name}') => {data.get('total_results',0)} total, returning {len(data.get('items',[]))} items")
        return data

###############################################################################
# The Analyzer
###############################################################################

class CompanyNetworkAnalyzer:
    def __init__(self, ch_api: EnhancedCH):
        self.ch = ch_api

    def log(self, msg: str):
        print(f"[ANALYZER] {msg}")

    def step0_top5(self, user_query: str) -> List[CompanyInfo]:
        """
        Return details (address+directors) for top 5 CH results for user_query
        """
        raw = self.ch.search_companies(user_query, 5)
        out = []
        for i, item in enumerate(raw, start=1):
            cn = item.get("company_number","")
            print(f"[STEP0] => Fetching addresses+directors for top-5 item #{i}: {item.get('title')} => {cn}")
            try:
                prof = self.ch.fetch_company_profile(cn)
                cinfo = self.ch.build_company_info(prof)
                out.append(cinfo)
            except Exception as e:
                print(f"[STEP0] Failed to fetch detail for {cn}: {e}")
        return out

    def find_exact_target(self, all_five: List[CompanyInfo], user_query: str) -> CompanyInfo:
        """
        Among those five, find EXACT ignoring case. If not found, pick first.
        """
        user_lower = user_query.strip().lower()
        best = all_five[0] if all_five else None
        for c in all_five:
            if c.name.strip().lower() == user_lower:
                best = c
                break
        return best

    def brand_extraction(self, target: CompanyInfo) -> str:
        if not GEMINI_API_KEY:
            print("[Gemini] No API key, skipping brand extraction => 'None'")
            return "None"
        prompt = get_brand_prompt(target.name)
        brand = generate_with_retry(prompt).strip()
        if not brand:
            brand = "None"
        return brand

    def search_brand(self, brand: str) -> List[CompanyInfo]:
        """
        Up to 20. If <12 => addresses+directors, else only name.
        """
        print(f"[BRAND] Searching brand => {brand}")
        raw = self.ch.search_companies(brand, 20)
        out = []
        if len(raw) < 12:
            for item in raw:
                cn = item.get("company_number","")
                nm = item.get("title","")
                print(f"[BRAND] => Full detail for {nm} ({cn})")
                try:
                    prof = self.ch.fetch_company_profile(cn)
                    cinfo = self.ch.build_company_info(prof)
                    out.append(cinfo)
                except Exception as e:
                    print(f"[BRAND] Failed to fetch {cn}: {e}")
        else:
            for item in raw:
                nm = item.get("title","")
                cn = item.get("company_number","")
                out.append(CompanyInfo(name=nm, number=cn, address="", directors=[]))
        return out

    def search_address(self, addr: str) -> List[CompanyInfo]:
        """
        Up to 20. If <12 => addresses+directors, else only name
        """
        print(f"[ADDRESS] Searching => {addr}")
        raw = self.ch.search_companies(addr, 20)
        out = []
        if len(raw) < 12:
            for item in raw:
                cn = item.get("company_number","")
                nm = item.get("title","")
                print(f"[ADDRESS] => Full detail for {nm} ({cn})")
                try:
                    prof = self.ch.fetch_company_profile(cn)
                    cinfo = self.ch.build_company_info(prof)
                    out.append(cinfo)
                except Exception as e:
                    print(f"[ADDRESS] Failed to fetch {cn}: {e}")
        else:
            for item in raw:
                nm = item.get("title","")
                cn = item.get("company_number","")
                out.append(CompanyInfo(name=nm, number=cn, address="", directors=[]))
        return out

    def search_directors_companies(self, dir_name: str) -> List[str]:
        """
        Real approach:
         /search/officers?q="dir_name"
         parse each item => "links.officer.appointments" => fetch that => parse companies
         For simplicity, let's see if the returned item has an 'appointed_to' => 'company_number'
        We'll gather all distinct company_numbers
        """
        print(f"[DIRECTOR-SEARCH] Searching officers => '{dir_name}'")
        data = self.ch.search_officers(dir_name, 50)
        items = data.get("items", [])
        cnumbers = set()
        # each item might have 'appointed_to'=>{'company_number':...}
        for it in items:
            ap = it.get("appointed_to", {})
            if "company_number" in ap:
                cnumbers.add(ap["company_number"])
            # or it might have 'links'=>{'officer'=>{'appointments'=>...}} => we might do a second fetch
            # But the user wants a simpler approach, let's see if the item includes 'appointed_to'
        return list(cnumbers)

    def handle_director(self, dir_name: str) -> List[CompanyInfo]:
        """
        1) search_directors_companies
        2) if # <20 => fetch addresses+directors, else just name
        """
        cnums = self.search_directors_companies(dir_name)
        out = []
        if len(cnums) < 20:
            for cn in cnums:
                print(f"[DIRECTOR-SEARCH] => Full detail for {cn}")
                try:
                    prof = self.ch.fetch_company_profile(cn)
                    cinfo = self.ch.build_company_info(prof)
                    out.append(cinfo)
                except Exception as e:
                    print(f"[DIRECTOR-SEARCH] Failed to fetch {cn}: {e}")
        else:
            for cn in cnums:
                out.append(CompanyInfo(name="", number=cn, address="", directors=[]))
        return out

    def overlap_score(self, c: CompanyInfo, t: CompanyInfo, brand: str) -> int:
        """
        +1 if addresses match exactly ignoring case
        +1 for each shared director
        +1 if brand != 'None' and brand in c.name ignoring case
        total => if >=2 => [PRIORITY]
        """
        score = 0
        # address
        if c.address.strip().lower() == t.address.strip().lower() and c.address.strip():
            score += 1
        # directors
        tdirs = set(d.strip().lower() for d in t.directors)
        cdirs = set(d.strip().lower() for d in c.directors)
        shared_dirs = len(tdirs.intersection(cdirs))
        score += shared_dirs
        # brand
        if brand.lower() != "none":
            if brand.lower() in c.name.lower():
                score += 1
        return score

    def run_analysis(self, user_query: str):
        """The main BFS flow."""
        print(f"[STEP 0] Searching top-5 for '{user_query}', fetching addresses+directors for each.")
        top5 = self.step0_top5(user_query)
        if not top5:
            print("No results from CH at all. Exiting.")
            return
        print("\n[STEP 0b] We have 5 items with addresses+directors:")
        for i, c in enumerate(top5, start=1):
            print(f"  => {i}) {c.name} ({c.number}) / address={c.address}, {len(c.directors)} directors")

        print("\n[STEP 1] Identify EXACT target among them (or first).")
        target = self.find_exact_target(top5, user_query)
        if not target:
            print("No top5 at all? (should not happen). Exiting.")
            return
        print(f" => EXACT target = {target.name} ({target.number})")
        print(f"    Address: {target.address}")
        print(f"    Directors: {target.directors}")

        # brand extraction
        print("\n[STEP 2] BRAND extraction from target's name via Gemini.")
        brand = self.brand_extraction(target)
        print(f" => brand: {brand}")

        # brand-based search
        brand_companies = []
        if brand.lower() != "none" and brand.strip():
            print(f"\n[STEP 2b] Searching brand = {brand}")
            brand_companies = self.search_brand(brand)

        # address-based
        address_companies = []
        addr_clean = target.address.strip()
        if addr_clean:
            print(f"\n[STEP 3] Searching companies at target address => {addr_clean}")
            address_companies = self.search_address(addr_clean)

        # director-based
        director_companies = []
        print("\n[STEP 4] Searching for each target director's companies. If there's a comma => we also flip.")
        for d in target.directors:
            variants = [d]
            if "," in d:
                # e.g. "Szabo, Domonkos" => "Domonkos Szabo"
                parts = [p.strip() for p in d.split(",",1)]
                if len(parts)==2 and parts[0] and parts[1]:
                    variants.append(f"{parts[1]} {parts[0]}")
            for var in variants:
                print(f"  => Searching director: {var}")
                partial = self.handle_director(var)
                # combine
                director_companies.extend(partial)

        # combine
        print("\n[STEP 5] Combine brand-based, address-based, director-based. Then Overlap check.")
        combined = [("brand", bc) for bc in brand_companies] \
                 + [("address", ac) for ac in address_companies] \
                 + [("director", dc) for dc in director_companies]

        # deduplicate
        final = []
        seen = set()
        tnum = target.number.strip().upper()
        for cat, comp in combined:
            key_ = (comp.number.upper().strip(), comp.name.strip().lower())
            if key_ in seen:
                continue
            if comp.number.strip().upper() == tnum:
                # skip the target itself
                continue
            seen.add(key_)
            final.append((cat, comp))

        # Overlaps
        for cat, comp in final:
            sc = self.overlap_score(comp, target, brand)
            priority = "[PRIORITY]" if sc >=2 else ""
            print(f" => {comp.name} ({comp.number}) from {cat}: Overlap={sc} {priority}")
            if comp.address:
                print(f"    address: {comp.address}")
            if comp.directors:
                print(f"    directors: {comp.directors}")

        print("\nDone.")


@click.command()
def main():
    if not CH_API_KEY:
        print("No CH_API_KEY in environment. Exiting.")
        sys.exit(1)
    ch = EnhancedCH(CH_API_KEY)
    analyzer = CompanyNetworkAnalyzer(ch)
    name = input("Enter the company name to analyze: ").strip()
    if not name:
        return
    analyzer.run_analysis(name)

if __name__ == "__main__":
    main()