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
}

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
    country_pattern = r'\b([a-zA-Z]{2})!'
    country_filters = set()
    matches = re.finditer(country_pattern, query)
    for match in matches:
        code = match.group(1).lower()
        if code in COUNTRY_CODES:
            country_filters.add(code)
    clean_query = re.sub(country_pattern, '', query)
    clean_query = re.sub(r'\s+', ' ', clean_query).strip(' ,.!?')
    return clean_query, country_filters

def format_query_for_api(query: str, enable_regex: bool = False) -> str:
    query = query.strip().strip('"\'')
    if enable_regex:
        return query
    if ' ' in query:
        return f'"{query}"'
    return query

def matches_country_filter(entity_countries: List[str], country_filters: Set[str]) -> bool:
    if not country_filters:
        return True
    if not entity_countries:
        print("  • No country information available")
        return True
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
    id: str
    schema: str
    name: str
    properties: Dict
    datasets: List[Dict]
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
        return self.properties.get(prop_name, default)

    def get_identifier(self, scheme: str = None) -> Optional[str]:
        if not self.identifiers:
            return None
        if scheme:
            for ident in self.identifiers:
                if isinstance(ident, dict) and ident.get('scheme') == scheme:
                    return ident.get('identifier')
        return self.identifiers[0] if self.identifiers else None

    def get_highlighted_text(self, field: str = None) -> List[str]:
        if not self.highlights:
            return []
        if isinstance(self.highlights, dict):
            if field:
                return self.highlights.get(field, [])
            return [text for texts in self.highlights.values() for text in texts]
        elif isinstance(self.highlights, list):
            return self.highlights
        return []

class AlephSearchException(Exception):
    def __init__(self, exc):
        self.exc = exc
        self.response = None
        self.status = None
        self.transient = isinstance(exc, (requests.ConnectionError, requests.Timeout))
        self.message = str(exc)
        if hasattr(exc, 'response') and exc.response is not None:
            self.response = exc.response
            self.status = self.response.status_code
            self.transient = self.response.status_code >= 500
            try:
                data = self.response.json()
                self.message = data.get('message')
            except Exception:
                self.message = self.response.text
    def __str__(self):
        return self.message

