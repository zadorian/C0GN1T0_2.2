#!/usr/bin/env python3
"""
hybrid_api_fallback.py

Demonstration of a single-file "Hybrid" approach that:
1) Tries Companies House (CH) first for each call
2) If CH is rate-limited (429) or daily usage exceeded => fallback to OpenCorporates (OC)
3) If OC also fails or is out of usage => fallback to CH again, or error if truly no option
4) Resets usage if new day

The user specifically wants:
 - If CH hits rate limit, switch immediately to OC *until* CH is available again
 - If OC hits rate limit or daily usage, switch back to CH with slower usage
 - If both are out, we raise an error

We track ephemeral counters for daily usage, resetting at midnight or whenever you prefer.
"""
import os
import sys
import time
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Union
from dataclasses import dataclass, field
import urllib.parse

import requests

# If you want brand extraction or other generative logic with Gemini:
import google.generativeai as genai
from dotenv import load_dotenv
from prompts import (
    WELCOME_MESSAGE,
    RATE_LIMIT_MESSAGE,
    DAILY_LIMIT_MESSAGE,
    NO_RESULTS_MESSAGE,
    MULTIPLE_RESULTS_MESSAGE,
    format_control_nature,
    get_company_network_analysis_prompt,
    get_ownership_structure_prompt,
    get_psc_ownership_prompt,
    format_company_info
)

from company_search.companies_house import CompaniesHouseAPI
from company_search.opencorporates import OpenCorporatesAPI, format_company_info
from AI_models.gemini_flash_1_5 import generate_with_retry

# Load env
load_dotenv()
CH_API_KEY = os.getenv("CH_API_KEY", "")
OC_API_KEY = os.getenv("OPENCORPORATES_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-pro")


@dataclass
class CompanyInfo:
    name: str
    number: str
    address: str
    directors: List[str] = field(default_factory=list)
    incorporation_date: Optional[str] = None
    status: Optional[str] = None
    company_type: Optional[str] = None
    source: str = "CH"  # "CH" or "OC"


