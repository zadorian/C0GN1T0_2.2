import requests
import json
from typing import Dict, List, Optional, Set, Any, Generator, Mapping, Iterable
from datetime import datetime
from pathlib import Path
import os
from dataclasses import dataclass
import time
import re
import logging
from logging.handlers import RotatingFileHandler
import uuid
from urllib.parse import urljoin, urlencode
from itertools import count
import click

# Constants
VERSION = "3.0.0"
ALEPH_API_KEY = "1c0971afa4804c2aafabb125c79b275e"
ALEPH_BASE_URL = "https://aleph.occrp.org/api/2/"
MAX_RETRIES = 5
RETRY_DELAY = 2
REQUEST_TIMEOUT = 30
MAX_RESULTS_PER_PAGE = 50

# Set up logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "aleph_search.log"

logger = logging.getLogger("aleph_search")
logger.setLevel(logging.INFO)

# File handler for detailed logging
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] %(message)s'))
logger.addHandler(file_handler)

# Console handler for minimal output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

# Country code mapping (add more as needed)
COUNTRY_CODES = {
    'uk': ['gbr', 'gb', 'uk', 'united kingdom', 'britain', 'british', 'england', 'scotland', 'wales', 'northern ireland'],
    'fr': ['fra', 'fr', 'france', 'french'],
    'de': ['deu', 'de', 'germany', 'german'],
    'es': ['esp', 'es', 'spain', 'spanish'],
    'it': ['ita', 'it', 'italy', 'italian'],
    'us': ['usa', 'us', 'united states', 'american'],
    'ca': ['can', 'ca', 'canada', 'canadian'],
    'au': ['aus', 'au', 'australia', 'australian'],
    'nz': ['nzl', 'nz', 'new zealand'],
    'ie': ['irl', 'ie', 'ireland', 'irish'],
    'ch': ['che', 'ch', 'switzerland', 'swiss'],
    # Add more country mappings as needed
}

# Expanded schema types
ENTITY_SCHEMAS = [
    'Company',
    'Person', 
    'Organization',
    'LegalEntity',
    'Asset',
    'Event',
    'Contract',
    'Payment',
    'BankAccount',
    'Vehicle',
    'RealEstate',
    'Directorship',
    'Ownership',
    'Membership'
]

def _categorize_entity(self, entity: Dict, relationships: Dict) -> None:
    """Categorize entity into appropriate relationship category"""
    schema = entity.get('schema', '').lower()
    properties = entity.get('properties', {})
    
    entity_data = {
        'id': entity.get('id'),
        'name': properties.get('name', [entity.get('name', 'Unknown')])[0] if isinstance(properties.get('name'), list) else properties.get('name', entity.get('name', 'Unknown')),
        'schema': entity.get('schema'),
        'properties': properties,
        'dataset': entity.get('dataset'),
        'collection_id': entity.get('collection_id'),
        'identifiers': entity.get('identifiers', []),
        'addresses': properties.get('addresses', []),
        'countries': properties.get('countries', [])
    }
    
    # Add relationship context if available
    if 'mentions' in properties:
        entity_data['relationship_context'] = properties['mentions']
        
    # Add extra details based on schema
    if schema == 'person':
        if dob := properties.get('birthDate'):
            entity_data['birth_date'] = dob
        if nationality := properties.get('nationality'):
            entity_data['nationality'] = nationality
        relationships['related_people'].append(entity_data)
        print(f"✓ Added related person: {entity_data['name']}")
        
    elif any(term in schema for term in ['company', 'organization', 'legalentity']):
        if reg_num := properties.get('registrationNumber'):
            entity_data['registration_number'] = reg_num
        if inc_date := properties.get('incorporationDate'):
            entity_data['incorporation_date'] = inc_date
        if status := properties.get('status'):
            entity_data['status'] = status
        relationships['related_companies'].append(entity_data)
        print(f"✓ Added related company: {entity_data['name']}")
        
    else:
        relationships['other_entities'].append(entity_data)
        print(f"✓ Added other entity: {entity_data['name']} ({schema})")

@dataclass
class AlephEntity:
    """Enhanced entity class with full property support based on FtM model"""
    id: str
    schema: str
    name: str
    properties: Dict
    countries: List[str]
    addresses: List[str]
    identifiers: List[Dict]
    datasets: List[Dict]
    links: Dict
    collection_id: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

