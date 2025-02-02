import requests
from typing import Dict, List, Optional
from AI_models.gemini_flash_1_5 import generate_with_retry  # Replace Claude

async def analyze_entity_data(entity_data: Dict) -> str:
    """Analyze entity data using Gemini."""
    prompt = f"""Analyze this entity data and provide insights:

Entity Data:
{entity_data}

Focus on:
1. Key relationships and connections
2. Potential risk indicators
3. Notable patterns
4. Verification of information
5. Data gaps or inconsistencies

Format as a clear analysis with sections and bullet points."""

    return generate_with_retry(prompt, temperature=0.3)

def search_entities(query, limit=100):
    # Define the API endpoint for searching entities
    search_url = "https://aleph.occrp.org/api/2/entities"

    # Your API key
    api_key = "1c0971afa4804c2aafabb125c79b275e"

    # Set up the request headers
    headers = {
        'Authorization': f'ApiKey {api_key}',
        'Accept': 'application/json'
    }

    offset = 0
    total_results = []

    while True:
        # Set up the query parameters
        params = {
            'q': query,
            'filter:schema': 'Person,Company',  # Note: case sensitive
            'limit': limit,
            'offset': offset
        }

        try:
            # Make the GET request with timeouts
            response = requests.get(search_url, headers=headers, params=params, timeout=(3.05, 27))
            response.raise_for_status()
            
            search_results = response.json()
            
            results = search_results.get('results', [])
            
            if not results:
                if offset == 0:  # Only print this message on first attempt
                    print("No results found for this query.")
                break
                
            total_results.extend(results)

            # Check if there are more results to fetch
            if 'next' in search_results.get('links', {}):
                offset += limit
            else:
                break
                
        except requests.exceptions.Timeout:
            print("Request timed out. The server is taking too long to respond.")
            break
        except requests.exceptions.ConnectionError:
            print("Failed to connect to the server. Please check your internet connection.")
            break
        except requests.exceptions.HTTPError as err:
            print(f"HTTP Error occurred: {err}")
            break
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            break

    print("\n" + "="*50)
    print(f"SEARCH RESULTS FOR: {query}")
    print("="*50)
    print(f"Total Results Found: {len(total_results)}\n")

    for entity in total_results:
        print("-"*50)
        schema = entity.get('schema', 'N/A')
        properties = entity.get('properties', {})
        links = entity.get('links', {})
        
        # Enhanced links section
        print("\nLINKS:")
        # OCCRP Aleph link
        print(f"OCCRP Aleph: {links.get('ui', 'N/A')}")
        # Original source link
        if links.get('source'):
            print(f"Original Source: {links.get('source')}")
        # Document links if available
        if links.get('file'):
            print(f"Document File: {links.get('file')}")
        if links.get('pdf'):
            print(f"PDF Version: {links.get('pdf')}")
        
        # Print entity details
        if schema == 'Person':
            name_parts = []
            if properties.get('title'): name_parts.extend(properties['title'])
            if properties.get('firstName'): name_parts.extend(properties['firstName'])
            if properties.get('middleName'): name_parts.extend(properties['middleName'])
            if properties.get('lastName'): name_parts.extend(properties['lastName'])
            full_name = ' '.join(name_parts) if name_parts else properties.get('name', ['N/A'])[0]
            
            print(f"PERSON:")
            print(f"Name: {full_name}")
            print(f"Nationality: {', '.join(properties.get('nationality', ['N/A']))}")
            print(f"Address: {', '.join(properties.get('address', ['N/A']))}")
            print(f"Birth Date: {', '.join(properties.get('birthDate', ['N/A']))}")

        elif schema == 'Company':
            print(f"COMPANY:")
            print(f"Name: {properties.get('name', ['N/A'])[0]}")
            print(f"Jurisdiction: {', '.join(properties.get('jurisdiction', ['N/A']))}")
            print(f"Registration: {', '.join(properties.get('registrationNumber', ['N/A']))}")
            print(f"Address: {', '.join(properties.get('address', ['N/A']))}")

        elif schema == 'Ownership':
            owner = properties.get('owner', [{}])[0].get('properties', {})
            asset = properties.get('asset', [{}])[0].get('properties', {})
            
            print(f"OWNERSHIP RECORD:")
            print("Owner:")
            print(f"  - {owner.get('name', ['N/A'])[0]}")
            print("Asset:")
            print(f"  - {asset.get('name', ['N/A'])[0]}")

        # Enhanced source information
        try:
            collection_id = entity.get('collection', {}).get('id')
            if collection_id:
                collection_url = f"https://aleph.occrp.org/api/2/collections/{collection_id}"
                collection_response = requests.get(collection_url, headers=headers, timeout=(3.05, 27))
                collection_response.raise_for_status()
                collection_info = collection_response.json()
                
                print("\nSOURCE:")
                print(f"Collection: {collection_info.get('label', 'N/A')}")
                print(f"Publisher: {collection_info.get('publisher', 'N/A')}")
                print(f"Collection Link: {collection_info.get('links', {}).get('ui', 'N/A')}")
                
                # Add original source URL if available
                if collection_info.get('data', {}).get('source_url'):
                    print(f"Original Data Source: {collection_info['data']['source_url']}")
                
                # Add any additional source links
                source_links = collection_info.get('links', {})
                if source_links.get('source'):
                    print(f"Source Portal: {source_links['source']}")
                if source_links.get('file'):
                    print(f"Source File: {source_links['file']}")
        except Exception as e:
            print("\nSOURCE: Unable to fetch source information")

        # Add AI analysis for complex entities
        if entity.get('schema') in ['Company', 'Person'] and entity.get('properties'):
            analysis = generate_with_retry(
                f"""Analyze this entity's information and highlight key points:
                {entity}
                Focus on relationships, patterns, and potential risk indicators.""",
                temperature=0.3
            )
            if analysis:
                print("\nAI ANALYSIS:")
                print(analysis)

        print()

    print("="*50)
    print(f"End of results for: {query}")
    print("="*50 + "\n")
    
    return total_results  # Return the results list

if __name__ == "__main__":
    query = input("Enter your search query: ")
    search_entities(query)
