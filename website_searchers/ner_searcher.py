import os
import sys
import json
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set
import asyncio

# Make sure we can import from project root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Azure Text Analytics
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

# Local config (assuming config.py is in project root)
from config import config

# Corrected references to caching + scrapers (no "website_searcher" subfolder):
from scraping.caching.scrape_caching import content_cache
from scraping.scrapers.firecrawl import get_content

# If you really do have "Tags/scenarios/scenario_ner_search.py", keep this:
from Tags.scenarios.scenario_ner_search import NERSearchScenario
# Otherwise, adjust to wherever scenario_ner_search.py actually is
# e.g. from scenarios.scenario_ner_search import NERSearchScenario

async def process_chunk(text: str, url: str) -> Set[str]:
    """Process a single chunk of text through Azure Text Analytics."""
    try:
        credential = AzureKeyCredential(config.AZURE_KEY)
        client = TextAnalyticsClient(
            endpoint=config.AZURE_ENDPOINT,
            credential=credential
        )

        # Get response from Azure
        response = client.recognize_entities(documents=[text])[0]
        if response.is_error:
            print(f"Error processing chunk from {url}: {response.error}")
            return set()

        # Extract entities based on category
        entities = set()
        for entity in response.entities:
            if len(entity.text.strip()) > 1:  # Skip single characters
                entities.add(entity.text.strip())

        return entities

    except Exception as e:
        print(f"Error in chunk processing: {str(e)}")
        return set()

async def handle_ner_extraction(url: str, options: dict) -> str:
    """
    Extract named entities from content.
    """
    try:
        print("\nExtracting entities from content:")
        print(f"\n{url}:\n")
        
        content = options.get('cached_content', {})
        ner_type = options.get('ner_type', '')

        # Dictionary to store text by URL
        url_texts = {}
        
        # Handle different content structures
        if isinstance(content, dict):
            if 'pages' in content:
                for page in content['pages']:
                    url_key = page.get('url', url)
                    url_texts[url_key] = page.get('content', page.get('text', ''))
            elif 'urls' in content:
                for url_data in content['urls']:
                    url_key = url_data.get('url', url)
                    url_texts[url_key] = url_data.get('content', url_data.get('text', ''))
            elif 'summary' in content:
                # Historic content structure
                url_texts[url] = content['summary']
            elif 'text' in content:
                url_texts[url] = content['text']
            elif 'content' in content:
                url_texts[url] = content['content']
        else:
            url_texts[url] = str(content)

        if not url_texts:
            return "No content found to analyze"

        # If 'ent!', expand to all entity types
        if 'ent!' in ner_type:
            ner_types = ['p', 'c', 'l', '@', 't']
        else:
            ner_types = ner_type.split()  # Split into multiple types

        # Process each URL and store results
        url_results = {}
        type_labels = {
            'p': 'People',
            'c': 'Companies/Organizations',
            'l': 'Locations',
            '@': 'Email Addresses',
            't': 'Phone Numbers'
        }
        
        total_entities = 0
        for url_key, text in url_texts.items():
            if not text:
                continue
                
            url_results[url_key] = {}
            for ner_type in ner_types:
                ner_type = ner_type.rstrip('!')
                entities = extract_entities(text, ner_type)
                
                # Post-process people entities
                if ner_type == 'p':
                    full_names = {e for e in entities if len(e.split()) > 1}
                    first_names = {e for e in entities if len(e.split()) == 1}
                    
                    filtered_first_names = set()
                    for first_name in first_names:
                        appears_in_full = False
                        for full_name in full_names:
                            if full_name.lower().startswith(first_name.lower() + " "):
                                appears_in_full = True
                                break
                        if not appears_in_full:
                            filtered_first_names.add(first_name)
                    
                    entities = sorted(full_names | filtered_first_names)
                
                if entities:
                    url_results[url_key][ner_type] = sorted(entities)
                    total_entities += len(entities)
        
        # Format output
        if url_results:
            result = []
            for url_key in sorted(url_results.keys()):
                if url_results[url_key]:  # Only show URLs with results
                    for ner_type in ner_types:
                        ner_type = ner_type.rstrip('!')
                        if ner_type in url_results[url_key]:
                            type_label = type_labels.get(ner_type, f'Type {ner_type}')
                            result.append(f"\n{type_label}:")
                            for entity in url_results[url_key][ner_type]:
                                result.append(f"- {entity}")
            
            result.append(f"\nTotal entities found: {total_entities}")
            return "\n".join(result)
        else:
            return f"No entities found in content."

    except Exception as e:
        print(f"Error in entity extraction: {e}")
        traceback.print_exc()
        return "Error in entity extraction"

def extract_entities(text: str, entity_type: str) -> List[str]:
    """Direct Azure NER on a single text string, returning matching entities."""
    try:
        credential = AzureKeyCredential(config.AZURE_KEY)
        client = TextAnalyticsClient(
            endpoint=config.AZURE_ENDPOINT, 
            credential=credential
        )
        
        type_map = {
            'p': ['Person'],
            '@': ['Email'],
            't': ['PhoneNumber'],
            'l': ['Location'],
            'c': ['Organization']
        }
        targets = type_map.get(entity_type, [])
        if not targets:
            return []
        
        # Break into 5K chunks
        chunk_size = 5000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        found_entities = set()
        for chunk in chunks:
            try:
                doc = client.recognize_entities(documents=[chunk])[0]
                if not doc.is_error:
                    for e in doc.entities:
                        if e.category in targets:
                            cleaned = e.text.strip()
                            if len(cleaned) > 1:
                                found_entities.add(cleaned)
            except Exception as ex:
                print(f"Error processing chunk: {ex}")
                continue
        
        return sorted(found_entities)

    except Exception as e:
        print(f"Error in entity extraction: {e}")
        return []