class AlephAPI:
    def __init__(self):
        self.base_url = ALEPH_BASE_URL
        self.api_key = ALEPH_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {self.api_key}',
            'Accept': 'application/json',
            'User-Agent': f'AlephSearchClient/{VERSION}'
        })

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Dict:
        """Make request to Aleph API with retry logic"""
        url = urljoin(self.base_url, endpoint)
        retries = 0
        
        while retries < MAX_RETRIES:
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                retries += 1
                if retries == MAX_RETRIES:
                    logger.error(f"Failed request after {MAX_RETRIES} retries: {str(e)}")
                    raise
                time.sleep(RETRY_DELAY)

    def search_entity(self, query: str) -> Dict:
        """Search for an entity and build its complete graph of relationships in real-time"""
        try:
            print("\nInitiating search...")
            params = {
                'q': query,
                'filter:schema': ENTITY_SCHEMAS,
                'limit': MAX_RESULTS_PER_PAGE,
                'include': 'properties,schema,names,addresses,countries,identifiers'
            }
            
            results = self._make_request("entities", params=params)
            if not results.get('results'):
                print("No exact matches, trying broader search...")
                params.pop('filter:schema')
                results = self._make_request("entities", params=params)
                
            if not results.get('results'):
                logger.info(f"No results found for query: {query}")
                print("No results found")
                return {}
                
            entity = results['results'][0]
            entity_id = entity['id']
            schema_type = entity.get('schema')
            
            print(f"\nFound primary entity: {entity.get('properties', {}).get('name', ['Unknown'])[0]}")
            print(f"Type: {schema_type}")
            
            network_data = self._build_network_data(entity)
            self._gather_relationships(entity_id, network_data)
            self._gather_documents(entity_id, network_data)
            self._gather_mentions(entity_id, network_data)
            
            return network_data

        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            print(f"\nError: {str(e)}")
            return {}

    def _build_network_data(self, entity: Dict) -> Dict:
        """Initialize network data structure"""
        network_data = {
            'entity': entity,
            'properties': entity.get('properties', {}),
            'identifiers': entity.get('identifiers', []),
            'schema': entity.get('schema'),
            'relationships': {
                'directorships': [],
                'memberships': [],
                'ownership': [],
                'associates': [],
                'subsidiaries': [],
                'parent_companies': [],
                'related_entities': []
            },
            'documents': [],
            'mentions': []
        }
        
        # Print immediate basic information
        properties = entity.get('properties', {})
        if properties:
            print("\nBasic Information:")
            for key in ['registrationNumber', 'jurisdiction', 'incorporationDate', 'status']:
                if key in properties:
                    print(f"- {key}: {properties[key][0]}")
        
        return network_data

    def get_entity_relationships(self, entity_id: str) -> Dict:
        """Get all relationships for an entity"""
        print("\nGathering relationships...")
        relationships = {
            'directors': [],
            'shareholders': [],
            'subsidiaries': [],
            'members': []
        }
        
        try:
            params = {'filter:entities': entity_id}
            response = self._make_request(f"entities/{entity_id}/relationships", params=params)
            
            for rel in response.get('results', []):
                self._categorize_entity(rel, relationships)
                
            return relationships
        except Exception as e:
            logger.error(f"Failed to get relationships: {str(e)}")
            return relationships

    def get_related_documents(self, entity_id: str) -> List[Dict]:
        """Get documents related to an entity"""
        try:
            params = {'filter:entities': entity_id, 'limit': 10}
            response = self._make_request("documents", params=params)
            return response.get('results', [])
        except Exception as e:
            logger.error(f"Failed to get documents: {str(e)}")
            return []

    def get_mentions(self, entity_id: str) -> List[Dict]:
        """Get mentions of an entity in other records"""
        try:
            params = {'filter:mentions': entity_id, 'limit': 10}
            response = self._make_request("entities", params=params)
            return response.get('results', [])
        except Exception as e:
            logger.error(f"Failed to get mentions: {str(e)}")
            return []