def backoff(exc: AlephSearchException, attempt: int):
    sleep_time = min(2 ** attempt, 120)
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
        self.base_url = ALEPH_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'ApiKey {ALEPH_API_KEY}',
            'Accept': 'application/json'
        })
        self.seen_entities = set()

    def _request(self, method: str, url: str, **kwargs) -> Dict:
        if not url.startswith('http'):
            url = self.base_url + url
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(RETRY_DELAY * (attempt + 1))
        return {}

    def _get_paginated_results(self, url: str, params: Dict = None) -> List[Dict]:
        all_results = []
        params = params or {}
        params['limit'] = 50
        while True:
            response = self._request('GET', url, params=params)
            results = response.get('results', [])
            if not results:
                break
            all_results.extend(results)
            nxt = response.get('next')
            if not nxt:
                break
            params['offset'] = params.get('offset', 0) + len(results)
        return all_results

    # Helper to handle owners/directors that might be dictionaries or lists
    def _extract_ids(self, val: Any) -> List[str]:
        """
        If `val` is a single string => [val]
        If `val` is a dict => [val["id"]] if present
        If `val` is a list => flatten it
        Otherwise => []
        """
        if not val:
            return []
        if isinstance(val, str):
            return [val]
        if isinstance(val, dict):
            possible_id = val.get("id")
            return [possible_id] if possible_id else []
        if isinstance(val, list):
            out = []
            for x in val:
                out.extend(self._extract_ids(x))
            return out
        return []

    def get_entity_network(self, entity_id: str, processed_entities: Set = None) -> Dict:
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
            entity_url = f"entities/{entity_id}"
            entity = self._request("GET", entity_url, params={
                'include': 'properties,schema,names,addresses,countries,identifiers,tags',
                'expand': 'true'
            })
            network_data['entity'] = entity

            # Directorship
            directorships = self._get_paginated_results("entities", params={
                'filter:schema': 'Directorship',
                'filter:properties.organization': entity_id,
                'include': 'properties'
            })
            for dship in directorships:
                props = dship.get('properties', {})
                # Safely extract director IDs
                for did in self._extract_ids(props.get('director')):
                    try:
                        director = self._request("GET", f"entities/{did}")
                        if director:
                            director['position'] = props.get('role', 'Director')
                            director['start_date'] = props.get('startDate')
                            director['end_date'] = props.get('endDate')
                            network_data['directors'].append(director)
                    except Exception as e:
                        logger.error(f"Failed to fetch director {did}: {str(e)}")

            # Ownership
            ownerships = self._get_paginated_results("entities", params={
                'filter:schema': 'Ownership',
                'filter:properties.asset': entity_id,
                'include': 'properties'
            })
            for own in ownerships:
                props = own.get('properties', {})
                for oid in self._extract_ids(props.get('owner')):
                    try:
                        owner = self._request("GET", f"entities/{oid}")
                        if owner:
                            owner['ownership_percentage'] = props.get('shareValue')
                            owner['ownership_type'] = props.get('ownershipType')
                            network_data['owners'].append(owner)
                    except Exception as e:
                        logger.error(f"Failed to fetch owner {oid}: {str(e)}")

            # Adjacents
            for prop in ['directorOf', 'ownerOf', 'parentOf', 'subsidiaryOf', 'memberOf']:
                try:
                    adj = self._get_paginated_results(f"entities/{entity_id}/adjacent/{prop}")
                    for a in adj:
                        a['relationship_type'] = prop
                        network_data['related_entities'].append(a)
                except Exception as e:
                    logger.error(f"Failed to fetch adjacency for {prop}: {str(e)}")

            # Expand
            try:
                expanded = self._get_paginated_results(f"entities/{entity_id}/expand")
                network_data['related_entities'].extend(expanded)
            except Exception as e:
                logger.error(f"Failed to expand network: {str(e)}")

            # Similar => references
            try:
                similar = self._get_paginated_results(f"entities/{entity_id}/similar")
                network_data['references'].extend(similar)
            except Exception as e:
                logger.error(f"Failed to get similar entities: {str(e)}")

            # Statements
            try:
                stmts = self._get_paginated_results(f"entities/{entity_id}/statements")
                network_data['statements'].extend(stmts)
            except Exception as e:
                logger.error(f"Failed to get statements: {str(e)}")

            # Profile
            if entity.get('profile_id'):
                try:
                    prof_data = self.get_complete_profile(entity['profile_id'])
                    network_data['profiles'].append(prof_data)
                except Exception as e:
                    logger.error(f"Failed to get profile data: {str(e)}")

            # Collection
            if entity.get('collection_id'):
                try:
                    coll = self._request("GET", f"collections/{entity['collection_id']}")
                    if coll:
                        network_data['collections'].append(coll)
                except Exception as e:
                    logger.error(f"Failed to get collection data: {str(e)}")

            # Documents
            try:
                docs = self._get_paginated_results("entities", params={
                    'filter:schema': 'Pages',
                    'filter:properties.mentions': entity_id
                })
                network_data['documents'].extend(docs)
            except Exception as e:
                logger.error(f"Failed to get documents: {str(e)}")

            return network_data

        except Exception as e:
            logger.error(f"Failed to get entity network: {str(e)}")
            return network_data

    def search_entity(self, query: str) -> Dict:
        try:
            search_params = {
                "q": query,
                "filter:schema": "Company",
                "limit": 10
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
            logger.info(f"Found entity: {entity.get('name')} (ID: {entity_id})")

            entity_url = f"entities/{entity_id}"
            full_entity = self._request("GET", entity_url, params={
                'include': 'properties,schema,names,addresses,countries,identifiers,tags',
                'expand': 'true'
            })
            network = self.get_entity_network(entity_id)
            network['entity'] = full_entity
            return network
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {}

    def get_complete_profile(self, profile_id: str) -> Dict:
        data = {
            "profile": {},
            "merged": {},
            "references": [],
            "judgements": []
        }
        try:
            base = self._request("GET", f"profiles/{profile_id}")
            if base:
                data["profile"] = base
            merged = self._request("GET", f"profiles/{profile_id}/merged")
            if merged:
                data["merged"] = merged
            refs = self._get_paginated_results(f"profiles/{profile_id}/references")
            data["references"].extend(refs)
            jdg = self._get_paginated_results(f"profiles/{profile_id}/judgements")
            data["judgements"].extend(jdg)
        except Exception as e:
            logger.error(f"Failed to get profile {profile_id}: {str(e)}")
        return data

    def _patch_entity(self, item: Dict, publisher: bool) -> Dict:
        return item

def dict_to_aleph_entity(data: Dict) -> AlephEntity:
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
        identifiers=data.get("identifiers", []),
        datasets=[],
    )

