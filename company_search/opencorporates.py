import requests
from typing import Dict, List, Optional, Union
import json
import os
from datetime import datetime
from AI_models.gemini_flash_1_5 import generate_with_retry  # Replace Claude

class OpenCorporatesAPI:
    def __init__(self):
        """Initialize the OpenCorporates API client."""
        self.base_url = "https://api.opencorporates.com/v0.4"
        self.api_token = "UvjlNXuBiIeNymveADRR"
        self.session = requests.Session()
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the OpenCorporates API.
        
        Args:
            endpoint (str): API endpoint to call
            params (dict, optional): Query parameters
            
        Returns:
            dict: JSON response from the API
        """
        if params is None:
            params = {}
            
        # Add API token to parameters
        params['api_token'] = self.api_token
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            return {}

    def search_companies(self,  
                        query: str = None,
                        jurisdiction_code: Optional[str] = None,
                        country_code: Optional[str] = None,
                        company_type: Optional[str] = None,
                        registered_address: Optional[str] = None,
                        industry_codes: Optional[str] = None,
                        current_status: Optional[str] = None,
                        incorporation_date: Optional[str] = None,
                        dissolution_date: Optional[str] = None,
                        created_at: Optional[str] = None,
                        updated_at: Optional[str] = None,
                        identifier_uids: Optional[str] = None,
                        normalise_company_name: Optional[bool] = None,
                        types_of_data_held: Optional[str] = None,
                        order: Optional[str] = None,
                        inactive: Optional[bool] = None,
                        page: int = 1,
                        per_page: int = 30) -> Dict:
        """Enhanced company search with all available filters."""
        params = {
            'page': page,
            'per_page': min(per_page, 100)
        }
        
        # Add optional parameters if provided
        if query:
            params['q'] = query
        if jurisdiction_code:
            params['jurisdiction_code'] = jurisdiction_code
        if country_code:
            params['country_code'] = country_code
        if company_type:
            params['company_type'] = company_type
        if registered_address:
            params['registered_address'] = registered_address
        if industry_codes:
            params['industry_codes'] = industry_codes
        if current_status:
            params['current_status'] = current_status
        if incorporation_date:
            params['incorporation_date'] = incorporation_date
        if dissolution_date:
            params['dissolution_date'] = dissolution_date
        if created_at:
            params['created_at'] = created_at
        if updated_at:
            params['updated_at'] = updated_at
        if identifier_uids:
            params['identifier_uids'] = identifier_uids
        if normalise_company_name is not None:
            params['normalise_company_name'] = str(normalise_company_name).lower()
        if types_of_data_held:
            params['types_of_data_held'] = types_of_data_held
        if order:
            params['order'] = order
        if inactive is not None:
            params['inactive'] = str(inactive).lower()
            
        return self._make_request('companies/search', params)

    def get_company_details(self, jurisdiction_code: str, company_number: str) -> Dict:
        """Get detailed information about a specific company.
        
        Args:
            jurisdiction_code (str): Company jurisdiction code
            company_number (str): Company registration number
            
        Returns:
            dict: Company details
        """
        endpoint = f'companies/{jurisdiction_code}/{company_number}'
        return self._make_request(endpoint)

    def get_company_filings(self, 
                          jurisdiction_code: str, 
                          company_number: str,
                          page: int = 1) -> Dict:
        """Get company filings.
        
        Args:
            jurisdiction_code (str): Company jurisdiction code
            company_number (str): Company registration number
            page (int): Page number for pagination
            
        Returns:
            dict: Company filings
        """
        endpoint = f'companies/{jurisdiction_code}/{company_number}/filings'
        params = {'page': page}
        return self._make_request(endpoint, params)

    def get_jurisdictions(self) -> Dict:
        """Get list of available jurisdictions.
        
        Returns:
            dict: List of jurisdictions
        """
        return self._make_request('jurisdictions')

    def search_by_fields(self, 
                        query: str,
                        fields: List[str]) -> Dict:
        """Search companies by specific fields.
        
        Available fields:
        - name
        - normalised_name
        - company_number
        - heavily_normalised_number
        - native_company_number
        - previous_names
        - postal_codes
        - trademark_registration_mark_texts
        """
        params = {
            'q': query,
            'fields': ','.join(fields)
        }
        return self._make_request('companies/search', params)

    def search_company_events(self,
                            jurisdiction_code: str,
                            event_type: Optional[str] = None,
                            time_range: Optional[str] = None,
                            categories: Optional[str] = None) -> Dict:
        """Search company events in a jurisdiction.
        
        Args:
            jurisdiction_code: Country/jurisdiction code
            event_type: Type of event (e.g., 'Event::Company::Incorporation')
            time_range: Date range (YYYY-MM-DD:YYYY-MM-DD)
            categories: Event categories (e.g., 'kyc')
        """
        params = {}
        if event_type:
            params['type'] = event_type
        if time_range:
            params['time_range'] = time_range
        if categories:
            params['categories'] = categories
            
        endpoint = f'companies/{jurisdiction_code}/events'
        return self._make_request(endpoint, params)

    def search_by_previous_names(self, name: str) -> Dict:
        """Search companies by their previous names."""
        return self.search_by_fields(name, ['previous_names'])

    def search_by_postal_code(self, postal_code: str) -> Dict:
        """Search companies by postal code."""
        return self.search_by_fields(postal_code, ['postal_codes'])

    def search_by_trademark(self, trademark: str) -> Dict:
        """Search companies by trademark registration."""
        return self.search_by_fields(trademark, ['trademark_registration_mark_texts'])

    def search_alternate_registrations(self, jurisdiction_code: str, company_number: str) -> Dict:
        """Get alternate registrations for a company."""
        results = self.get_company_details(jurisdiction_code, company_number)
        if results and 'results' in results:
            return results['results'].get('company', {}).get('alternate_registration_entities', [])
        return []

    def search_with_filters(self,
                           branch: Optional[bool] = None,
                           nonprofit: Optional[bool] = None,
                           date_range: Optional[Dict[str, str]] = None,
                           order_by: Optional[str] = None) -> Dict:
        """
        Advanced search with additional filters.
        
        Args:
            branch (bool): Filter for branch companies
            nonprofit (bool): Filter for nonprofit companies
            date_range (dict): Date range for various dates (incorporation, dissolution, etc)
            order_by (str): Sort results by (score, created_at, updated_at, 
                            incorporation_date, dissolution_date)
        """
        params = {}
        
        if branch is not None:
            params['branch'] = str(branch).lower()
        if nonprofit is not None:
            params['nonprofit'] = str(nonprofit).lower()
        if date_range:
            for date_type, date_value in date_range.items():
                params[date_type] = date_value
        if order_by:
            params['order'] = order_by
            
        return self._make_request('companies/search', params)

    def search_officers(self,
                       query: str = None,
                       jurisdiction_code: Optional[str] = None,
                       position: Optional[str] = None,
                       date_of_birth: Optional[str] = None,
                       address: Optional[str] = None,
                       inactive: Optional[bool] = None,
                       order: Optional[str] = 'score',
                       page: int = 1,
                       per_page: int = 30) -> Dict:
        """Search for company officers (directors, agents, etc.).
        
        Args:
            query (str): Name of the officer
            jurisdiction_code (str, optional): Filter by jurisdiction
            position (str, optional): Filter by position (e.g., 'director', 'ceo', 'agent')
            date_of_birth (str, optional): Filter by DOB (YYYY-MM-DD) - UK only
            address (str, optional): Filter by address
            inactive (bool, optional): Include/exclude inactive officers
            order (str, optional): Sort order ('score' or alphabetical if None)
            page (int): Page number
            per_page (int): Results per page
        """
        params = {
            'page': page,
            'per_page': min(per_page, 100)
        }
        
        if query:
            params['q'] = query
        if jurisdiction_code:
            params['jurisdiction_code'] = jurisdiction_code
        if position:
            params['position'] = position
        if date_of_birth:
            params['date_of_birth'] = date_of_birth
        if address:
            params['address'] = address
        if inactive is not None:
            params['inactive'] = str(inactive).lower()
        if order:
            params['order'] = order
            
        return self._make_request('officers/search', params)

    def search_company_network(self, 
                             jurisdiction_code: str, 
                             company_number: str,
                             confidence: Optional[int] = 60,
                             dates: Optional[str] = None,
                             ownership_percentage: Optional[int] = None) -> Dict:
        """Search company's corporate network (parents and subsidiaries).
        
        Args:
            jurisdiction_code: Company jurisdiction code
            company_number: Company registration number
            confidence: Minimum confidence score (0-100) for relationships
            dates: Date to get historical network data (ISO 8601 format)
            ownership_percentage: Minimum ownership percentage to include
        """
        endpoint = f'companies/{jurisdiction_code}/{company_number}/network'
        params = {}
        
        if confidence:
            params['confidence'] = confidence
        if dates:
            params['dates'] = dates
        if ownership_percentage is not None:
            params['ownership_percentage'] = ownership_percentage
            
        return self._make_request(endpoint, params)

    def search_company_statements(self,
                                jurisdiction_code: str,
                                company_number: str,
                                page: int = 1) -> Dict:
        """Get statements about a company (facts from various sources).
        
        Args:
            jurisdiction_code: Company jurisdiction code
            company_number: Company registration number
            page: Page number for pagination
        """
        endpoint = f'companies/{jurisdiction_code}/{company_number}/statements'
        params = {'page': page}
        return self._make_request(endpoint, params)

    def search_gazette_notices(self,
                             query: str,
                             jurisdiction_code: Optional[str] = None,
                             publication_title: Optional[str] = None,
                             classification: Optional[str] = None,
                             order: Optional[str] = 'date_published',
                             page: int = 1) -> Dict:
        """Search gazette notices.
        
        Args:
            query: Search term
            jurisdiction_code: Filter by jurisdiction
            publication_title: Filter by publication
            classification: Filter by notice type
            order: Sort order ('date_published' or 'score')
            page: Page number
        """
        endpoint = 'statements/gazette_notices/search'
        params = {
            'q': query,
            'page': page,
            'order': order
        }
        
        if jurisdiction_code:
            params['jurisdiction_code'] = jurisdiction_code
        if publication_title:
            params['publication_title'] = publication_title
        if classification:
            params['normalised_classification_level_1'] = classification
            
        return self._make_request(endpoint, params)

    def search_control_statements(self,
                                query: Optional[str] = None,
                                is_ultimate_beneficial_owner: Optional[bool] = None,
                                has_controlling_entities: Optional[bool] = None,
                                control_mechanisms: Optional[str] = None,
                                controlling_entity_types: Optional[str] = None,
                                controlled_entity_name: Optional[str] = None,
                                controlling_entity_name: Optional[str] = None,
                                order: Optional[str] = 'created_at',
                                page: int = 1) -> Dict:
        """Search control statements about company ownership and control.
        
        Args:
            query: General search term
            is_ultimate_beneficial_owner: Filter for ultimate beneficial owners
            has_controlling_entities: Filter for presence of controlling entities
            control_mechanisms: Filter by control type (e.g. share ownership)
            controlling_entity_types: Filter by controller type (e.g. company, person)
            controlled_entity_name: Name of controlled entity
            controlling_entity_name: Name of controlling entity
            order: Sort order ('created_at' or 'score')
            page: Page number
        """
        endpoint = 'statements/control_statements/search'
        params = {'page': page, 'order': order}
        
        if query:
            params['q'] = query
        if is_ultimate_beneficial_owner is not None:
            params['is_ultimate_beneficial_owner'] = str(is_ultimate_beneficial_owner).lower()
        if has_controlling_entities is not None:
            params['has_controlling_entities'] = str(has_controlling_entities).lower()
        if control_mechanisms:
            params['control_mechanisms_mechanism_type'] = control_mechanisms
        if controlling_entity_types:
            params['controlling_entities_entity_type'] = controlling_entity_types
        if controlled_entity_name:
            params['controlled_entity_name'] = controlled_entity_name
        if controlling_entity_name:
            params['controlling_entities_name'] = controlling_entity_name
            
        return self._make_request(endpoint, params)

    def search_trademark_registrations(self,
                                     query: str,
                                     order: Optional[str] = 'created_at',
                                     page: int = 1) -> Dict:
        """Search trademark registrations.
        
        Args:
            query: Search term matching trademark text
            order: Sort by ('created_at', 'mark_text', 'registration_date', 
                   'expiry_date', 'score')
            page: Page number
        """
        endpoint = 'statements/trademark_registrations/search'
        params = {
            'q': query,
            'order': order,
            'page': page
        }
        return self._make_request(endpoint, params)

    def match_jurisdiction(self, 
                          query: str,
                          related_jurisdiction_code: Optional[str] = None) -> Dict:
        """Match jurisdiction names to codes.
        
        Args:
            query: Jurisdiction name or code to match
            related_jurisdiction_code: Optional related jurisdiction to help disambiguation
        """
        params = {'q': query}
        if related_jurisdiction_code:
            params['related_jurisdiction_code'] = related_jurisdiction_code
        return self._make_request('jurisdictions/match', params)

    def get_industry_codes(self,
                          code_scheme_id: Optional[str] = None,
                          code: Optional[str] = None) -> Dict:
        """Get information about industry classification codes.
        
        Args:
            code_scheme_id: Optional specific code scheme (e.g. 'uk_sic_2007')
            code: Optional specific code within the scheme
        """
        if code_scheme_id and code:
            endpoint = f'industry_codes/{code_scheme_id}/{code}'
        elif code_scheme_id:
            endpoint = f'industry_codes/{code_scheme_id}'
        else:
            endpoint = 'industry_codes'
        return self._make_request(endpoint)

    async def analyze_company_network(self, company_data: Dict) -> str:
        """Analyze company network data using Gemini."""
        network_data = self.search_company_network(
            company_data['jurisdiction_code'],
            company_data['company_number']
        )
        
        prompt = f"""Analyze this company network data and provide insights about:
