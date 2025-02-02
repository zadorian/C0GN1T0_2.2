from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from tags.base.base_tag import BaseTag
import google.generativeai as genai
from config import config
import json
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import traceback

logger = logging.getLogger(__name__)

class EntityTag(BaseTag):
    """Tag class for entities"""
    
    ENTITY_TYPES = {
        'PERSON': 'ep0',
        'COMPANY': 'ec0',
        'LOCATION': 'el0',
        'EMAIL': 'ee0',
        'PHONE': 'et0'
    }
    
    def __init__(self, tags_dir: Optional[str] = None):
        # Initialize base with proper tags directory
        super().__init__(tags_dir=tags_dir)
        
        # Configure Gemini with API key
        genai.configure(api_key=config.GEMINI_API_KEY)
        self._variation_cache = {}
        self._executor = ThreadPoolExecutor(max_workers=10)  # Limit concurrent calls
        
        logger.info(f"EntityTag initialized with tags directory: {self.tags_dir}")
        
    async def create_batch(self, entities: List[Dict[str, str]]) -> List[Dict]:
        """Create multiple entity tags in parallel"""
        try:
            logger.info(f"Creating batch of {len(entities)} entity tags")
            tasks = []
            for entity in entities:
                tasks.append(self.create(
                    name=entity['name'],
                    entity_type=entity['entity_type'],
                    notes=entity.get('notes', []),
                    metadata=entity.get('metadata', {})
                ))
            results = await asyncio.gather(*tasks)
            
            # Filter out None results and count successes
            valid_results = [r for r in results if r is not None]
            logger.info(f"Successfully created {len(valid_results)} out of {len(entities)} entity tags")
            
            return valid_results
            
        except Exception as e:
            logger.error(f"Error in create_batch: {str(e)}")
            return []

    async def create(self, name: str, entity_type: str, notes: List[str] = None, metadata: Dict = None) -> Dict:
        """Async version of entity tag creation"""
        try:
            logger.info(f"EntityTag.create called for: {name} ({entity_type})")
            
            # Create base tag
            tag = self.create_base_tag(
                name=name,
                class_type='Entity',
                sub_type=entity_type,
                notes=notes
            )
            
            if not tag:
                logger.error(f"Failed to create base tag for entity: {name}")
                return None
            
            logger.info(f"Base tag created successfully for: {name}")
            
            # Generate variations based on entity type
            if entity_type == 'PERSON':
                variations = await self._get_person_variations(name)
                logger.info(f"Generated variations for {name}: {variations}")
                tag['variations'] = variations
            elif entity_type == 'COMPANY':
                tag['variations'] = await self._get_company_variations(name)
            elif entity_type == 'LOCATION':
                tag['variations'] = await self._get_location_variations(name)
            elif entity_type == 'PHONE':
                tag['variations'] = await self._get_phone_variations(name)
            else:
                # For other types, just use the name
                tag['variations'] = [name]
            
            # Ensure original name is always included
            if name not in tag['variations']:
                tag['variations'].append(name)
            
            # Remove duplicates while preserving order
            tag['variations'] = list(dict.fromkeys(tag['variations']))
            
            # Add metadata if provided (but not source-related)
            if metadata:
                # Remove any source-related keys
                clean_metadata = {k: v for k, v in metadata.items() 
                                if not k.startswith('source_')}
                if clean_metadata:
                    tag['metadata'] = clean_metadata
            
            # Save the updated tag
            if self.save_tags([tag]):
                logger.info(f"Successfully created entity tag: {tag['id_']}")
                return tag
            else:
                logger.error(f"Failed to save entity tag: {tag['id_']}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating entity tag: {str(e)}")
            return None
            
    async def _get_person_variations(self, name: str) -> List[str]:
        """Async version of name variation generation"""
        try:
            # Check cache first
            cache_key = f"name_variations_{name}"
            if cache_key in self._variation_cache:
                return self._variation_cache[cache_key]
            
            # Run Gemini API call in thread pool to prevent blocking
            loop = asyncio.get_event_loop()
            variations = await loop.run_in_executor(
                self._executor,
                self._generate_variations,
                name,
                self._get_person_prompt(name)
            )
            
            if variations:
                self._variation_cache[cache_key] = variations
                if name not in variations:
                    variations.append(name)
                return list(set(variations))
                
            return [name]
            
        except Exception as e:
            logger.error(f"Error in async name variation generation: {str(e)}")
            return [name]

    def _generate_variations(self, name: str, prompt: str) -> List[str]:
        """Run Gemini API call in thread pool"""
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            
            try:
                variations = json.loads(response.text)
                if isinstance(variations, list):
                    return variations
            except:
                pass
                
            return [name]
            
        except Exception as e:
            logger.error(f"Error in Gemini API call: {str(e)}")
            return [name]

    def _get_person_prompt(self, name: str) -> str:
        """Get the prompt for person name variations"""
        return f"""
        Generate name variations for: {name}
        
        CRITICAL: NEVER INVENT OR CREATE NEW NAMES! ONLY USE PARTS OF THE ORIGINAL NAME!
        
        Rules:
        1. Always include the surname in each variation
        2. Follow these exact patterns using ONLY the parts from "{name}":
           - "firstname lastname"
           - "lastname, firstname"
           - "firstname middlename lastname" (if middle name exists)
           - "firstname m. lastname" (middle initial if exists)
           - Include common/cultural variations ONLY if they are standard (e.g., "Robert" -> "Bob")
        3. DO NOT include:
           - Single names without surname
           - Unrelated nicknames
           - Initials only
           - ANY invented or guessed variations
        
        Return ONLY a JSON array of strings, nothing else.
        Example for "Robert James Smith":
        ["Robert James Smith", "Smith, Robert James", "Robert J. Smith", "Smith, Robert J.", "Bob Smith"]
        """

    async def _get_company_variations(self, name: str) -> List[str]:
        """Get variations for a company name"""
        try:
            prompt = f"""
            Generate variations of this company name: {name}
            
            CRITICAL: NEVER INVENT NEW NAMES! ONLY USE PARTS OF THE ORIGINAL NAME!
            
            Rules:
            1. Only use parts that appear in "{name}"
            2. Include:
               - Full name
               - Name without legal suffix (Inc, LLC, Ltd, etc)
               - Standard abbreviations of words in the name
            3. DO NOT:
               - Add any new words
               - Guess at abbreviations
               - Create fictional variations
            
            Return ONLY a JSON array of strings, nothing else.
            Example for "International Business Machines Corporation":
            ["International Business Machines Corporation", "International Business Machines", "IBM Corporation", "IBM"]
            """
            
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            
            try:
                variations = json.loads(response.text)
                if isinstance(variations, list):
                    variations.append(name)
                    return list(set(variations))
            except:
                pass
                
            return [name]
            
        except Exception as e:
            logger.error(f"Error getting company variations: {str(e)}")
            return [name]

    async def _get_location_variations(self, name: str) -> List[str]:
        """Get variations for a location name using Gemini"""
        prompt = f"""
        Generate variations of this location name: {name}
        
        CRITICAL: NEVER INVENT NEW NAMES! ONLY USE OFFICIAL OR WIDELY DOCUMENTED VARIATIONS!
        
        Rules:
        1. Only include:
           - Official alternate names
           - Standard abbreviations (e.g., NY for New York)
           - Well-documented historical names
           - Common local language variations
        2. DO NOT:
           - Invent nicknames
           - Guess at variations
           - Add fictional or unofficial names
        
        Return ONLY a JSON array of strings.
        Example for "New York City":
        ["New York City", "NYC", "New York", "NY"]
        """
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            variations = json.loads(response.text)
            return variations
        except Exception as e:
            logger.error(f"Error getting location variations: {str(e)}")
            return [name]

    async def _get_phone_variations(self, number: str) -> List[str]:
        """Get variations for a phone number using Gemini"""
        prompt = f"""
        Generate all plausible variations of this phone number: {number}
        
        Include:
        1. Different separator patterns (spaces, dashes, dots, brackets)
        2. With and without country code if present
        3. Common local formats based on the country
        4. With and without leading zeros or trunk prefixes
        
        Rules:
        - Only include variations that represent the exact same number
        - Include international and local formats
        - For US/Canada numbers, include both (123) 456-7890 and 123-456-7890 styles
        - For international numbers, include +XX and 00XX country code variants
        
        Return ONLY a JSON array of strings.
        Examples:
        ["+1 (555) 123-4567", "1-555-123-4567", "(555) 123-4567", "555.123.4567"]
        ["+44 20 7123 4567", "020 7123 4567", "0207123 4567"]
        """
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            variations = json.loads(response.text)
            return variations
        except Exception as e:
            logger.error(f"Error getting phone variations: {str(e)}")
            return [number] 