def print_network_info(network: Dict):
    """Print network information in a structured format (plus raw expansions)."""
    if not network:
        print("\n❌ No network information found")
        return

    print("\n" + "="*80)
    print("🏢 ENTITY DETAILS")
    print("="*80)
    entity = network['entity']
    print(f"Name: {entity.get('name')}")
    print(f"ID: {entity.get('id')}")
    print(f"Schema: {entity.get('schema')}")

    if entity.get('properties'):
        print("\nProperties:")
        for key, value in entity['properties'].items():
            if value:
                print(f"  • {key}: {value}")

    if network['directors']:
        print("\n" + "="*80)
        print("👥 DIRECTORS")
        print("="*80)
        for d in network['directors']:
            print(f"\nName: {d.get('name')}")
            print(f"Position: {d.get('position', 'Director')}")
            if d.get('start_date'):
                print(f"Started: {d['start_date']}")
            if d.get('end_date'):
                print(f"Ended: {d['end_date']}")

    if network['owners']:
        print("\n" + "="*80)
        print("💼 OWNERSHIP")
        print("="*80)
        for o in network['owners']:
            print(f"\nOwner: {o.get('name')}")
            if o.get('ownership_percentage'):
                print(f"Share: {o['ownership_percentage']}%")
            if o.get('ownership_type'):
                print(f"Type: {o['ownership_type']}")

    if network['related_entities']:
        print("\n" + "="*80)
        print("🔗 RELATED ENTITIES (adjacency + expanded)")
        print("="*80)
        for e in network['related_entities']:
            print(f"\nName: {e.get('name')}")
            print(f"Schema: {e.get('schema')}")
            if e.get('relationship_type'):
                print(f"Relationship: {e['relationship_type']}")
            if e.get('properties'):
                print("Properties:")
                for k, v in e['properties'].items():
                    if v:
                        print(f"  • {k}: {v}")

    if network['statements']:
        print("\n" + "="*80)
        print("📜 STATEMENTS")
        print("="*80)
        for s in network['statements']:
            print(f"\nType: {s.get('schema')}")
            if s.get('properties'):
                print("Properties:")
                for k, v in s['properties'].items():
                    if v:
                        print(f"  • {k}: {v}")

    if network['references']:
        print("\n" + "="*80)
        print("🔄 REFERENCES")
        print("="*80)
        for r in network['references']:
            print(f"\nName: {r.get('name')}")
            print(f"Type: {r.get('schema')}")
            if r.get('score'):
                print(f"Match Score: {r['score']}")

    if network['documents']:
        print("\n" + "="*80)
        print("📄 DOCUMENTS")
        print("="*80)
        for doc in network['documents']:
            print(f"\nTitle: {doc.get('title')}")
            if doc.get('schema'):
                print(f"Type: {doc['schema']}")
            if doc.get('properties', {}).get('sourceUrl'):
                print(f"Source: {doc['properties']['sourceUrl']}")

    # EXTRA: Print the raw expansions so you can see all the data from adjacency/expand
    print("\n" + "="*80)
    print("🗂 RAW EXPANSIONS (Full 'related_entities' as-is)")
    print("="*80)
    for i, re_entity in enumerate(network['related_entities'], start=1):
        print(f"\nEntity #{i} RAW:\n{json.dumps(re_entity, indent=2, ensure_ascii=False)}")

@click.command()
def main():
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

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(f"aleph_data/{query.replace(' ', '_')}_{timestamp}")
            output_dir.mkdir(parents=True, exist_ok=True)

            results_file = output_dir / "network.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(network, f, indent=2, ensure_ascii=False)

            print_network_info(network)
            print(f"\n💾 Results saved in: {output_dir}")

            more = input("\nWould you like to search for another entity? (y/n): ").strip().lower()
            if more not in ['y', 'yes']:
                print("\nGoodbye! 👋")
                break

    except KeyboardInterrupt:
        print("\n\nSearch interrupted. Goodbye! 👋")
    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    main()