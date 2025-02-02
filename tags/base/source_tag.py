from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from tags.base.base_tag import BaseTag
import logging
import traceback

logger = logging.getLogger(__name__)

class SourceTag(BaseTag):
    """Base class for source tags (URLs, files, etc)"""
    
    def __init__(self, tags_dir: Optional[str] = None):
        super().__init__(tags_dir=tags_dir)
        logger.info(f"SourceTag initialized with tags directory: {self.tags_dir}")

    async def create(self, url: str, type_: str = 'WebPage', notes: List[str] = None, metadata: Dict = None) -> Dict:
        """Create a source tag
        
        Args:
            url: URL of the source
            type_: Type of source (WebPage, PDF, etc.)
            notes: Optional list of notes about the source
            metadata: Optional metadata dictionary
            
        Returns:
            Dict: The created source tag or None if creation fails
        """
        try:
            logger.info(f"Creating source tag - URL: {url}, Type: {type_}")
            
            # Create base tag with variations explicitly set to None
            tag = self.create_base_tag(
                name=url,
                class_type='Source',
                sub_type=type_,
                variations=None,  # Source tags never have variations
                notes=notes
            )
            
            if not tag:
                logger.error(f"Failed to create base tag for source: {url}")
                return None
            
            # FORCE variations to be None - no exceptions!
            tag['variations'] = None
            
            # Add metadata if provided
            if metadata:
                tag['metadata'] = metadata
            
            # Double check variations is None before saving
            if tag.get('variations') is not None:
                logger.warning("Forcing variations to None for source tag")
                tag['variations'] = None
            
            # Save the tag
            if self.save_tags([tag]):
                # Triple check variations is None after save
                if tag.get('variations') is not None:
                    logger.error("Variations was set to non-None after save!")
                    tag['variations'] = None
                    self.save_tags([tag])  # Save again to ensure None
                logger.info(f"Successfully created source tag: {tag['id_']}")
                return tag
            else:
                logger.error(f"Failed to save source tag: {tag['id_']}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating source tag: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    async def find_existing(self, url: str, existing_tags: List[Dict]) -> Optional[Dict]:
        """Find existing source tag by exact URL match"""
        try:
            for tag in existing_tags:
                if tag['class_'] == 'Source' and tag['name'] == url:
                    return tag
            return None
            
        except Exception as e:
            logger.error(f"Error finding existing source tag: {str(e)}")
            logger.error(traceback.format_exc())
            return None 