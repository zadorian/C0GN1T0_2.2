from datetime import datetime
from typing import Dict, List, Optional, Union
from pathlib import Path
import json
from Tags.tag_indexer import TagIndexer
from .edge_rules import EDGE_TYPES
import traceback
import logging

logger = logging.getLogger(__name__)

class BaseTag:
    """Base class for all tags with enforced structure"""
    
    def __init__(self, tags_dir: Optional[Union[str, Path]] = None):
        """Initialize BaseTag with optional custom tags directory"""
        if tags_dir:
            self.tags_dir = Path(tags_dir)
        else:
            self.tags_dir = Path(__file__).parent.parent / "tags"
            
        # Create tags directory if it doesn't exist
        self.tags_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up tags file path
        self.tags_file = self.tags_dir / "tags.json"
        
        # Create empty tags file if it doesn't exist
        if not self.tags_file.exists():
            self.tags_file.write_text('[]')
            logger.info(f"Created empty tags file at: {self.tags_file}")
        
        logger.info(f"Tags will be stored in: {self.tags_file}")

    def load_tags(self) -> List[Dict]:
        """Load tags from flat list structure"""
        try:
            if self.tags_file.exists():
                content = self.tags_file.read_text()
                if not content:
                    logger.warning("Tags file exists but is empty")
                    return []
                    
                try:
                    tags = json.loads(content)
                    # Always ensure we return a list
                    if isinstance(tags, dict):
                        # Convert old format to new
                        logger.warning("Converting old dict format to list format")
                        return []
                    return tags if isinstance(tags, list) else []
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding tags file: {str(e)}")
                    return []
            return []
        except Exception as e:
            logger.error(f"Error loading tags: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def save_tags(self, tags: List[Dict]) -> bool:
        """Save multiple tags to the flat list structure"""
        try:
            # Load existing tags
            existing_tags = self.load_tags()
            if existing_tags is None:
                existing_tags = []
            
            # Track stats
            updated_count = 0
            added_count = 0
            
            # Process each new tag
            for new_tag in tags:
                if not new_tag or 'id_' not in new_tag:
                    logger.error(f"Invalid tag structure: {new_tag}")
                    continue
                    
                # Check if tag already exists
                existing_idx = None
                for idx, existing_tag in enumerate(existing_tags):
                    if existing_tag.get('id_') == new_tag['id_']:
                        existing_idx = idx
                        break
                
                # Update or append
                if existing_idx is not None:
                    existing_tags[existing_idx] = new_tag
                    updated_count += 1
                else:
                    existing_tags.append(new_tag)
                    added_count += 1
            
            # Write back ALL tags as a flat list
            try:
                self.tags_file.write_text(json.dumps(existing_tags, indent=2))
                logger.info(f"Successfully saved tags - Updated: {updated_count}, Added: {added_count}, Total: {len(existing_tags)}")
                
                # Verify the file was written
                if self.tags_file.exists():
                    content = self.tags_file.read_text()
                    if content:
                        saved_tags = json.loads(content)
                        if len(saved_tags) == len(existing_tags):
                            logger.info("Tags file verified successfully")
                        else:
                            logger.error(f"Tag count mismatch after save - Expected: {len(existing_tags)}, Found: {len(saved_tags)}")
                    else:
                        logger.error("Tags file exists but is empty after save")
                else:
                    logger.error("Tags file does not exist after save attempt")
            except Exception as e:
                logger.error(f"Error writing tags file: {str(e)}")
                logger.error(traceback.format_exc())
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in save_tags(): {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def create_base_tag(self, name: str, class_type: str, sub_type: str, variations: List[str] = None, notes: List[str] = None, note: str = "") -> Dict:
        """Create a tag with enforced standard structure"""
        try:
            # Generate ID based on class, type and name
            tag_id = self._generate_id(class_type, sub_type, name)
            
            # Create timestamp
            timestamp = datetime.now().isoformat()
            
            # Ensure variations list exists
            if not variations:
                variations = [name]
                
            # Handle notes - simple string list
            if note and not notes:
                notes = [note]
            elif not notes:
                notes = []
                
            # Create tag with enforced structure
            tag = {
                "id_": tag_id,
                "name": {
                    "value": name,
                    "variations": variations,
                    "shortcut": None
                },
                "class_": class_type,
                "type_": sub_type,
                "notes": notes,
                "track": timestamp,
                "edges": []
            }
            
            # Just return the tag - DON'T SAVE IT HERE
            return tag
            
        except Exception as e:
            logger.error(f"Error creating base tag: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def _generate_id(self, class_type: str, sub_type: str, name: str) -> str:
        """Generate a standardized 20-character ID
        Format: [Class(1)][Type(3)][Timestamp(6)][Name(10)]
        """
        try:
            # 1. Class Code (1 char)
            class_codes = {
                'Query': 'q',
                'Source': 's',
                'Entity': 'e',
                'Narrative': 'n'
            }
            class_code = class_codes.get(class_type, 'x')

            # 2. Type Code (3 chars)
            # Convert subtype path to 3-letter code
            type_parts = sub_type.split('→') if '→' in sub_type else [sub_type]
            type_code = ''.join(part[0].lower() for part in type_parts)
            # Pad or truncate to exactly 3 chars
            type_code = (type_code + '0' * 3)[:3]

            # 3. Timestamp (6 chars: hhddmm)
            now = datetime.now()
            timestamp = now.strftime('%H%d%m')  # Hour, Day, Month

            # 4. Name (10 chars)
            # Clean name: lowercase, remove special chars, spaces
            clean_name = ''.join(c for c in name if c.isalnum())
            # Pad or truncate to exactly 10 chars
            name_part = (clean_name + '0' * 10)[:10]

            # Combine all parts
            tag_id = f"{class_code}{type_code}{timestamp}{name_part}"
            
            return tag_id

        except Exception as e:
            print(f"Error generating ID: {str(e)}")
            return None

    def _get_type_code(self, class_type: str, sub_type: str) -> str:
        """Get type code from TYPE_CODES mapping"""
        try:
            if class_type in TYPE_CODES and sub_type in TYPE_CODES[class_type]:
                return TYPE_CODES[class_type][sub_type]
            return 'xxx'  # Unknown type
        except Exception as e:
            print(f"Error getting type code: {str(e)}")
            return 'xxx'

    def add_edge(self, source_tag: Dict, target_tag: Dict, edge_type: str) -> str:
        """Add edge between two tags"""
        try:
            edge_id = self._generate_edge_id(
                source_tag['id_'],
                target_tag['id_'],
                edge_type
            )
            
            source_tag['edges'].append(edge_id)
            target_tag['edges'].append(edge_id)
            
            return edge_id
            
        except Exception as e:
            print(f"Error adding edge: {str(e)}")
            return None

    def add_note(self, tag: Dict, note: str) -> Dict:
        """Add a simple note to a tag"""
        try:
            if 'notes' not in tag:
                tag['notes'] = []
                
            tag['notes'].append(note)
            tag['track'] = datetime.now().isoformat()  # Update track timestamp
            
            return tag
            
        except Exception as e:
            print(f"Error adding note: {str(e)}")
            return tag

    def _generate_edge_id(self, source_id: str, target_id: str, edge_type: str) -> str:
        """Generate standardized edge ID"""
        return f"{source_id}-{edge_type}-{target_id}"

    def _index_tag(self, tag: Dict) -> None:
        """Index a single tag in Whoosh"""
        try:
            self.tag_indexer.add_document(
                id=tag['id_'],
                name=tag['name'],
                type=tag['type_'],
                class_=tag['class_'],
                variations=','.join(tag.get('variations', [])),
                notes=json.dumps(tag.get('notes', [])),
                created=datetime.now(),
                raw_data=json.dumps(tag)
            )
        except Exception as e:
            print(f"Error indexing tag: {str(e)}") 

    def _validate_tag(self, tag: Dict) -> bool:
        """Validate tag structure and IDs"""
        required_fields = ['name', 'class_', 'type_', 'id_', 'edges']
        if not all(field in tag for field in required_fields):
            return False
        
        # Validate ID format
        if not tag['id_'].startswith(self._get_type_code(tag['class_'], tag['type_'])):
            return False
        
        # Validate edge IDs
        for edge_id in tag['edges']:
            parts = edge_id.split('-')
            if len(parts) != 3 or parts[1] not in EDGE_TYPES:
                return False
            
        return True 

TYPE_CODES = {
    # Entity Types
    'Entity': {
        'Person': 'ep0',      # Generic person
        'PersonMale': 'epm',  # Male person
        'PersonFemale': 'epf', # Female person
        'Company': 'ec0',     # Company/Organization
        'Location': 'el0',    # Generic location
        'LocationCity': 'elu', # Urban/City
        'LocationCountry': 'elc', # Country
        'Email': 'ee0',       # Generic email
        'EmailCorp': 'eec',   # Corporate email
        'EmailPrivate': 'eep', # Private email
        'Phone': 'et0',       # Phone number
        'Unknown': 'xxx'      # Unknown entity type
    },
    
    # Query Types
    'Query': {
        'DomainNERCurrent': 'qsdc',   # Query-Site-Domain-Current-NER
        'DomainNERHistoric': 'qsdh',   # Query-Site-Domain-Historic-NER
        'PageNERCurrent': 'qspc',      # Query-Site-Page-Current-NER
        'PageNERHistoric': 'qsph',     # Query-Site-Page-Historic-NER
        'DomainAICurrent': 'qadc',     # Query-AI-Domain-Current
        'DomainAIHistoric': 'qadh',    # Query-AI-Domain-Historic
        'PageAICurrent': 'qapc',       # Query-AI-Page-Current
        'PageAIHistoric': 'qaph',      # Query-AI-Page-Historic
        'ArchiveComparison': 'qcmp',   # Query-Comparison
    }
} 