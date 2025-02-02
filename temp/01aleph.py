import requests
import json
from typing import Dict, List, Optional, Set, Tuple, Any, Generator, Mapping, Iterable
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
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
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

def extract_country_filters(query: str) -> Tuple[str, Set[str]]:
    """Extract country filters from query and normalize them"""
    country_pattern = r'\b([a-zA-Z]{2})!'  # Allow both upper and lower case
    country_filters = set()
    
    # Find all country codes with ! operator
    matches = re.finditer(country_pattern, query)  # Remove .lower() to match original case
    for match in matches:
        country_code = match.group(1).lower()  # Convert to lowercase for comparison
        if country_code in COUNTRY_CODES:
            country_filters.add(country_code)
    
    # Remove country filters from query and clean up
    clean_query = re.sub(country_pattern, '', query)
    # Remove any trailing/leading punctuation and normalize spaces
    clean_query = re.sub(r'\s+', ' ', clean_query).strip(' ,.!?')
    return clean_query, country_filters

def format_query_for_api(query: str, enable_regex: bool = False) -> str:
    """Format a query string for the Aleph API with enhanced options"""
    # Remove any existing quotes
    query = query.strip().strip('"\'')
    
    if enable_regex:
        return query  # Return as-is for regex queries
    
    # For multi-word queries, wrap in quotes to ensure exact phrase matching
    if ' ' in query:
        return f'"{query}"'
    
    return query

def matches_country_filter(entity_countries: List[str], country_filters: Set[str]) -> bool:
    """Check if entity matches any of the country filters"""
    if not country_filters:
        return True
        
    if not entity_countries:
        print("  • No country information available")
        return True  # If no country info, include it
        
    entity_countries = [c.lower() for c in entity_countries]
    print(f"  • Checking countries: {entity_countries}")
    
    for filter_code in country_filters:
        valid_codes = COUNTRY_CODES.get(filter_code, [])
        print(f"  • Looking for matches with {filter_code}: {valid_codes}")
        if any(code in entity_countries for code in valid_codes):
            print("  • ✓ Match found!")
            return True
        
    print("  • ✗ No country matches found")
    return False

@dataclass
class AlephEntity:
    """Structured data class for Aleph entities following internal model"""
    id: str
    schema: str
    name: str
    properties: Dict
    datasets: List[Dict]  # Changed from List[str] to List[Dict] to include more metadata
    countries: List[str]
    addresses: List[str]
    links: List[Dict]
    raw_data: Dict
    collection_id: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    fingerprints: Optional[List[str]] = None
    names: Optional[List[str]] = None
    identifiers: Optional[List[str]] = None
    roles: Optional[List[Dict]] = None
    highlights: Optional[Dict[str, List[str]]] = None

    def to_dict(self) -> Dict:
        """Convert entity to dictionary format following Aleph's model"""
        return {
            'id': self.id,
            'schema': self.schema,
            'name': self.name,
            'properties': self.properties,
            'datasets': self.datasets,
            'countries': self.countries,
            'addresses': self.addresses,
            'links': self.links,
            'collection_id': self.collection_id,
            'created_at': self.first_seen,
            'updated_at': self.last_seen,
            'fingerprints': self.fingerprints,
            'names': self.names,
            'identifiers': self.identifiers,
            'roles': self.roles,
            'highlights': self.highlights
        }

    def get_property(self, prop_name: str, default: Any = None) -> Any:
        """Safely get a property value"""
        return self.properties.get(prop_name, default)

    def get_identifier(self, scheme: str = None) -> Optional[str]:
        """Get an identifier by scheme"""
        if not self.identifiers:
            return None
        if scheme:
            for ident in self.identifiers:
                if isinstance(ident, dict) and ident.get('scheme') == scheme:
                    return ident.get('identifier')
        return self.identifiers[0] if self.identifiers else None

    def get_highlighted_text(self, field: str = None) -> List[str]:
        """Get highlighted text snippets"""
        if not self.highlights:
            return []
        # Handle both dict and list formats of highlights
        if isinstance(self.highlights, dict):
            if field:
                return self.highlights.get(field, [])
            return [text for texts in self.highlights.values() for text in texts]
        elif isinstance(self.highlights, list):
            return self.highlights
        return []

