import requests
from typing import List, Dict
from AI_models.gemini_flash_1_5 import generate_with_retry  # Replace Claude

ALEPH_BASE_URL = "https://aleph.occrp.org/api/2/entities"

async def analyze_person_connections(directorships: List[Dict]) -> str:
    """Analyze person's business connections using Gemini."""
    if not directorships:
        return "No directorship data available for analysis."
        
    prompt = f"""Analyze these business connections and identify patterns:
    
Directorship Data:
{directorships}

Please analyze:
1. Common industries or sectors
2. Geographic patterns
3. Temporal patterns (appointment dates)
4. Potential risk indicators
5. Notable relationships

Format as a clear report with bullet points."""

    return generate_with_retry(prompt, temperature=0.3)

def get_company_directorships(person_id: str, headers: dict) -> List[Dict]:
    """Get all companies where the person is a director"""
    params = {
        'filter:entities': person_id,
        'filter:schemata': ['Directorship', 'Company', 'Organization'],
        'include': ['properties', 'entities', 'schema'],
        'expand': 'true',
        'limit': 50
    }
    
    try:
        response = requests.get(ALEPH_BASE_URL, headers=headers, params=params)
        response.raise_for_status()
        results = response.json().get('results', [])
        
        directorships = []
        for result in results:
            if result.get('schema') in ['Company', 'Organization']:
                directorships.append({
                    'company': result,
                    'properties': {
                        'role': ['Director']
                    }
                })
            elif result.get('schema') == 'Directorship':
                props = result.get('properties', {})
                org_id = props.get('organization', [None])[0]
                if org_id:
                    for entity in result.get('entities', []):
                        if entity.get('id') == org_id:
                            directorships.append({
                                'company': entity,
                                'properties': props
                            })
                            break
        
        return directorships
        
    except Exception as e:
        print(f"Error fetching directorships: {e}")
        return [] 