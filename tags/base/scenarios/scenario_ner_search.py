from typing import Dict, List, Optional, Tuple
from datetime import datetime
import traceback
import re
import logging
from collections import defaultdict
from pathlib import Path
import sys
import json

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

# Import tag classes using absolute imports
from tags.base.query_tag import QueryTag
from tags.base.source_tag import SourceTag 
from tags.base.entity_tag import EntityTag
from tags.base.edge_rules import create_query_result_edge, create_source_edge

# Import tag indexer with proper path
try:
    from indexing.tag_indexing.tag_indexer import TagIndexer
    logger.info("Successfully imported TagIndexer")
    HAS_INDEXER = True
except ImportError:
    logger.warning("Tag indexer not available - tags will not be indexed")
    HAS_INDEXER = False

class NERSearchScenario:
    """
    Handles NER-based website searches like 'p :example.com?' (persons)
    NER types: p (persons), @ (emails), t (phones), l (locations), c (companies)
    """
    
    def __init__(self):
        try:
            # Set up tags directory in root
            self.tags_dir = project_root / 'tags'
            self.tags_dir.mkdir(exist_ok=True)
            
            # Create tags.json if it doesn't exist
            self.tags_file = self.tags_dir / 'tags.json'
            if not self.tags_file.exists():
                self.tags_file.write_text('[]')
                logger.info(f"Created empty tags file at: {self.tags_file}")
            
            logger.info(f"Tags directory: {self.tags_dir}")
            logger.info(f"Tags file: {self.tags_file}")
            
            # Initialize tag handlers with correct path
            self.query_tag = QueryTag(tags_dir=self.tags_dir)
            self.source_tag = SourceTag(tags_dir=self.tags_dir)
            self.entity_tag = EntityTag(tags_dir=self.tags_dir)
            
            # Initialize tag indexer if available
            self.tag_indexer = TagIndexer(
                str(project_root / 'indexing' / 'tag_indexing' / 'index')
            ) if HAS_INDEXER else None
            
            # Map NER types to full names and descriptions
            self.ner_types = {
                'p': {'type': 'PERSON', 'desc': 'Person entity'},
                '@': {'type': 'EMAIL', 'desc': 'Email address'},
                't': {'type': 'PHONE', 'desc': 'Phone number'},
                'l': {'type': 'LOCATION', 'desc': 'Location entity'},
                'c': {'type': 'COMPANY', 'desc': 'Company entity'}
            }
            
            # Track statistics
            self.stats = defaultdict(int)
            
            logger.info("NER Search Scenario initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing NER scenario: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _validate_input(self, ner_type: str, domain: str, results: List[Dict]) -> Tuple[bool, str]:
        """Validate input parameters"""
        if not ner_type or ner_type not in self.ner_types:
            return False, f"Invalid NER type: {ner_type}"
        if not domain:
            return False, "Domain cannot be empty"
        if not results:
            return False, "No results provided"
        return True, ""

    def _deduplicate_entities(self, results: List[Dict]) -> List[Dict]:
        """Deduplicate entities while preserving URL context"""
        seen_entities = {}
        deduplicated = []
        
        for result in results:
            entity = result['entity']
            if entity not in seen_entities:
                seen_entities[entity] = result
                deduplicated.append(result)
            else:
                # Merge URL context if entity already exists
                existing = seen_entities[entity]
                if result['url'] not in existing.get('urls', []):
                    existing.setdefault('urls', []).append(result['url'])
        
        return deduplicated

    def _generate_query_notes(self, ner_type: str, domain: str, timestamp: datetime, results_count: int) -> List[str]:
        """Generate notes for query tag"""
        type_desc = self.ner_types[ner_type]['desc']
        return [
            f"NER search for {type_desc}s on {domain}",
            f"Search performed at {timestamp.isoformat()}",
            f"Found {results_count} unique entities"
        ]

    def _generate_entity_notes(self, entity: str, ner_type: str, domain: str, timestamp: datetime) -> List[str]:
        """Generate notes for entity tag"""
        type_desc = self.ner_types[ner_type]['desc']
        return [
            f"{type_desc} found on {domain}",
            f"First discovered: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Original text: {entity}"
        ]

    def _generate_source_notes(self, url: str, domain: str, timestamp: datetime) -> List[str]:
        """Generate notes for source tag"""
        return [
            f"Web page from domain: {domain}",
            f"First crawled: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Source URL: {url}"
        ]

    async def process(self, ner_type: str, domain: str, results: List[Dict], search_type: str = None) -> List[Dict]:
        """Process NER entities and create entity tags asynchronously"""
        try:
            logger.info(f"\nProcessing NER results for {domain}")
            logger.info(f"NER type: {ner_type}")
            logger.info(f"Results count: {len(results)}")
            
            # Validate input
            is_valid, error_msg = self._validate_input(ner_type, domain, results)
            if not is_valid:
                logger.error(f"Validation failed: {error_msg}")
                return []

            # Initialize tracking
            start_time = datetime.now()
            self.stats.clear()
            
            # Deduplicate entities
            results = self._deduplicate_entities(results)
            logger.info(f"Deduplicated to {len(results)} unique entities")
            
            tags_to_save = []
            
            # Create query tag first
            logger.info("Creating query tag...")
            query_type = 'PageNERHistoric' if search_type == 'historic' else 'PageNERCurrent'
            query_notes = self._generate_query_notes(ner_type, domain, start_time, len(results))
            
            query_tag = await self.query_tag.create(
                name=f"{ner_type} :{domain}",
                query_type=query_type,
                notes=query_notes
            )
            
            if query_tag:
                tags_to_save.append(query_tag)
                logger.info("Query tag created successfully")

            # Create source tags for each unique URL
            logger.info("Creating source tags...")
            source_tags = {}
            for result in results:
                url = result['url']
                if url not in source_tags:
                    source_tag = await self.source_tag.create(
                        url=url,
                        type_='WebPage',
                        notes=self._generate_source_notes(url, domain, start_time)
                    )
                    if source_tag:
                        source_tag['variations'] = None
                        source_tags[url] = source_tag
                        tags_to_save.append(source_tag)
                        
                        # Connect source tag to query tag
                        edge_id = create_query_result_edge(query_tag, source_tag)
                        logger.info(f"Created edge between query and source: {edge_id}")

            # Create entity tags - one for each unique entity
            logger.info("Creating entity tags...")
            seen_entities = set()
            entity_tags = []

            logger.info(f"Processing {len(results)} results for entity creation")
            for result in results:
                url = result['url']
                entity = result['entity']
                
                logger.info(f"Processing entity: {entity} from URL: {url}")
                
                # Skip if we've already created a tag for this entity
                if entity in seen_entities:
                    logger.info(f"Skipping duplicate entity: {entity}")
                    continue
                
                seen_entities.add(entity)
                logger.info(f"Creating new entity tag for: {entity}")
                
                # Create entity tag
                entity_tag = await self.entity_tag.create(
                    name=entity,
                    entity_type=self.ner_types[ner_type]['type'],
                    notes=self._generate_entity_notes(entity, ner_type, domain, start_time)
                )
                
                if entity_tag:
                    logger.info(f"Successfully created tag for: {entity}")
                    entity_tags.append(entity_tag)
                    tags_to_save.append(entity_tag)
                    
                    # Connect entity to query tag
                    query_edge = create_query_result_edge(query_tag, entity_tag)
                    logger.info(f"Created edge between query and entity: {query_edge}")
                    
                    # Connect entity to its source tag
                    source_tag = source_tags.get(url)
                    if source_tag:
                        source_edge = create_source_edge(entity_tag, source_tag)
                        logger.info(f"Created edge between entity and source: {source_edge}")
                else:
                    logger.error(f"Failed to create tag for: {entity}")

            # Log what we're about to save
            logger.info(f"Preparing to save tags:")
            logger.info(f"- Total tags to save: {len(tags_to_save)}")
            logger.info(f"- Entity tags created: {len(entity_tags)}")
            for tag in tags_to_save:
                logger.info(f"- Tag: {tag['name']} ({tag['class_']}/{tag['type_']})")

            # Save ALL tags at once
            if tags_to_save:
                try:
                    logger.info(f"Saving {len(tags_to_save)} tags...")
                    saved = self.entity_tag.save_tags(tags_to_save)
                    logger.info(f"Save operation result: {saved}")
                    
                    if self.tag_indexer and HAS_INDEXER:
                        try:
                            self.tag_indexer.index_tags(tags_to_save)
                            logger.info(f"Indexed {len(tags_to_save)} new tags")
                        except Exception as e:
                            logger.error(f"Error indexing tags: {str(e)}")
                            
                except Exception as e:
                    logger.error(f"Error saving tags: {str(e)}")
            
            return entity_tags
            
        except Exception as e:
            logger.error(f"Error in async entity processing: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def get_statistics(self) -> Dict:
        """Return current processing statistics"""
        return dict(self.stats) 