1. Corporate structure
2. Key relationships
3. Ownership patterns
4. Potential red flags

Data to analyze:
{network_data}

Format the response as a clear report with sections and bullet points."""

        return generate_with_retry(prompt, temperature=0.3)

def format_company_info(company_data: Dict, api: OpenCorporatesAPI) -> str:
    """Format company information with AI-enhanced analysis."""
    try:
        output = []
        company = company_data.get('company', {})
        
        # Basic company info
        output.append(f"Company Name: {company.get('name', 'Not specified')}")
        output.append(f"Company Number: {company.get('company_number', 'Not specified')}")
        output.append(f"Jurisdiction: {company.get('jurisdiction_code', 'Not specified').upper()}")
        output.append(f"Status: {company.get('current_status', 'Not specified')}")
        
        # Incorporation date
        if company.get('incorporation_date'):
            output.append(f"Incorporated: {company['incorporation_date']}")
        
        # Address
        if company.get('registered_address_in_full'):
            output.append(f"Registered Address: {company['registered_address_in_full']}")
        
        # Get officers/directors using OpenCorporates officers endpoint
        try:
            jurisdiction = company.get('jurisdiction_code')
            company_number = company.get('company_number')
            if jurisdiction and company_number:
                # First try to get officers directly
                officers_results = api.search_officers(
                    jurisdiction_code=jurisdiction,
                    position="director",
                    inactive=False
                )
                
                current_directors = []
                if officers_results and 'results' in officers_results and 'officers' in officers_results['results']:
                    for officer in officers_results['results']['officers']:
                        officer_info = officer.get('officer', {})
                        if (officer_info.get('company_number') == company_number and 
                            not officer_info.get('end_date')):  # Only include active directors
                            current_directors.append({
                                'name': officer_info.get('name'),
                                'position': officer_info.get('position'),
                                'start_date': officer_info.get('start_date')
                            })
                
                if current_directors:
                    output.append("\nCurrent Directors:")
                    for director in current_directors:
                        output.append(f"- {director['name']}")
                        output.append(f"  Position: {director['position']}")
                        if director.get('start_date'):
                            output.append(f"  Appointed: {director['start_date']}")
                else:
                    # Fallback to filings if no directors found through officers search
                    filings = api.get_company_filings(jurisdiction, company_number)
                    if filings and 'results' in filings and 'filings' in filings['results']:
                        current_directors = []
                        for filing in filings['results']['filings']:
                            f_info = filing.get('filing', {})
                            title = f_info.get('title', '').lower()
                            
                            if 'appointment of director' in title:
                                name = f_info.get('description', '').split('Appointment of ')[-1].split(' as')[0]
                                if name and name not in [d['name'] for d in current_directors]:
                                    current_directors.append({
                                        'name': name,
                                        'start_date': f_info.get('date')
                                    })
                            elif 'termination of appointment of director' in title:
                                name = f_info.get('description', '').split('Termination of appointment of ')[-1].split(' as')[0]
                                current_directors = [d for d in current_directors if d['name'] != name]
                        
                        if current_directors:
                            output.append("\nCurrent Directors (from filings):")
                            for director in current_directors:
                                output.append(f"- {director['name']}")
                                if director.get('start_date'):
                                    output.append(f"  Appointed: {director['start_date']}")
                        else:
                            output.append("\nNo current directors found")
        except Exception as e:
            output.append(f"\nError getting directors: {str(e)}")
        
        # Registry URL
        if company.get('registry_url'):
            output.append(f"\nRegistry URL: {company['registry_url']}")
        
        # Add AI analysis of complex data
        if company.get('network_data'):
            network_analysis = generate_with_retry(
                f"""Analyze this corporate network and highlight key relationships:
                {company['network_data']}
                Focus on ownership patterns and potential risk indicators.""",
                temperature=0.3
            )
            if network_analysis:
                output.append("\nNetwork Analysis:")
                output.append(network_analysis)
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error formatting company info: {str(e)}"

def main():
    """Interactive command line interface for OpenCorporates API"""
    api = OpenCorporatesAPI()
    
    while True:
        print("\nOpenCorporates Search")
        print("1. Search Companies")
        print("2. Search Officers (Directors/Executives)")
        print("3. Get Company Details")
        print("4. List Jurisdictions")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            query = input("Enter company name to search: ")
            page = input("Enter page number (default 1): ") or 1
            results = api.search_companies(query=query, page=int(page))
            
            if 'results' in results and 'companies' in results['results']:
                companies = results['results']['companies']
                total = results['results']['total_count']
                print(f"\nFound {total} companies matching '{query}'")
                print("=" * 80)
                
                for company in companies:
                    print(format_company_info(company, api))
            else:
                print("No results found or error in search")
            
        elif choice == '2':
            query = input("Enter officer name to search: ")
            jurisdiction = input("Enter jurisdiction code (optional): ") or None
            results = api.search_officers(query=query, jurisdiction_code=jurisdiction)
            
            if 'results' in results and 'officers' in results['results']:
                officers = results['results']['officers']
                total = results['results']['total_count']
                print(f"\nFound {total} officers matching '{query}'")
                print("=" * 80)
                
                for officer in officers:
                    info = officer['officer']
                    company_name = info.get('company', {}).get('name') if info.get('company') else info.get('company_name', 'Not specified')
                    print(f"""
    Name: {info.get('name', 'Not specified')}
    Position: {info.get('position', 'Not specified')}
    Company: {company_name}
    Company Number: {info.get('company', {}).get('company_number', 'Not specified') if info.get('company') else 'Not specified'}
    Jurisdiction: {info.get('jurisdiction_code', 'Not specified').upper()}
    Start Date: {info.get('start_date', 'Not specified')}
    End Date: {info.get('end_date', 'Not specified')}
    {'=' * 80}
                    """)
            else:
                print("No results found or error in search")
            
        elif choice == '3':
            jurisdiction = input("Enter jurisdiction code (e.g., us_de): ")
            company_number = input("Enter company number: ")
            results = api.get_company_details(jurisdiction, company_number)
            
            if 'results' in results and 'company' in results['results']:
                company = results['results']
                print(format_company_info({'company': company['company']}, api))
            else:
                print("Company not found or error in search")
            
        elif choice == '4':
            results = api.get_jurisdictions()
            if 'results' in results and 'jurisdictions' in results['results']:
                jurisdictions = results['results']['jurisdictions']
                print("\nAvailable Jurisdictions:")
                print("=" * 80)
                for jurisdiction in jurisdictions:
                    info = jurisdiction['jurisdiction']
                    print(f"""
    Code: {info['code']}
    Name: {info['name']}
    Type: {info.get('type', 'Not specified')}
    {'=' * 80}
                    """)
            else:
                print("Error retrieving jurisdictions")
            
        elif choice == '5':
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == '__main__':
    main()