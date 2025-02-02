from typing import Dict, Optional, List
from datetime import datetime
from tags.base.base_tag import BaseTag
import logging
import traceback

logger = logging.getLogger(__name__)

class QueryTag(BaseTag):
    """Base class for query tags"""
    
    QUERY_TYPES = {
        'BASE': 'qw',
        'SCOPE': {
            'DOMAIN': 'dom',
            'PAGE': 'pag'
        },
        'TIME': {
            'CURRENT': 'cur',
            'HISTORIC': 'his'
        },
        'SEARCH': {
            'NER': 'ner',
            'KEYWORD': 'key',
            'AI': 'ai0',
            'SCRAPE': 'scr'
        }
    }
    
    def __init__(self, tags_dir: Optional[str] = None):
        super().__init__(tags_dir=tags_dir)
        logger.info(f"QueryTag initialized with tags directory: {self.tags_dir}")

    async def create(self, name: str, query_type: str, notes: List[str] = None) -> Dict:
        """Create a new query tag
        
        THE HOLY RULE: 
        Query tag name MUST BE EXACTLY the user's input string.
        No modifications. No exceptions. Ever.
        
        Args:
            name: The exact user input string (THE HOLY RULE)
            query_type: Type of query (e.g., 'PageNERCurrent')
            notes: Optional list of notes about the query
            
        Returns:
            Dict: The created query tag or None if creation fails
        """
        try:
            # HOLY RULE ENFORCEMENT: name parameter must be raw user input
            if not name:
                logger.error("Query name cannot be empty - MUST be exact user input")
                return None
                
            logger.info(f"Creating query tag - Name: {name}, Type: {query_type}")
                
            # Create tag with enforced structure
            tag = self.create_base_tag(
                name=name,  # THE HOLY RULE: Exact user input, no exceptions
                class_type="Query",
                sub_type=query_type,
                variations=None,  # Query tags never have variations
                notes=notes
            )
            
            if not tag:
                logger.error(f"Failed to create base tag for query: {name}")
                return None
            
            # Ensure variations is None
            tag['variations'] = None
            
            # Save the tag
            if self.save_tags([tag]):
                logger.info(f"Successfully created query tag: {tag['id_']}")
                return tag
            else:
                logger.error(f"Failed to save query tag: {tag['id_']}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating query tag: {str(e)}")
            logger.error(traceback.format_exc())
            return None 