class AlephSearchException(Exception):
    """Custom exception class for Aleph API errors"""
    def __init__(self, exc):
        self.exc = exc
        self.response = None
        self.status = None
        self.transient = isinstance(exc, (requests.ConnectionError, requests.Timeout))
        self.message = str(exc)
        
        if hasattr(exc, 'response') and exc.response is not None:
            self.response = exc.response
            self.status = exc.response.status_code
            self.transient = exc.response.status_code >= 500
            try:
                data = exc.response.json()
                self.message = data.get('message')
            except Exception:
                self.message = exc.response.text
    
    def __str__(self):
        return self.message

def backoff(exc: AlephSearchException, attempt: int):
    """Implement exponential backoff"""
    sleep_time = min(2 ** attempt, 120)  # Cap at 120 seconds
    logger.warning(f"Request failed (attempt {attempt}), retrying in {sleep_time}s... Error: {exc}")
    time.sleep(sleep_time)

class APIResultSet:
    def __init__(self, api: "AlephAPI", url: str):
        self.api = api
        self.url = url
        self.current = 0
        self.result = self.api._request("GET", self.url)

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= self.result.get("limit"):
            next_url = self.result.get("next")
            if next_url is None:
                raise StopIteration
            self.result = self.api._request("GET", next_url)
            self.current = 0
        try:
            item = self.result.get("results", [])[self.index]
        except IndexError:
            raise StopIteration
        self.current += 1
        return self._patch(item)

    next = __next__

    def _patch(self, item):
        return item

    @property
    def index(self):
        return self.current - self.result.get("offset", 0)

    def __len__(self):
        return self.result.get("total", 0)

    def __repr__(self):
        return "<APIResultSet(%r, %r)>" % (self.url, len(self))

class EntityResultSet(APIResultSet):
    def __init__(self, api: "AlephAPI", url: str, publisher: bool = False):
        super().__init__(api, url)
        self.publisher = publisher
    
    def _patch(self, item: Dict) -> Dict:
        """Override _patch to add publisher info"""
        return self.api._patch_entity(item, self.publisher)

    def __iter__(self):
        return self

    def __next__(self):
        if self.current >= len(self.result.get("results", [])):
            next_url = self.result.get("next")
            if next_url is None:
                raise StopIteration
            self.result = self.api._request("GET", next_url)
            self.current = 0
        
        item = self.result.get("results", [])[self.current]
        self.current += 1
        return self._patch(item)

