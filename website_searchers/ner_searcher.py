import os
import sys
import json
import traceback
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import asyncio
from datetime import datetime
import re
from collections import defaultdict
import spacy
from spacy.language import Language
from scraping.current_scraping import content_controller

# Make sure we can import from project root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Azure Text Analytics
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

# Local config (assuming config.py is in project root)
from config import config

# Corrected references to caching + scrapers (no "website_searcher" subfolder):
from scraping.caching.scrape_caching import content_cache
from scraping.scrapers.firecrawl import get_content

# Import tag scenario with correct path
try:
    from tags.base.scenarios.scenario_ner_search import NERSearchScenario
    logger.info("Successfully imported NERSearchScenario")
except ImportError as e:
    logger.error(f"Failed to import NERSearchScenario: {str(e)}")
    logger.error(f"Current sys.path: {sys.path}")
    raise

# Add type labels for output formatting
type_labels = {
    'p': 'People',
    '@': 'Emails',
    't': 'Phone Numbers',
    'l': 'Locations',
    'c': 'Companies'
}

# Add scraping options
scrape_options = {
    'max_depth': 2,
    'follow_links': True,
    'timeout': 30,
    'max_retries': 3
}

# Global spaCy model
nlp: Language = None

def initialize_spacy():
    """Initialize spaCy with the English model"""
    global nlp
    try:
        nlp = spacy.load("en_core_web_sm")
        logger.info("Successfully loaded spaCy model")
    except Exception as e:
        logger.error(f"Error loading spaCy model: {str(e)}")
        raise

def extract_entities(text: str, ner_type: str) -> Set[str]:
    """Extract entities using Azure Text Analytics"""
    logger.info(f"Extracting entities of type {ner_type} from text length: {len(text)}")
    
    try:
        # Initialize Azure Text Analytics client
        credential = AzureKeyCredential(config.AZURE_KEY)
        text_analytics_client = TextAnalyticsClient(
            endpoint=config.AZURE_ENDPOINT, 
            credential=credential
        )
        
        # Map our types to Azure entity categories
        azure_categories = {
            'p': ['Person'],
            'c': ['Organization'],
            'l': ['Location'],
            't': ['PhoneNumber'],
            '@': ['Email']
        }
        
        target_categories = azure_categories.get(ner_type, [])
        logger.info(f"Looking for Azure entity categories: {target_categories}")
        
        # Split text into chunks if too long (Azure has a 5120 char limit)
        max_length = 5000
        text_chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        
        full_names = set()
        first_names = set()
        last_names = set()
        
        # Process each chunk
        for chunk in text_chunks:
            try:
                # Call Azure API with proper document format
                response = text_analytics_client.recognize_entities(
                    documents=[{
                        "id": "1",
                        "language": "en",
                        "text": chunk
                    }]
                )
                
                # Process results
                for doc in response:
                    if doc.is_error:
                        logger.error(f"Error in Azure NER: {doc.error}")
                        continue
                        
                    for entity in doc.entities:
                        if entity.category in target_categories and entity.confidence_score > 0.6:
                            clean_text = entity.text.strip()
                            if clean_text and len(clean_text) > 2:
                                # If it contains a space, it's a full name
                                if ' ' in clean_text:
                                    full_names.add(clean_text)
                                    # Add parts to first/last name sets for filtering
                                    parts = clean_text.split()
                                    first_names.add(parts[0])
                                    if len(parts) > 1:
                                        last_names.add(parts[-1])
                                else:
                                    # Store single names temporarily
                                    first_names.add(clean_text)
            
            except Exception as chunk_e:
                logger.error(f"Error processing chunk: {str(chunk_e)}")
                continue
        
        # Final set: full names + single names that aren't parts of full names
        final_entities = full_names.union({name for name in first_names 
                                         if name not in first_names and name not in last_names})
        
        logger.info(f"Found {len(final_entities)} matching entities from Azure")
        for entity in sorted(final_entities):
            logger.info(f"- {entity}")
            
        return final_entities
        
    except Exception as e:
        logger.error(f"Error in Azure entity extraction: {str(e)}")
        logger.error(traceback.format_exc())
        return set()

async def search_entities(content: Dict) -> str:
    """Search for named entities in the provided content"""
    try:
        if not content or 'pages' not in content:
            return "No content to analyze"

        pages = content['pages']
        logger.info(f"Processing {len(pages)} pages")
        
        url_results = {}
        entity_results = []
        total_entities = 0

        # FIRST PHASE: Extract and show entities immediately
        for page in pages:
            if 'url' in page and 'content' in page:
                url_key = page['url']
                text = page['content']
                logger.info(f"\nProcessing URL: {url_key}")
                
                if not text:
                    continue
                    
                url_results[url_key] = {}
                entities = extract_entities(text, 'p')
                if entities:
                    url_results[url_key]['p'] = sorted(entities)
                    total_entities += len(entities)
                    for entity in entities:
                        entity_results.append({
                            'entity': entity,
                            'entity_type': 'PERSON',
                            'url': url_key
                        })

        # Format and IMMEDIATELY return results to user
        result = []
        if url_results:
            for url_key, type_results in sorted(url_results.items()):
                if any(type_results.values()):
                    result.append(f"\nURL: {url_key}")
                    if 'p' in type_results and type_results['p']:
                        result.append("\nPeople:")
                        for entity in sorted(type_results['p']):
                            result.append(f"- {entity}")
            
            if total_entities > 0:
                result.append(f"\nTotal unique people found: {total_entities}")

        output = "\n".join(result) if result else "No people found in content"
        print(output)  # IMMEDIATELY show results to user

        # SECOND PHASE: Create and index tags
        if entity_results:
            try:
                domain = url_key.split('/')[2] if '/' in url_key else url_key
                print("\nCreating and indexing tags...")
                
                # Create tags directly (not in background)
                ner_scenario = NERSearchScenario()
                created_tags = await ner_scenario.process(
                    ner_type='p',
                    domain=domain,
                    results=entity_results,
                    search_type='current'
                )
                
                if created_tags:
                    logger.info(f"Successfully created {len(created_tags)} tags:")
                    logger.info(f"- Query tag: {created_tags[0]['id_']}")
                    logger.info(f"- Source tags: {len([t for t in created_tags if t['class_'] == 'Source'])}")
                    logger.info(f"- Entity tags: {len([t for t in created_tags if t['class_'] == 'Entity'])}")
                    print(f"\nCreated and indexed {len(created_tags)} tags successfully.")
                else:
                    logger.error("No tags were created!")
                    print("\nError: Failed to create tags!")
                
            except Exception as e:
                logger.error(f"Error creating tags: {str(e)}")
                logger.error(traceback.format_exc())
                print("\nError: Failed to create tags!")

        return ""  # Return empty since we already printed results

    except Exception as e:
        logging.error(f"Error in entity extraction: {e}", exc_info=True)
        return f"Error in entity extraction: {str(e)}"

async def handle_ner_extraction(url: str, ner_types: List[str]) -> str:
    """Handle NER extraction request from WebsiteSearcher"""
    try:
        # Get content using the content controller
        content = await content_controller.get_content(url)
        if not content:
            return "No content found to analyze"

        # Process the content through our entity extraction
        return await search_entities(content)

    except Exception as e:
        logger.error(f"Error in NER extraction handler: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error in NER extraction: {str(e)}"