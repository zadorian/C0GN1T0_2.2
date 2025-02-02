import scrapy
from scrapy.spiders import Spider
from scrapy.http import Request
import json
from typing import Dict, List, Generator
from datetime import datetime

class AlephSpider(Spider):
    name = 'aleph_spider'
    allowed_domains = ['aleph.occrp.org']
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)',
        'ROBOTSTXT_OBEY': False,
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': False
    }

    def __init__(self, entity_id=None, api_key=None, *args, **kwargs):
        super(AlephSpider, self).__init__(*args, **kwargs)
        self.entity_id = entity_id
        self.api_key = api_key
        self.base_url = 'https://aleph.occrp.org/api/2'
        self.headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Accept': 'application/json'
        }
        self.data = {
            'entity': {},
            'relationships': {
                'directors': [],
                'shareholders': [],
                'subsidiaries': [],
                'memberships': [],
                'other': []
            },
            'documents': [],
            'mentions': [],
            'adjacent_entities': [],
            'network': {}
        }

    def start_requests(self) -> Generator[Request, None, None]:
        """Start the crawling process with the entity details"""
        if not self.entity_id:
            return

        # Get main entity details
        yield Request(
            url=f'{self.base_url}/entities/{self.entity_id}',
            headers=self.headers,
            callback=self.parse_entity,
            meta={'include': 'properties,schema,names,addresses,countries,identifiers,tags,relationships,datasets,collections'}
        )

        # Get relationships where entity is referenced
        yield Request(
            url=f'{self.base_url}/entities',
            headers=self.headers,
            callback=self.parse_relationships,
            meta={
                'params': {
                    'filter:properties.organization.id': self.entity_id,
                    'filter:schemata': ['Directorship', 'Ownership', 'Membership'],
                    'include': 'properties,schema,names,addresses,countries,identifiers',
                    'limit': 50
                }
            }
        )

        # Get relationships where entity is owner
        yield Request(
            url=f'{self.base_url}/entities',
            headers=self.headers,
            callback=self.parse_relationships,
            meta={
                'params': {
                    'filter:properties.owner.id': self.entity_id,
                    'filter:schemata': ['Ownership'],
                    'include': 'properties,schema,names,addresses,countries,identifiers',
                    'limit': 50
                }
            }
        )

        # Get related documents
        yield Request(
            url=f'{self.base_url}/entities',
            headers=self.headers,
            callback=self.parse_documents,
            meta={
                'params': {
                    'filter:schema': 'Document',
                    'filter:properties.mentions': self.entity_id,
                    'include': 'properties,schema,names,addresses,countries,identifiers',
                    'limit': 50
                }
            }
        )

        # Get mentions
        yield Request(
            url=f'{self.base_url}/entities',
            headers=self.headers,
            callback=self.parse_mentions,
            meta={
                'params': {
                    'filter:properties.mentions': self.entity_id,
                    'include': 'properties,schema',
                    'limit': 50
                }
            }
        )

    def parse_entity(self, response: scrapy.http.Response) -> None:
        """Parse the main entity details"""
        data = json.loads(response.text)
        self.data['entity'] = data
        
        # Extract adjacent entities from properties
        properties = data.get('properties', {})
        for prop_value in properties.values():
            if isinstance(prop_value, list):
                for item in prop_value:
                    if isinstance(item, dict) and 'id' in item:
                        yield Request(
                            url=f'{self.base_url}/entities/{item["id"]}',
                            headers=self.headers,
                            callback=self.parse_adjacent_entity,
                            meta={'include': 'properties,schema'}
                        )

    def parse_relationships(self, response: scrapy.http.Response) -> None:
        """Parse relationship data"""
        data = json.loads(response.text)
        for relation in data.get('results', []):
            schema = relation.get('schema', '').lower()
            props = relation.get('properties', {})
            
            if schema == 'directorship':
                if director := props.get('director'):
                    self.data['relationships']['directors'].append({
                        'person': director,
                        'role': props.get('role', 'Director'),
                        'start_date': props.get('startDate'),
                        'end_date': props.get('endDate'),
                        'source': props.get('source'),
                        'summary': props.get('summary')
                    })
                    # Crawl director details
                    yield Request(
                        url=f'{self.base_url}/entities/{director["id"]}',
                        headers=self.headers,
                        callback=self.parse_adjacent_entity,
                        meta={'include': 'properties,schema'}
                    )
            elif schema == 'ownership':
                self._process_ownership(relation)
            elif schema == 'membership':
                if member := props.get('member'):
                    self.data['relationships']['memberships'].append({
                        'member': member,
                        'role': props.get('role'),
                        'start_date': props.get('startDate'),
                        'end_date': props.get('endDate'),
                        'source': props.get('source')
                    })
            else:
                self.data['relationships']['other'].append({
                    'type': schema,
                    'properties': props,
                    'id': relation.get('id')
                })

    def _process_ownership(self, relation: Dict) -> None:
        """Process ownership relationships"""
        props = relation.get('properties', {})
        if owner := props.get('owner'):
            if owner.get('id') != self.entity_id:
                self.data['relationships']['shareholders'].append({
                    'owner': owner,
                    'percentage': props.get('percentage'),
                    'start_date': props.get('startDate'),
                    'end_date': props.get('endDate'),
                    'source': props.get('source'),
                    'type': props.get('ownershipType')
                })
        if asset := props.get('asset'):
            if asset.get('id') != self.entity_id:
                self.data['relationships']['subsidiaries'].append({
                    'company': asset,
                    'percentage': props.get('percentage'),
                    'start_date': props.get('startDate'),
                    'end_date': props.get('endDate'),
                    'source': props.get('source')
                })

    def parse_documents(self, response: scrapy.http.Response) -> None:
        """Parse related documents"""
        data = json.loads(response.text)
        self.data['documents'].extend(data.get('results', []))

    def parse_mentions(self, response: scrapy.http.Response) -> None:
        """Parse entity mentions"""
        data = json.loads(response.text)
        self.data['mentions'].extend(data.get('results', []))

    def parse_adjacent_entity(self, response: scrapy.http.Response) -> None:
        """Parse adjacent entity details"""
        data = json.loads(response.text)
        self.data['adjacent_entities'].append(data)

    def closed(self, reason: str) -> None:
        """Save the collected data when spider closes"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"aleph_network_{self.entity_id}_{timestamp}.json"
        
        # Process network data
        self.data['network'] = self._process_network()
        
        with open(filename, 'w') as f:
            json.dump(self.data, f, indent=2)
        print(f"\nDetailed network data saved to: {filename}")

    def _process_network(self) -> Dict:
        """Process collected data into a network structure"""
        network = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'entity_id': self.entity_id,
                'timestamp': datetime.now().isoformat(),
                'total_relationships': len(self.data['relationships']['directors']) + 
                                    len(self.data['relationships']['shareholders']) +
                                    len(self.data['relationships']['subsidiaries']) +
                                    len(self.data['relationships']['memberships']),
                'total_documents': len(self.data['documents']),
                'total_mentions': len(self.data['mentions']),
                'total_adjacent_entities': len(self.data['adjacent_entities'])
            }
        }

        # Add main entity as node
        network['nodes'].append({
            'id': self.entity_id,
            'type': 'main_entity',
            'data': self.data['entity']
        })

        # Add relationship nodes and edges
        self._add_relationship_nodes(network)
        
        return network

    def _add_relationship_nodes(self, network: Dict) -> None:
        """Add nodes and edges for relationships"""
        for director in self.data['relationships']['directors']:
            if person := director.get('person'):
                network['nodes'].append({
                    'id': person['id'],
                    'type': 'director',
                    'data': person
                })
                network['edges'].append({
                    'source': person['id'],
                    'target': self.entity_id,
                    'type': 'directorship',
                    'data': director
                })

        for shareholder in self.data['relationships']['shareholders']:
            if owner := shareholder.get('owner'):
                network['nodes'].append({
                    'id': owner['id'],
                    'type': 'shareholder',
                    'data': owner
                })
                network['edges'].append({
                    'source': owner['id'],
                    'target': self.entity_id,
                    'type': 'ownership',
                    'data': shareholder
                })

        for subsidiary in self.data['relationships']['subsidiaries']:
            if company := subsidiary.get('company'):
                network['nodes'].append({
                    'id': company['id'],
                    'type': 'subsidiary',
                    'data': company
                })
                network['edges'].append({
                    'source': self.entity_id,
                    'target': company['id'],
                    'type': 'ownership',
                    'data': subsidiary
                }) 