def print_network_info(network: Dict) -> None:
    """Print formatted network information"""
    if not network:
        print("No network information available")
        return

    entity = network.get('entity', {})
    properties = entity.get('properties', {})
    
    print("\nEntity Information:")
    if name := properties.get('name'):
        print(f"Name: {name[0]}")
    if schema := entity.get('schema'):
        print(f"Type: {schema}")
    
    # Print other basic information
    for key in ['registrationNumber', 'jurisdiction', 'incorporationDate', 'status']:
        if key in properties:
            print(f"{key}: {properties[key][0]}")

class EnhancedAlephAPI:
    """Enhanced Aleph API client with comprehensive entity search"""
    
    def __init__(self, api_key: str, base_url: str = "https://aleph.occrp.org/api/2/"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {api_key}',
            'Accept': 'application/json'
        })
        self.seen_entities = set()

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request with retries and proper error handling"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        retries = 3
        
        # Ensure params is a dict
        params = params or {}
        
        # Clean and format the query parameter
        if 'q' in params:
            # Remove special characters and extra whitespace
            query = ' '.join(params['q'].split())
            # Properly encode the query
            params['q'] = query

        for attempt in range(retries):
            try:
                print(f"Making request to: {url}")
                print(f"With parameters: {params}")
                response = self.session.get(url, params=params, timeout=30)
                
                # Handle common error cases
                if response.status_code == 400:
                    print("Error: Invalid query format")
                    return {'results': []}
                elif response.status_code == 403:
                    print("Error: Authentication failed - check your API key")
                    return {'results': []}
                elif response.status_code == 429:
                    print("Rate limit exceeded, waiting before retry...")
                    time.sleep(30)  # Wait 30 seconds before retry
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                print(f"HTTP Error: {str(e)}")
                if attempt == retries - 1:
                    return {'results': []}
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                print("Connection error, retrying...")
                if attempt == retries - 1:
                    return {'results': []}
                time.sleep(2 ** attempt)
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                if attempt == retries - 1:
                    return {'results': []}
                time.sleep(2 ** attempt)

    def get_entity_details(self, entity_id: str) -> Dict:
        """Get complete entity details including all properties"""
        params = {
            'include': 'properties,schema,names,addresses,countries,identifiers,tags,relationships,datasets,collections',
            'expand': 'true'
        }
        return self._make_request(f"entities/{entity_id}", params=params)

    def get_entity_relationships(self, entity_id: str) -> Dict:
        """Get all relationships for an entity using the FtM model"""
        relationships = {
            'directors': [],
            'shareholders': [],
            'subsidiaries': [],
            'memberships': [],
            'ownerships': [],
            'directorships': [],
            'other': []
        }

        # Get relationships where this entity is referenced
        params = {
            'filter:entities': entity_id,
            'filter:schema': 'Directorship',
            'include': 'properties,schema,names,addresses,countries,identifiers',
            'limit': 50
        }
        
        directors = self._make_request("entities", params=params)
        
        # Get ownerships
        ownership_params = {
            'filter:entities': entity_id,
            'filter:schema': 'Ownership',
            'include': 'properties,schema,names,addresses,countries,identifiers',
            'limit': 50
        }
        
        ownerships = self._make_request("entities", params=ownership_params)
        
        # Get memberships
        membership_params = {
            'filter:entities': entity_id,
            'filter:schema': 'Membership',
            'include': 'properties,schema,names,addresses,countries,identifiers',
            'limit': 50
        }
        
        memberships = self._make_request("entities", params=membership_params)
        
        # Process all relationships
        for relation in directors.get('results', []):
            props = relation.get('properties', {})
            if director := props.get('director'):
                relationships['directors'].append({
                    'person': director,
                    'role': props.get('role', 'Director'),
                    'start_date': props.get('startDate'),
                    'end_date': props.get('endDate'),
                    'source': props.get('source'),
                    'summary': props.get('summary')
                })
        
        for relation in ownerships.get('results', []):
            props = relation.get('properties', {})
            if owner := props.get('owner'):
                if owner.get('id') != entity_id:  # This entity is the asset
                    relationships['shareholders'].append({
                        'owner': owner,
                        'percentage': props.get('percentage'),
                        'start_date': props.get('startDate'),
                        'end_date': props.get('endDate'),
                        'source': props.get('source'),
                        'type': props.get('ownershipType')
                    })
            if asset := props.get('asset'):
                if asset.get('id') != entity_id:  # This entity is the owner
                    relationships['subsidiaries'].append({
                        'company': asset,
                        'percentage': props.get('percentage'),
                        'start_date': props.get('startDate'),
                        'end_date': props.get('endDate'),
                        'source': props.get('source')
                    })
        
        for relation in memberships.get('results', []):
            props = relation.get('properties', {})
            if member := props.get('member'):
                relationships['memberships'].append({
                    'member': member,
                    'role': props.get('role'),
                    'start_date': props.get('startDate'),
                    'end_date': props.get('endDate'),
                    'source': props.get('source')
                })

        return relationships

    def get_related_documents(self, entity_id: str) -> List[Dict]:
        """Get all documents mentioning or related to the entity"""
        params = {
            'filter:schema': 'Document',
            'filter:entities': entity_id,
            'include': 'properties,schema,names,addresses,countries,identifiers',
            'limit': 50
        }
        
        documents = []
        while True:
            response = self._make_request("entities", params=params)
            results = response.get('results', [])
            if not results:
                break
                
            documents.extend(results)
            if 'next' not in response:
                break
                
            params['offset'] = params.get('offset', 0) + len(results)
            
        return documents

    def get_mentions(self, entity_id: str) -> List[Dict]:
        """Get all entities mentioning this entity"""
        params = {
            'filter:entities': entity_id,
            'include': 'properties,schema',
            'limit': 50
        }
        
        mentions = []
        while True:
            response = self._make_request("entities", params=params)
            results = response.get('results', [])
            if not results:
                break
                
            mentions.extend(results)
            if 'next' not in response:
                break
                
            params['offset'] = params.get('offset', 0) + len(results)
            
        return mentions

    def get_complete_entity_network(self, entity_id: str, depth: int = 1) -> Dict:
        """Get complete network including all relationships and documents"""
        if entity_id in self.seen_entities or depth < 0:
            return {}
            
        self.seen_entities.add(entity_id)
        
        # Get entity details
        entity = self.get_entity_details(entity_id)
        relationships = self.get_entity_relationships(entity_id)
        documents = self.get_related_documents(entity_id)
        mentions = self.get_mentions(entity_id)
        
        # Recursively get related entities
        if depth > 0:
            # Process directors
            for director in relationships.get('directors', []):
                if person := director.get('person'):
                    if person_id := person.get('id'):
                        director['network'] = self.get_complete_entity_network(person_id, depth - 1)
            
            # Process shareholders
            for shareholder in relationships.get('shareholders', []):
                if owner := shareholder.get('owner'):
                    if owner_id := owner.get('id'):
                        shareholder['network'] = self.get_complete_entity_network(owner_id, depth - 1)
            
            # Process subsidiaries
            for subsidiary in relationships.get('subsidiaries', []):
                if company := subsidiary.get('company'):
                    if company_id := company.get('id'):
                        subsidiary['network'] = self.get_complete_entity_network(company_id, depth - 1)
            
            # Process memberships
            for membership in relationships.get('memberships', []):
                if member := membership.get('member'):
                    if member_id := member.get('id'):
                        membership['network'] = self.get_complete_entity_network(member_id, depth - 1)
        
        network = {
            'entity': entity,
            'relationships': relationships,
            'documents': documents,
            'mentions': mentions,
            'depth': depth
        }
        
        return network

    def search_entities(self, query: str, schema_filter: Optional[str] = None) -> List[Dict]:
        """Enhanced entity search with schema filtering and proper query formatting"""
        # Format query for exact phrase matching if multiple words
        if ' ' in query:
            query = f'"{query}"'
            
        params = {
            'q': query,
            'limit': 50
        }
        
        # Add schema filter if specified
        if schema_filter:
            params['filter:schema'] = schema_filter
        else:
            # Default to searching across common entity types
            params['filter:schemata'] = ['Company', 'Organization', 'LegalEntity']
            
        # Add additional search parameters
        params['filter:collection_id'] = None  # Search across all collections
        params['facet'] = ['schema', 'countries']  # Get faceted results
        
        results = self._make_request("entities", params=params).get('results', [])
        
        if not results:
            # Try alternative search without quotes
            params['q'] = query.strip('"')
            results = self._make_request("entities", params=params).get('results', [])
        
        # Deduplicate results based on registration number
        seen_reg_numbers = set()
        deduplicated_results = []
        
        for result in results:
            reg_number = str(result.get('properties', {}).get('registrationNumber', [None])[0])
            if reg_number not in seen_reg_numbers:
                seen_reg_numbers.add(reg_number)
                deduplicated_results.append(result)
            
        return deduplicated_results

    def format_entity_network(self, network: Dict) -> Dict:
        """Format network data in a structured way"""
        entity = network.get('entity', {})
        properties = entity.get('properties', {})
        
        formatted = {
            'entity': {
                'name': properties.get('name', [entity.get('name', 'Unknown')])[0] if isinstance(properties.get('name'), list) else properties.get('name', entity.get('name', 'Unknown')),
                'schema': entity.get('schema'),
                'registration_number': properties.get('registrationNumber', []),
                'incorporation_date': properties.get('incorporationDate', []),
                'status': properties.get('status', []),
                'jurisdiction': properties.get('jurisdiction', []),
                'addresses': properties.get('addresses', []),
                'countries': properties.get('countries', []),
                'previous_names': properties.get('previousNames', []),
                'website': properties.get('website', []),
                'email': properties.get('email', []),
                'phone': properties.get('phone', []),
                'source_url': properties.get('sourceUrl', [])
            },
            'relationships': {
                'directors': network.get('relationships', {}).get('directors', []),
                'shareholders': network.get('relationships', {}).get('shareholders', []),
                'subsidiaries': network.get('relationships', {}).get('subsidiaries', []),
                'memberships': network.get('relationships', {}).get('memberships', []),
                'other': network.get('relationships', {}).get('other', [])
            },
            'documents': network.get('documents', []),
            'mentions': network.get('mentions', []),
            'datasets': entity.get('datasets', []),
            'collections': entity.get('collections', []),
            'timestamp': datetime.now().isoformat()
        }
        
        return formatted