class AlephAPI:
    def __init__(self):
        """Initialize Aleph API client"""
        self.base_url = ALEPH_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {ALEPH_API_KEY}',
            'Accept': 'application/json'
        })
        self.seen_entities = set()  # Track processed entities to avoid loops

    def _request(self, method: str, url: str, **kwargs) -> Dict:
        """Make HTTP request with retries and rate limiting"""
        if not url.startswith('http'):
            url = self.base_url + url

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=REQUEST_TIMEOUT,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue

    def _get_paginated_results(self, url: str, params: Dict = None) -> List[Dict]:
        """Get all results from paginated endpoint"""
        all_results = []
        params = params or {}
        params['limit'] = 50

        while True:
            response = self._request('GET', url, params=params)
            results = response.get('results', [])
            if not results:
                break

            all_results.extend(results)
            
            # Check for next page
            next_url = response.get('next')
            if not next_url:
                break
                
            # Update offset for next page
            params['offset'] = params.get('offset', 0) + len(results)

        return all_results

    def get_entity_network(self, entity_id: str, processed_entities: Set = None) -> Dict:
        """Recursively get all connected information for an entity"""
        if processed_entities is None:
            processed_entities = set()

        if entity_id in processed_entities:
            return {}

        processed_entities.add(entity_id)
        network_data = {
            'entity': {},
            'directors': [],
            'owners': [],
            'subsidiaries': [],
            'parent_companies': [],
            'related_entities': [],
            'documents': [],
            'statements': [],
            'references': [],
            'collections': [],
            'profiles': []
        }

        try:
            # 1. Get full entity details
            entity_url = f"entities/{entity_id}"
            entity = self._request("GET", entity_url, params={
                'include': 'properties,schema,names,addresses,countries,identifiers,tags',
                'expand': 'true'
            })
            network_data['entity'] = entity

            # 2. Get directorships
            directorships = self._get_paginated_results("entities", params={
                'filter:schema': 'Directorship',
                'filter:properties.organization': entity_id,
                'include': 'properties'
            })

            # Process directors
            for directorship in directorships:
                if directorship.get('properties', {}).get('director'):
                    director_id = directorship['properties']['director']
                    try:
                        director = self._request("GET", f"entities/{director_id}")
                        if director:
                            director['position'] = directorship.get('properties', {}).get('role', 'Director')
                            director['start_date'] = directorship.get('properties', {}).get('startDate')
                            director['end_date'] = directorship.get('properties', {}).get('endDate')
                            network_data['directors'].append(director)
                    except Exception as e:
                        logger.error(f"Failed to fetch director {director_id}: {str(e)}")

            # 3. Get ownership data
            ownerships = self._get_paginated_results("entities", params={
                'filter:schema': 'Ownership',
                'filter:properties.asset': entity_id,
                'include': 'properties'
            })

            # Process owners
            for ownership in ownerships:
                if ownership.get('properties', {}).get('owner'):
                    owner_id = ownership['properties']['owner']
                    try:
                        owner = self._request("GET", f"entities/{owner_id}")
                        if owner:
                            owner['ownership_percentage'] = ownership.get('properties', {}).get('shareValue')
                            owner['ownership_type'] = ownership.get('properties', {}).get('ownershipType')
                            network_data['owners'].append(owner)
                    except Exception as e:
                        logger.error(f"Failed to fetch owner {owner_id}: {str(e)}")

            # 4. Get adjacent relationships
            adjacent_props = ['directorOf', 'ownerOf', 'parentOf', 'subsidiaryOf', 'memberOf']
            for prop in adjacent_props:
                try:
                    adjacent = self._get_paginated_results(f"entities/{entity_id}/adjacent/{prop}")
                    for adj_entity in adjacent:
                        adj_entity['relationship_type'] = prop
                        network_data['related_entities'].append(adj_entity)
                except Exception as e:
                    logger.error(f"Failed to fetch {prop} relationships: {str(e)}")

            # 5. Get network expansion
            try:
                expanded = self._get_paginated_results(f"entities/{entity_id}/expand")
                network_data['related_entities'].extend(expanded)
            except Exception as e:
                logger.error(f"Failed to expand network: {str(e)}")

            # 6. Get similar entities and references
            try:
                similar = self._get_paginated_results(f"entities/{entity_id}/similar")
                network_data['references'].extend(similar)
            except Exception as e:
                logger.error(f"Failed to get similar entities: {str(e)}")

            # 7. Get statements
            try:
                statements = self._get_paginated_results(f"entities/{entity_id}/statements")
                network_data['statements'] = statements
            except Exception as e:
                logger.error(f"Failed to get statements: {str(e)}")

            # 8. Get profile information
            if entity.get('profile_id'):
                try:
                    profile_data = self.get_complete_profile(entity['profile_id'])
                    network_data['profiles'].append(profile_data)
                except Exception as e:
                    logger.error(f"Failed to get profile data: {str(e)}")

            # 9. Get collection information
            if entity.get('collection_id'):
                try:
                    collection = self._request("GET", f"collections/{entity['collection_id']}")
                    network_data['collections'].append(collection)
                except Exception as e:
                    logger.error(f"Failed to get collection data: {str(e)}")

            # 10. Get associated documents
            try:
                documents = self._get_paginated_results("entities", params={
                    'filter:schema': 'Pages',
                    'filter:properties.mentions': entity_id
                })
                network_data['documents'] = documents
            except Exception as e:
                logger.error(f"Failed to get documents: {str(e)}")

            return network_data

        except Exception as e:
            logger.error(f"Failed to get entity network: {str(e)}")
            return network_data

    def search_entity(self, query: str) -> Dict:
        """Search for an entity and build its complete graph of relationships"""
        try:
            # Initial search with broader schema types
            search_params = {
                "q": query,
                "filter:schema": ["Company", "Organization", "LegalEntity", "Person"],
                "limit": 10,
                "include": "properties,schema,names,addresses,countries,identifiers"
            }
            
            results = self._request("GET", "entities", params=search_params)
            if not results.get('results'):
                search_params.pop('filter:schema')
                results = self._request("GET", "entities", params=search_params)
                
            if not results.get('results'):
                logger.info(f"No results found for query: {query}")
                return {}
                
            entity = results['results'][0]
            entity_id = entity['id']
            schema_type = entity.get('schema')
            
            network_data = {
                'entity': entity,
                'properties': entity.get('properties', {}),
                'identifiers': entity.get('identifiers', []),
                'schema': schema_type,
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

            # Get all relationships based on schema type
            relationship_queries = [
                ("Directorship", "organization", "directors", "director"),
                ("Directorship", "director", "directorships", "organization"),
                ("Membership", "organization", "members", "member"),
                ("Membership", "member", "memberships", "organization"),
                ("Ownership", "asset", "owners", "owner"),
                ("Ownership", "owner", "assets", "asset"),
                ("Associate", "person", "associates", "associate"),
                ("Associate", "associate", "associations", "person")
            ]

            for schema, source_prop, target_type, target_prop in relationship_queries:
                try:
                    params = {
                        "filter:schema": schema,
                        f"filter:properties.{source_prop}": entity_id,
                        "include": "properties"
                    }
                    relationships = self._request("GET", "entities", params=params)
                    
                    for rel in relationships.get('results', []):
                        if 'properties' in rel:
                            target_id = rel['properties'].get(target_prop)
                            if target_id:
                                target_entity = self._request("GET", f"entities/{target_id}")
                                if target_entity:
                                    relationship_data = {
                                        'entity': target_entity,
                                        'role': rel.get('properties', {}).get('role'),
                                        'start_date': rel.get('properties', {}).get('startDate'),
                                        'end_date': rel.get('properties', {}).get('endDate'),
                                        'relationship_type': schema
                                    }
                                    network_data['relationships'][f"{target_type}"].append(relationship_data)
                except Exception as e:
                    logger.error(f"Failed to get {schema} relationships: {str(e)}")

            # Get documents mentioning this entity
            try:
                doc_params = {
                    "filter:entities": entity_id,
                    "limit": 20
                }
                documents = self._request("GET", "documents", params=doc_params)
                network_data['documents'] = documents.get('results', [])
            except Exception as e:
                logger.error(f"Failed to get documents: {str(e)}")

            return network_data
                
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {}

def dict_to_aleph_entity(data: Dict) -> AlephEntity:
    """Convert a dictionary to an AlephEntity object"""
    return AlephEntity(
        id=data.get("id"),
        schema=data.get("schema"),
        name=data.get("caption", data.get("name", "Unknown")),
        properties=data.get("properties", {}),
        countries=data.get("properties", {}).get("countries", []),
        addresses=data.get("properties", {}).get("addresses", []),
        links=data.get("relationships", []),
        raw_data=data,
        collection_id=data.get("collection_id"),
        first_seen=data.get("created_at"),
        last_seen=data.get("updated_at"),
        identifiers=data.get("identifiers", [])
    )

def print_network_info(network: Dict):
    """Print comprehensive network information"""
    if not network:
        print("\n❌ No network information found")
        return

    print("\n" + "="*80)
    print(f"🔍 ENTITY PROFILE ({network.get('schema', 'Unknown type').upper()})")
    print("="*80)
    
    properties = network.get('properties', {})
    
    # Basic Information
    print("\n📋 Basic Information:")
    basic_props = [
        ('name', 'Name'),
        ('registrationNumber', 'Registration Number'),
        ('jurisdiction', 'Jurisdiction'),
        ('incorporationDate', 'Incorporated'),
        ('status', 'Status'),
        ('legalForm', 'Legal Form')
    ]
    for prop, label in basic_props:
        if prop in properties:
            print(f"  • {label}: {properties[prop][0]}")

    # Person-specific information
    if network.get('schema') == 'Person':
        person_props = [
            ('position', 'Position'),
            ('nationality', 'Nationality'),
            ('birthDate', 'Birth Date'),
            ('birthPlace', 'Birth Place')
        ]
        print("\n👤 Personal Details:")
        for prop, label in person_props:
            if prop in properties and properties[prop]:
                print(f"  • {label}: {properties[prop][0]}")

    # Relationships
    relationships = network.get('relationships', {})
    
    if relationships.get('directors'):
        print("\n👥 Directors:")
        for rel in relationships['directors']:
            entity = rel['entity']
            role = rel.get('role', 'Director')
            dates = []
            if rel.get('start_date'):
                dates.append(f"from {rel['start_date']}")
            if rel.get('end_date'):
                dates.append(f"until {rel['end_date']}")
            date_str = f" ({' '.join(dates)})" if dates else ""
            print(f"  • {entity.get('name', 'Unknown')} - {role}{date_str}")

    if relationships.get('members'):
        print("\n🤝 Members:")
        for rel in relationships['members']:
            entity = rel['entity']
            role = rel.get('role', 'Member')
            print(f"  • {entity.get('name', 'Unknown')} - {role}")

    if relationships.get('owners'):
        print("\n💼 Ownership Structure:")
        for rel in relationships['owners']:
            entity = rel['entity']
            print(f"  • Owned by: {entity.get('name', 'Unknown')}")

    if relationships.get('associates'):
        print("\n🔗 Associates:")
        for rel in relationships['associates']:
            entity = rel['entity']
            print(f"  • {entity.get('name', 'Unknown')}")

    # Documents
    if network.get('documents'):
        print("\n📄 Related Documents:")
        for doc in network['documents'][:5]:
            print(f"  • {doc.get('title', 'Untitled')} ({doc.get('schema', 'Unknown type')})")

def main():
    """Interactive CLI for searching entities in the OCCRP Aleph database"""
    try:
        print("\n" + "="*80)
        print("🔍 ALEPH ENTITY SEARCH")
        print("="*80)
        print("\nThis tool will search for an entity and retrieve its complete network")
        print("including directors, owners, related companies, and documents.")
        
        while True:
            query = input("\nEnter search term (or 'quit' to exit): ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋")
                break
                
            if not query:
                print("Please enter a search term")
                continue
            
            print(f"\n🔎 Searching for: {query}")
            print("This may take a while as we gather all connected information...")
            
            api = AlephAPI()
            network = api.search_entity(query)
            
            if not network:
                print("\n❌ No results found")
                continue
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(f"aleph_data/{query.replace(' ', '_')}_{timestamp}")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            results_file = output_dir / "network.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(network, f, indent=2, ensure_ascii=False)
            
            # Print results
            print_network_info(network)
            
            print(f"\n💾 Results saved in: {output_dir}")
            
            search_again = input("\nWould you like to search for another entity? (y/n): ").strip().lower()
            if search_again not in ['y', 'yes']:
                print("\nGoodbye! 👋")
                break
                
    except KeyboardInterrupt:
        print("\n\nSearch interrupted. Goodbye! 👋")
    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    main() 