###############################
# Fake or minimal stubs for OpenCorporates
###############################
class EnhancedOpenCorporatesAPI:
    """
    Minimal mock or partial code for OpenCorporates usage.
    In real code, you'd do real requests with your OC_API_KEY, handle rate-limits, etc.
    We'll just store usage counters and simulate 429 if we exceed daily usage or calls.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.opencorporates.com/v0.4"
        # Configure your session, etc.
        self.daily_limit = 1000  # or however many calls you can do
        self.calls_today = 0
        self.day_marker = datetime.now().strftime("%Y-%m-%d")

        # If we get a 429 from OC, we do a short cooldown
        self.oc_unavailable_until: Optional[datetime] = None

        self.current_search_id = None
        self.last_request_time = 0
        self.min_request_interval = 2.0  # Increased to 2 seconds
        self.max_retries = 5
        self.base_backoff = 5  # Base backoff in seconds

    def _check_new_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.day_marker:
            # new day, reset
            self.calls_today = 0
            self.day_marker = today

    def _maybe_429(self):
        """Simulate rate-limits or daily usage for demonstration."""
        self._check_new_day()
        if self.calls_today >= self.daily_limit:
            raise Exception("[OC] daily usage exceeded")
        # else no real 429 here for demonstration
        # If you do get a real 429 from OC, you'd do it in the actual request

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with exponential backoff retry logic."""
        for retry in range(self.max_retries):
            # Ensure minimum interval between requests
            time_since_last = time.time() - self.last_request_time
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                print(f"Rate limiting: waiting {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            
            try:
                response = super()._make_request(endpoint, params)
                self.last_request_time = time.time()
                return response
                
            except Exception as e:
                if "rate limit" in str(e).lower():
                    # Calculate exponential backoff time
                    backoff = self.base_backoff * (2 ** retry)
                    print(f"Rate limit exceeded (attempt {retry + 1}/{self.max_retries})")
                    print(f"Waiting {backoff} seconds before retry...")
                    time.sleep(backoff)
                    continue
                raise e
                
        print("Max retries exceeded - please wait a while before trying again")
        return None

    def search_companies(self, name: str, max_results: int=20) -> List[Dict]:
        """Pretend to call OpenCorporates for a name search."""
        self._maybe_429()
        self.calls_today += 1
        print(f"[OC] Searching '{name}' (calls_today={self.calls_today}/{self.daily_limit})")
        # Return some dummy partial results
        return [
            {"company_number": f"OC-{i}", "title": f"FakeOC Co {i}"} for i in range(min(3, max_results))
        ]

    def get_company_details(self, company_number: str, jurisdiction: str="gb") -> Optional[CompanyInfo]:
        self._maybe_429()
        self.calls_today += 1
        print(f"[OC] get_company_details {company_number} (calls_today={self.calls_today}/{self.daily_limit})")
        # Return a minimal mock
        return CompanyInfo(
            name=f"OC_{company_number}",
            number=company_number,
            address=f"OC Address for {company_number}",
            directors=["OC Dir A", "OC Dir B"],
            source="OC"
        )

    def get_officer_details(self, officer_id: str) -> Optional[Dict]:
        """Get detailed information about an officer by their ID"""
        url = f"{self.base_url}/officers/{officer_id}"
        try:
            response = self._make_request(url)
            if response and 'results' in response:
                return response['results']
            return None
        except Exception as e:
            print(f"Error getting officer details: {e}")
            return None


###############################
# Companies House
###############################
class EnhancedCompaniesHouseAPI:
    """
    Minimal approach for CH usage, with daily usage limit and
    a real check for 429 from the HTTP response. We'll store ephemeral usage counters.
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

        # If we get 429, we do a fallback window
        self.ch_unavailable_until: Optional[datetime] = None

    def _check_new_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.day_marker:
            self.calls_today = 0
            self.day_marker = today

    def _make_request(self, url: str):
        self._check_new_day()
        if self.calls_today >= self.daily_limit:
            # out of daily usage
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
        """Search for companies with case-insensitive name matching."""
        # Convert name to lowercase for consistent searching
        name = name.lower()
        url = f"{self.base_url}/search/companies?q={name}&items_per_page={max_results}"
        data = self._make_request(url)
        if not data or "items" not in data:
            return []
        out = []
        for it in data["items"]:
            # Store original case but match case-insensitively
            out.append({
                "company_number": it.get("company_number",""),
                "title": it.get("title","")
            })
        return out

    def get_company_profile(self, number: str) -> Optional[dict]:
        """Get company profile with case-insensitive number matching."""
        # Convert number to uppercase as Companies House uses uppercase numbers
        number = number.upper()
        url = f"{self.base_url}/company/{number}"
        return self._make_request(url)

    def format_address(self, address: Dict) -> str:
        """Format address dictionary into a readable string."""
        parts = [
            address.get("address_line_1", ""),
            address.get("address_line_2", ""),
            address.get("locality", ""),
            address.get("region", ""),
            address.get("postal_code", ""),
            address.get("country", "")
        ]
        return ", ".join(part for part in parts if part)

    def get_company_details(self, company_number: str) -> CompanyInfo:
        """Get basic company details"""
        url = f"{self.base_url}/company/{company_number}"
        try:
            result = self._make_request(url)
            if result:
                return CompanyInfo(
                    name=result.get("company_name", ""),
                    number=result.get("company_number", ""),
                    address=self.format_address(result.get("registered_office_address", {})),
                    incorporation_date=result.get("date_of_creation", ""),
                    status=result.get("company_status", ""),
                    company_type=result.get("type", ""),
                    source="CH"
                )
        except Exception as e:
            print(f"Error getting company details: {e}")
        return None

    def get_company_officers(self, number: str) -> List[Dict]:
        """Get company officers with case-insensitive matching."""
        # Convert number to uppercase for consistency
        number = number.upper()
        url = f"{self.base_url}/company/{number}/officers"
        data = self._make_request(url)
        if not data or "items" not in data:
            return []
        out = []
        for it in data["items"]:
            out.append({
                "officer_number": it.get("officer_number", ""),
                "name": it.get("name", ""),
                "officer_role": it.get("officer_role", "")
            })
        return out

    def get_officer_appointments(self, officer_name: str) -> List[Dict]:
        """
        Search for officer appointments using Companies House API
        /search/officers endpoint and then get details from /officers/{officer_id}/appointments
        """
        # First search for the officer to get their ID
        search_url = f"{self.base_url}/search/officers"
        params = {
            "q": officer_name
        }
        search_results = self._make_request(search_url)
        
        if not search_results or "items" not in search_results:
            return []

        appointments = []
        for officer in search_results["items"]:
            if officer.get("officer_role") in ["director", "corporate-director"]:
                officer_id = officer.get("links", {}).get("self", "").split("/")[-1]
                if officer_id:
                    # Get appointments for this officer ID
                    appointments_url = f"{self.base_url}/officers/{officer_id}/appointments"
                    try:
                        appts = self._make_request(appointments_url)
                        if appts and "items" in appts:
                            appointments.extend(appts["items"])
                    except Exception as e:
                        print(f"Error getting appointments for {officer_id}: {e}")

        return appointments

    def get_company_pscs(self, company_number: str) -> List[Dict]:
        """
        Get Persons with Significant Control (PSCs) for a company
        Using /company/{company_number}/persons-with-significant-control endpoint
        """
        url = f"{self.base_url}/company/{company_number}/persons-with-significant-control"
        try:
            results = self._make_request(url)
            if results and "items" in results:
                return results["items"]
        except Exception as e:
            print(f"Error getting PSCs: {e}")
        return []

    def get_corporate_pscs(self, company_number: str) -> List[Dict]:
        """
        Get Corporate PSCs for a company
        Using /company/{company_number}/persons-with-significant-control/corporate-entity
        """
        url = f"{self.base_url}/company/{company_number}/persons-with-significant-control/corporate-entity"
        try:
            results = self._make_request(url)
            if results and "items" in results:
                return results["items"]
        except Exception as e:
            print(f"Error getting corporate PSCs: {e}")
        return []

    def generate_network_analysis(self, prompt: str) -> Optional[str]:
        """Generate network analysis using Gemini"""
        try:
            return generate_with_retry(prompt)
        except Exception as e:
            print(f"Network analysis generation failed: {e}")
            return None


###############################
# HYBRID logic
###############################
class HybridCompanyAPI:
    """
    We keep track of:
      - CH usage + fallback window
      - OC usage + fallback window
    We always attempt CH first. If CH is in a fallback window or daily limit,
    we try OC. If OC is also in fallback or daily limit, we try CH again, or fail if truly both are out.
    """

    def __init__(self, ch_api_key: str, oc_api_key: str):
        """Initialize the hybrid API client with both API keys."""
        self.ch_api = EnhancedCompaniesHouseAPI(ch_api_key)
        # Initialize OpenCorporates API without passing the key
        self.oc_api = OpenCorporatesAPI()
        # Store the keys
        self.ch_api_key = ch_api_key
        self.oc_api_key = oc_api_key
        
        # Initialize state
        self.ch_unavailable_until = None
        self.oc_unavailable_until = None
        self.current_search_id = None
        self.last_request_time = 0
        self.min_request_interval = 1.0

        # If CH triggers 429 => ch_fallback_until = now + X
        # If CH daily usage => ch_fallback_until = end of day or some next window
        self.ch_fallback_until: Optional[datetime] = None

        # If OC triggers daily usage or 429 => oc_fallback_until = ...
        self.oc_fallback_until: Optional[datetime] = None

        # some fallback durations
        self.rate_limit_cooldown = 120  # 2 minutes
        self.oc_rate_limit_cooldown = 120

    def _ch_available(self) -> bool:
        """Check if CH is not in fallback window."""
        if self.ch_fallback_until and datetime.now() < self.ch_fallback_until:
            return False
        return True

    def _oc_available(self) -> bool:
        """Check if OC is not in fallback window."""
        if self.oc_fallback_until and datetime.now() < self.oc_fallback_until:
            return False
        return True

    def _fail_ch(self, reason: str="429"):
        """Mark CH unavailable for some time, e.g. 2 minutes or until next day."""
        if reason == "daily":
            # If daily usage is exceeded, set fallback until next day 00:00 for example
            tomorrow = datetime.now().date() + timedelta(days=1)
            fallback_start = datetime.combine(tomorrow, datetime.min.time())
            self.ch_fallback_until = fallback_start
            print(f"[HYBRID] CH daily usage exceeded => fallback until {self.ch_fallback_until}")
        else:
            # For 429 or other
            cool_until = datetime.now() + timedelta(seconds=self.rate_limit_cooldown)
            self.ch_fallback_until = cool_until
            print(f"[HYBRID] CH is rate-limited => fallback until {cool_until}")

    def _fail_oc(self, reason: str="429"):
        if reason == "daily":
            # fallback until next day
            tomorrow = datetime.now().date() + timedelta(days=1)
            fallback_start = datetime.combine(tomorrow, datetime.min.time())
            self.oc_fallback_until = fallback_start
            print(f"[HYBRID] OC daily usage => fallback until {self.oc_fallback_until}")
        else:
            # short fallback
            cool_until = datetime.now() + timedelta(seconds=self.oc_rate_limit_cooldown)
            self.oc_fallback_until = cool_until
            print(f"[HYBRID] OC rate-limited => fallback until {cool_until}")

    # A helper to "try CH else fallback to OC else fallback to CH else error"
    def try_ch_else_oc(self, ch_func, oc_func):
        """
        ch_func: a zero-argument function that calls CH
        oc_func: a zero-argument function that calls OC
        We'll do:
          1) If CH available => call it
             a) if success => return
             b) if fail => fallback to OC
          2) If OC also fails => fallback to CH again or error
        """
        # 1) Attempt CH if not fallback
        if self._ch_available():
            try:
                return ch_func()
            except Exception as e:
                emsg = str(e).lower()
                if "429" in emsg:
                    self._fail_ch("429")
                elif "daily usage" in emsg:
                    self._fail_ch("daily")
                else:
                    print(f"[HYBRID] CH error => {e}")
                # fallback to OC

        # 2) Attempt OC if not fallback
        if self._oc_available():
            try:
                return oc_func()
            except Exception as e:
                emsg = str(e).lower()
                if "429" in emsg:
                    self._fail_oc("429")
                elif "daily usage" in emsg:
                    self._fail_oc("daily")
                else:
                    print(f"[HYBRID] OC error => {e}")
                # fallback to CH again

        # 3) final attempt CH if we haven't tried it or if fallback ended
        if self._ch_available():
            try:
                return ch_func()
            except Exception as e:
                print(f"[HYBRID] final CH error => {e}")

        # if we get here, we can't do anything
        raise Exception("[HYBRID] Both CH + OC are unavailable or daily usage exceeded")

    ############################
    # Now the actual "public" methods:
    ############################
    def search_companies(self, name: str, max_results: int=20) -> List[CompanyInfo]:
        """
        We'll define a function that returns a list of CompanyInfo by searching name
        in CH or fallback in OC.
        """
        def ch_search():
            # ch raw results
            raw = self.ch_api.search_companies(name, max_results)
            out = []
            for r in raw:
                # get minimal details
                cinfo = self.ch_api.get_company_details(r["company_number"])
                if cinfo:
                    out.append(cinfo)
            return out

        def oc_search():
            raw = self.oc_api.search_companies(name, max_results)
            out = []
            for r in raw:
                cinfo = self.oc_api.get_company_details(r["company_number"], "gb")
                if cinfo:
                    out.append(cinfo)
            return out

        return self.try_ch_else_oc(ch_search, oc_search)

    def get_full_company_details(self, company_number: str) -> Dict:
        """Get complete details for a company including directors, with fallback to OC"""
        try:
            # Try Companies House first
            if self._ch_available():
                try:
                    company = self.ch_api.get_company_details(company_number)
                    if company:
                        officers = self.ch_api.get_company_officers(company_number)
                        company.directors = [
                            o["name"] for o in officers 
                            if o.get("officer_role") in ["director", "corporate-director"]
                        ]
                        return {
                            "name": company.name,
                            "number": company.number,
                            "address": company.address,
                            "directors": company.directors,
                            "incorporation_date": company.incorporation_date,
                            "status": company.status,
                            "company_type": company.company_type,
                            "source": "CH"
                        }
                except Exception as e:
                    if "429" in str(e):
                        self._fail_ch("429")
                    elif "daily" in str(e).lower():
                        self._fail_ch("daily")
                    print(f"[CH] Failed, trying OC: {e}")

            # Try OpenCorporates if CH failed or unavailable
            if self._oc_available():
                try:
                    company = self.oc_api.get_company_details(company_number)
                    if company:
                        return {
                            "name": company.name,
                            "number": company.number,
                            "address": company.address,
                            "directors": company.directors,
                            "incorporation_date": company.incorporation_date,
                            "status": company.status,
                            "company_type": company.company_type,
                            "source": "OC"
                        }
                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        self._fail_oc("429")
                    elif "daily" in str(e).lower():
                        self._fail_oc("daily")
                    print(f"[OC] Failed: {e}")

            # If both failed, try CH again with slower rate
            if self._ch_available():
                time.sleep(2)  # Extra delay
                try:
                    company = self.ch_api.get_company_details(company_number)
                    if company:
                        officers = self.ch_api.get_company_officers(company_number)
                        company.directors = [
                            o["name"] for o in officers 
                            if o.get("officer_role") in ["director", "corporate-director"]
                        ]
                        return {
                            "name": company.name,
                            "number": company.number,
                            "address": company.address,
                            "directors": company.directors,
                            "incorporation_date": company.incorporation_date,
                            "status": company.status,
                            "company_type": company.company_type,
                            "source": "CH"
                        }
                except Exception as e:
                    print(f"[CH] Final attempt failed: {e}")

        except Exception as e:
            print(f"Error getting company details: {e}")

        return None

    def extract_brand_name(self, company_name: str) -> str:
        """Extract brand name from company name."""
        # Simple heuristic: take the first word as the brand name
        return company_name.split()[0]

    def analyze_company_network(self, search_term: str) -> Optional[Dict]:
        print("\n" + "="*50)
        print("1. TARGET COMPANY IDENTIFICATION")
        print("="*50)
        
        # Get target company
        target_result = self.find_target_company(search_term)
        if not target_result:
            return None
            
        # Get full details
        company_number = target_result["company_number"]
        target = self.ch_api.get_company_details(company_number)
        officers = self.ch_api.get_company_officers(company_number)
        target.directors = [
            officer["name"] for officer in officers 
            if officer.get("officer_role") in ["director", "corporate-director"]
        ]
        
        # Print basic company info and directors
        print(f"\n[TARGET COMPANY]")
        print(f"{target.name}")
        print("="*len(target.name))
        print(f"\nNumber: {target.number}")
        print(f"Address: {target.address}")
        print("\nDirectors:")
        for director in target.directors:
            print(f"-{director}")

        # Get and print ownership structure
        print("\nBeneficial Owners:")
        pscs = self.ch_api.get_company_pscs(company_number)
        corporate_pscs = self.ch_api.get_corporate_pscs(company_number)

        if pscs:
            for psc in pscs:
                print(f"\n- {psc.get('name', 'Unknown')}")
                controls = format_control_nature(psc.get('natures_of_control', []))
                print(f"  Control: {controls}")
                print(f"  Ownership: {psc.get('shares', {}).get('percentage', 'Unknown')}%")

        if corporate_pscs:
            for corp in corporate_pscs:
                print(f"\n- {corp.get('name', 'Unknown')}")
                print(f"  Company number: {corp.get('identification', {}).get('registration_number', 'Unknown')}")
                controls = format_control_nature(corp.get('natures_of_control', []))
                print(f"  Control: {controls}")
                print(f"  Ownership: {corp.get('shares', {}).get('percentage', 'Unknown')}%")

        # Director analysis using OpenCorporates
        print("\n[DIRECTOR ANALYSIS]")
        for director in target.directors:
            try:
                print(f"\nAnalyzing directorships for: {director}")
                print("=" * (len(director) + 24))
                
                results = self.oc_api.search_officers(
                    query=director,
                    jurisdiction_code="gb"
                )
                
                if results and 'results' in results and 'officers' in results['results']:
                    officers = results['results']['officers']
                    
                    if not officers:
                        print("No active directorships found")
                        continue
                        
                    for officer in officers:
                        officer_info = officer.get('officer', {})
                        company_info = officer_info.get('company', {})
                        
                        if company_info:
                            print(f"\nCompany: {company_info.get('name', 'Unknown')}")
                            print(f"Number: {company_info.get('company_number', 'Unknown')}")
                            print(f"Jurisdiction: {company_info.get('jurisdiction_code', 'Unknown').upper()}")
                            print(f"Position: {officer_info.get('position', 'Unknown')}")
                            print(f"Appointed: {officer_info.get('start_date', 'Unknown')}")
                            if officer_info.get('end_date'):
                                print(f"Ended: {officer_info.get('end_date')}")
                            
                            # Get company details using the same format as the CLI search
                            try:
                                company_results = self.oc_api.search_companies(
                                    query=company_info.get('name'),
                                    jurisdiction_code=company_info.get('jurisdiction_code')
                                )
                                
                                if company_results and 'results' in company_results and 'companies' in company_results['results']:
                                    for company in company_results['results']['companies']:
                                        if company['company']['company_number'] == company_info.get('company_number'):
                                            print(format_company_info(company, self.oc_api))
                                            break
                            except Exception as e:
                                print(f"Error getting company details: {e}")
                            
                            print("-" * 40)
                else:
                    print("No directorship information found")
                    
            except Exception as e:
                print(f"Error searching directorships: {e}")

        # Show details of other companies from initial search
        print("\n[RELATED COMPANIES FROM INITIAL SEARCH]")
        initial_results = self.ch_api.search_companies(search_term, max_results=5)
        for company in initial_results:
            if company['company_number'] != target.number:  # Skip target company as we already showed it
                details = self.ch_api.get_company_details(company['company_number'])
                officers = self.ch_api.get_company_officers(company['company_number'])
                if details:
                    print(f"\n{details.name}")
                    print("="*len(details.name))
                    print(f"Number: {details.number}")
                    print(f"Address: {details.address}")
                    print("\nDirectors:")
                    for officer in officers:
                        if officer.get("officer_role") in ["director", "corporate-director"]:
                            print(f"-{officer['name']}")

        # Brand analysis
        print("\n[BRAND ANALYSIS]")
        brand = self.extract_brand_name(target.name)
        print(f"Brand identified: {brand}")
        brand_companies = self.get_brand_related_companies(brand)
        if brand_companies:
            print("\nCompanies sharing brand name:")
            if len(brand_companies) <= 12:
                for company in brand_companies:
                    details = self.ch_api.get_company_details(company['company_number'])
                    officers = self.ch_api.get_company_officers(company['company_number'])
                    if details:
                        print(f"\n{details.name}")
                        print("-" * len(details.name))
                        print(f"Number: {details.number}")
                        print(f"Address: {details.address}")
                        print("Directors:")
                        for officer in officers:
                            if officer.get("officer_role") in ["director", "corporate-director"]:
                                print(f"-{officer['name']}")
            else:
                print(f"\nToo many brand-related companies ({len(brand_companies)}) for full details. Basic list:")
                for company in brand_companies:
                    print(f"- {company.get('name', 'Unknown')} ({company.get('company_number', 'Unknown')})")

        # Address analysis
        print("\n[ADDRESS ANALYSIS]")
        target_address = target.address
        address_companies = self.ch_api.search_companies(
            f'registered_office_address:"{target_address}"', 
            max_results=20
        )
        if address_companies:
            print(f"\nCompanies at same address ({target_address}):")
            for company in address_companies:
                if company['company_number'] != target.number:  # Skip target company
                    print(f"- {company['title']} ({company['company_number']})")

        print("\n[NETWORK ANALYSIS]")
        
        # Structure the data properly for the network analysis
        network_data = {
            "target_company": {
                "name": target.name,
                "number": target.number,
                "address": target.address,
                "directors": target.directors,
                "beneficial_owners": []
            },
            "initial_search_results": [
                {
                    "name": company.name,
                    "number": company.number,
                    "address": company.address,
                    "directors": company.directors if hasattr(company, 'directors') else []
                }
                for company in initial_results
            ],
            "brand_companies": [
                {
                    "name": company.get("title", ""),
                    "number": company.get("company_number", "")
                }
                for company in brand_companies
            ],
            "address_companies": [
                {
                    "name": company.get("title", ""),
                    "number": company.get("company_number", "")
                }
                for company in address_companies
            ]
        }

        # Add PSC data if available
        if pscs:
            network_data["target_company"]["beneficial_owners"] = [
                {
                    "name": psc.get("name", "Unknown"),
                    "type": "individual" if "name" in psc else "corporate",
                    "percentage": psc.get("shares", {}).get("percentage", "Unknown"),
                    "nature_of_control": psc.get("natures_of_control", [])
                }
                for psc in pscs
            ]

        if corporate_pscs:
            network_data["target_company"]["beneficial_owners"].extend([
                {
                    "name": corp.get("name", "Unknown"),
                    "type": "corporate",
                    "percentage": corp.get("shares", {}).get("percentage", "Unknown"),
                    "nature_of_control": corp.get("natures_of_control", [])
                }
                for corp in corporate_pscs
            ])

        # Get the analysis using Gemini
        try:
            prompt = get_company_network_analysis_prompt(network_data)
            
            analysis = generate_with_retry(prompt)
            if analysis:
                print("\nNetwork Analysis Results:")
                print("=" * 50)
                print(analysis)
            else:
                print("\nFailed to generate network analysis")
            
        except Exception as e:
            print(f"\nError in network analysis: {str(e)}")
            return None

        return {
            "target": target,
            "network_data": network_data,
            "analysis": analysis if 'analysis' in locals() else None
        }

    def find_target_company(self, search_term: str) -> Optional[Dict]:
        """Find target company from CH search results"""
        # Get up to 5 results from Companies House
        results = self.ch_api.search_companies(search_term, max_results=5)
        
        if not results:
            print("[ERROR] No companies found")
            return None
        
        # Clean up search term for comparison
        clean_search = search_term.lower().replace('ltd', '').replace('limited', '').strip()
        
        # First try exact match with the search term
        for result in results:
            clean_title = result['title'].lower().replace('ltd', '').replace('limited', '').strip()
            if clean_title == clean_search:
                return result
            
        # If no exact match, show all results and let user choose
        print("\nMultiple companies found. Please select one:")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['title']} ({r['company_number']})")
        
        while True:
            try:
                choice = int(input("\nEnter number (or 0 to exit): "))
                if choice == 0:
                    return None
                if 1 <= choice <= len(results):
                    return results[choice-1]
            except ValueError:
                pass
            print("Invalid choice. Please try again.")
        
        return None

    def get_brand_related_companies(self, brand: str) -> List[Dict]:
        """Get companies that share the brand name using OpenCorporates."""
        if not brand or brand == "NONE":
            return []
        
        # Use the same search pattern as the CLI
        results = self.oc_api.search_companies(
            query=brand,
            jurisdiction_code="gb"  # First try UK companies
        )
        
        companies = []
        if results and 'results' in results and 'companies' in results['results']:
            print("\nCompanies sharing brand name:")
            for company in results['results']['companies']:
                try:
                    print(format_company_info(company, self.oc_api))
                    print("-" * 40)
                    companies.append(company)
                except Exception as e:
                    print(f"Error getting company details: {e}")
                    continue
        
        return companies


def print_company_details(company):
    """Pretty print company details in requested format"""
    print(f"\n{company.name.upper()}")
    print(f"\nNumber: {company.number}")
    print(f"Address: {company.address}")
    print("\nDirectors:")
    for director in company.directors:
        print(f"-{director}")
    print("\n")  # Extra space between companies

def print_director_companies(director_name, companies):
    """Pretty print companies under a director search"""
    print(f"\n{director_name.upper()}")
    print("\n")  # Space after director name
    
    for company in companies:
        print(f"-{company.name}")
        print(f"\nNumber: {company.number}")
        print(f"Address: {company.address}")
        print("\nDirectors:")
        for dir in company.directors:
            print(f"     -{dir}")
        print("\n")  # Space between companies

def format_control_nature(control_list: List[str]) -> str:
    """Convert control nature codes into readable text"""
    control_map = {
        'ownership-of-shares-75-to-100-percent': 'Owns 75-100% of shares',
        'ownership-of-shares-50-to-75-percent': 'Owns 50-75% of shares',
        'ownership-of-shares-25-to-50-percent': 'Owns 25-50% of shares',
        'voting-rights-75-to-100-percent': 'Controls 75-100% of voting rights',
        'voting-rights-50-to-75-percent': 'Controls 50-75% of voting rights',
        'voting-rights-25-to-50-percent': 'Controls 25-50% of voting rights',
        'right-to-appoint-and-remove-directors': 'Can appoint/remove directors',
        'significant-influence-or-control': 'Has significant control'
    }
    
    return ', '.join(control_map.get(control, control) for control in control_list)

def main():
    ch_key = CH_API_KEY
    oc_key = OC_API_KEY
    if not ch_key:
        print("Missing CH_API_KEY in environment. Exiting.")
        sys.exit(1)
    if not oc_key:
        print("Warning: no OPENCORPORATES_API_KEY set. We'll still try fallback, but might fail if used...")

    hybrid = HybridCompanyAPI(ch_key, oc_key)

    name = input("Enter a company name to analyze: ").strip()
    if not name:
        return

    # do BFS
    result = hybrid.analyze_company_network(name)

if __name__ == "__main__":
    main()