def main():
    api = EnhancedAlephAPI(ALEPH_API_KEY)
    
    try:
        query = input("Enter search query: ").strip()
        if not query:
            print("Please enter a search query")
            return
            
        print(f"\nSearching for: {query}")
        print("This may take a moment...\n")
        
        # Try exact phrase first
        results = api.search_entities(query)
        
        if not results:
            # Try with company schema filter
            print("Trying company-specific search...")
            results = api.search_entities(query, schema_filter='Company')
            
        if not results:
            print("No results found. Trying broader search...")
            # Try broader search
            broader_query = query.replace(' Limited', '').replace(' Ltd', '').replace(' LLC', '')
            results = api.search_entities(broader_query)
            
        if not results:
            print("\nNo results found.")
            return
            
        print(f"\nFound {len(results)} matching entities")
        for idx, result in enumerate(results[:5], 1):
            props = result.get('properties', {})
            name = props.get('name', [result.get('name', 'Unknown')])[0] if isinstance(props.get('name'), list) else props.get('name', result.get('name', 'Unknown'))
            print(f"\n{idx}. {name} ({result.get('schema')})")
            print(f"   ID: {result.get('id')}")
            print(f"   Collection: {result.get('collection_id')}")
            print(f"   Dataset: {result.get('dataset')}")
            
            if countries := props.get('countries', []):
                print(f"   Countries: {', '.join(countries)}")
            if reg_num := props.get('registrationNumber', []):
                print(f"   Registration: {', '.join(str(i) for i in reg_num)}")
            if inc_date := props.get('incorporationDate', []):
                print(f"   Incorporation Date: {', '.join(str(d) for d in inc_date)}")
            if status := props.get('status', []):
                print(f"   Status: {', '.join(status)}")
            if addresses := props.get('addresses', []):
                print(f"   Addresses: {', '.join(str(a) for a in addresses)}")
            if website := props.get('website', []):
                print(f"   Website: {', '.join(website)}")
            if jurisdiction := props.get('jurisdiction', []):
                print(f"   Jurisdiction: {', '.join(jurisdiction)}")
        
        if len(results) > 0:
            selected = 0
            if len(results) > 1:
                while True:
                    try:
                        selected = int(input("\nSelect entity number to analyze (1-5): ")) - 1
                        if 0 <= selected < min(len(results), 5):
                            break
                        print("Please enter a valid number")
                    except ValueError:
                        print("Please enter a valid number")
            
            entity_id = results[selected]['id']
            entity_name = results[selected].get('properties', {}).get('name', [results[selected].get('name', 'Unknown Entity')])[0]
            
            print(f"\nGetting complete network for: {entity_name}")
            print("This may take a few moments...\n")
            
            # Get network with depth=2 for more comprehensive data
            network = api.get_complete_entity_network(entity_id, depth=2)
            formatted = api.format_entity_network(network)
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"entity_network_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(formatted, f, indent=2)
            
            print("\nNetwork Analysis:")
            print(f"Entity: {formatted['entity']['name']}")
            print(f"Type: {formatted['entity']['schema']}")
            
            if reg := formatted['entity']['registration_number']:
                print(f"Registration Number: {', '.join(str(r) for r in reg)}")
            if inc := formatted['entity']['incorporation_date']:
                print(f"Incorporation Date: {', '.join(str(d) for d in inc)}")
            if status := formatted['entity']['status']:
                print(f"Status: {', '.join(status)}")
            if jurisdiction := formatted['entity']['jurisdiction']:
                print(f"Jurisdiction: {', '.join(jurisdiction)}")
            if addresses := formatted['entity']['addresses']:
                print(f"Addresses: {', '.join(str(a) for a in addresses)}")
            if website := formatted['entity']['website']:
                print(f"Website: {', '.join(website)}")
            if email := formatted['entity']['email']:
                print(f"Email: {', '.join(email)}")
            if phone := formatted['entity']['phone']:
                print(f"Phone: {', '.join(phone)}")
            
            print("\nRelationships:")
            if directors := formatted['relationships']['directors']:
                print("\nDirectors:")
                for d in directors:
                    print(f"- {d['person'].get('name', 'Unknown')} ({d.get('role', 'Director')})")
                    if d.get('start_date'):
                        print(f"  From: {d['start_date']}")
                    if d.get('end_date'):
                        print(f"  To: {d['end_date']}")
                    if network := d.get('network', {}):
                        if other_roles := network.get('relationships', {}).get('directorships', []):
                            print("  Other Directorships:")
                            for role in other_roles:
                                print(f"  - {role.get('organization', {}).get('name', 'Unknown Company')}")
            
            if shareholders := formatted['relationships']['shareholders']:
                print("\nShareholders:")
                for s in shareholders:
                    print(f"- {s['owner'].get('name', 'Unknown')} ({s.get('percentage', 'Unknown')}%)")
                    if s.get('type'):
                        print(f"  Type: {s['type']}")
                    if network := s.get('network', {}):
                        if other_holdings := network.get('relationships', {}).get('subsidiaries', []):
                            print("  Other Holdings:")
                            for holding in other_holdings:
                                print(f"  - {holding.get('company', {}).get('name', 'Unknown Company')} ({holding.get('percentage', 'Unknown')}%)")
            
            if subsidiaries := formatted['relationships']['subsidiaries']:
                print("\nSubsidiaries/Investments:")
                for s in subsidiaries:
                    print(f"- {s['company'].get('name', 'Unknown')} ({s.get('percentage', 'Unknown')}%)")
                    if network := s.get('network', {}):
                        if sub_subsidiaries := network.get('relationships', {}).get('subsidiaries', []):
                            print("  Sub-subsidiaries:")
                            for sub in sub_subsidiaries:
                                print(f"  - {sub.get('company', {}).get('name', 'Unknown Company')} ({sub.get('percentage', 'Unknown')}%)")
            
            if docs := formatted['documents']:
                print(f"\nRelated Documents: {len(docs)}")
                for doc in docs[:5]:  # Show first 5 documents
                    if title := doc.get('properties', {}).get('title', []):
                        print(f"- {title[0]}")
            
            if mentions := formatted['mentions']:
                print(f"\nMentions in other entities: {len(mentions)}")
                for mention in mentions[:5]:  # Show first 5 mentions
                    if name := mention.get('properties', {}).get('name', []):
                        print(f"- {name[0]} ({mention.get('schema', 'Unknown Type')})")
            
            if datasets := formatted.get('datasets', []):
                print("\nData Sources:")
                for ds in datasets:
                    print(f"- {ds.get('label', 'Unknown Dataset')}")
            
            print(f"\nDetailed results saved to: {filename}")
            
    except KeyboardInterrupt:
        print("\nSearch cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        logging.exception("Error during search")

if __name__ == "__main__":
    main()