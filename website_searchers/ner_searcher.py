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

async def handle_ner_extraction(url: str, options: Dict) -> str:
    """Extract named entities from content."""
    ner_type_input = options.get('ner_type', 'p')
    
    # If 'ent!', expand to all entity types
    if 'ent!' in ner_type_input:
        ner_types = ['p', 'c', 'l', '@', 't']
    else:
        ner_types = ner_type_input.split()  # Split into multiple types
    
    content = options.get('cached_content', '')
    
    print("\nDEBUG: Content type:", type(content))
    if isinstance(content, dict):
        print("DEBUG: Content keys:", content.keys())
        
        # Get the date from metadata
        date_str = ""
        if 'metadata' in content:
            if 'timestamp' in content['metadata']:
                timestamp = content['metadata']['timestamp']
                # Convert YYYYMMDD to readable format
                try:
                    from datetime import datetime
                    date = datetime.strptime(timestamp, '%Y%m%d')
                    date_str = date.strftime('%d %B %Y')
                except:
                    date_str = content['metadata'].get('date', '')
            else:
                date_str = content['metadata'].get('date', '')
        
        # Dictionary to store text by URL
        url_texts = {}
        
        # Handle the nested structure from archived content
        if 'urls' in content:
            for url_data in content['urls']:
                url_key = url_data.get('url', 'unknown')
                if url_data.get('content'):
                    url_texts[url_key] = url_data['content']
                elif url_data.get('text'):
                    url_texts[url_key] = url_data['text']
        elif 'pages' in content:
            for page in content['pages']:
                url_key = page.get('url', 'unknown')
                if page.get('content'):
                    url_texts[url_key] = page['content']
                elif page.get('text'):
                    url_texts[url_key] = page['text']
        else:
            # Single page case
            if 'text' in content:
                url_texts[url] = content['text']
            elif 'content' in content:
                url_texts[url] = content['content']
            else:
                url_texts[url] = str(content)
    else:
        url_texts = {url: str(content)}
        date_str = ""
    
    if not url_texts:
        return "No content found to analyze"

    # Process each URL and store results by URL first
    url_results = {}  # url -> type -> set(entities)
    type_labels = {
        'p': 'People',
        'c': 'Companies/Organizations',
        'l': 'Locations',
        '@': 'Email Addresses',
        't': 'Phone Numbers'
    }
    
    total_entities = 0
    for url_key, text in url_texts.items():
        url_results[url_key] = {}
        
        for ner_type in ner_types:
            ner_type = ner_type.rstrip('!')  # Remove trailing !
            entities = extract_entities(text, ner_type)
            
            # Post-process people entities to remove first names that are part of full names
            if ner_type == 'p':
                full_names = {e for e in entities if len(e.split()) > 1}
                first_names = {e for e in entities if len(e.split()) == 1}
                
                # Remove first names that appear in full names
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
        result = f"\nExtracting entities from content:\n"
        
        # Show results grouped by URL
        for url_key in sorted(url_results.keys()):
            result += f"\n{url_key}"
            if date_str:
                result += f" [{date_str}]"
            result += ":\n"
            
            # Show each entity type for this URL
            for ner_type in ner_types:
                ner_type = ner_type.rstrip('!')
                if ner_type in url_results[url_key]:
                    type_label = type_labels.get(ner_type, f'Type {ner_type}')
                    result += f"\n{type_label}:\n"
                    for entity in url_results[url_key][ner_type]:
                        result += f"- {entity}\n"
        
        result += f"\nTotal entities found: {total_entities}"
        return result
    else:
        return f"No entities found in content."


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