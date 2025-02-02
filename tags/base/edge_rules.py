"""Central management of all edge operations and rules"""
from typing import Dict, List, Optional
from datetime import datetime

# Core edge type definitions
EDGE_TYPES = {
    # Source Relationships
    'sba': "B (Source) is source of A (Entity/Query)",  # source->entity/query
    
    # Query Relationships
    'rba': "B is result of A (Query)",  # query->result
    
    # Entity Relationships
    'oab': "A owns B",          # owner->owned
    'oba': "B owns A",          # owned->owner
    'ccc': "Business partners", # bidirectional business
    'cab': "A manages B",      # manager->managed
    'cba': "B manages A",      # managed->manager
    'raa': "Partners/Variations", # bidirectional partners/variations
    'rbb': "Siblings",         # bidirectional siblings
    'rab': "A parent of B",    # parent->child
    'rba': "B parent of A",    # child->parent
    'hab': "A location of B",  # location->entity
    'hba': "B location of A"   # entity->location
}

def validate_edge(edge_type: str, source_tag: Dict, target_tag: Dict) -> bool:
    """Validate if an edge can be created between two tags"""
    if edge_type not in EDGE_TYPES:
        return False
        
    # Define valid class pairs for each edge type
    valid_pairs = {
        'sba': [
            ('Entity', 'Source'),  # Entity -> Source
            ('Query', 'Source')    # Query -> Source
        ],
        'rba': [
            ('Query', 'Entity'),   # Query -> Entity
            ('Query', 'Source'),   # Query -> Source
            ('Query', 'Narrative') # Query -> Narrative
        ],
        'raa': [('Entity', 'Entity')],  # For person variations and relationships
        'ccc': [('Entity', 'Entity')]   # For business relationships
    }
    
    source_class = source_tag.get('class_')
    target_class = target_tag.get('class_')
    
    # Check if the class pair is valid for this edge type
    return (source_class, target_class) in valid_pairs.get(edge_type, [])

def generate_edge_id(source_id: str, edge_type: str, target_id: str) -> str:
    """Generate a standardized edge ID"""
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Invalid edge type: {edge_type}")
    return f"{source_id}-{edge_type}-{target_id}"

def create_edge(source_tag: Dict, target_tag: Dict, edge_type: str) -> Optional[str]:
    """Create and validate an edge between two tags"""
    if not validate_edge(edge_type, source_tag, target_tag):
        print(f"Warning: Invalid edge type '{edge_type}' between {source_tag['class_']}/{source_tag['type_']} and {target_tag['class_']}/{target_tag['type_']}")
        return None

    edge_id = generate_edge_id(source_tag['id_'], edge_type, target_tag['id_'])
    
    # Update tags
    if 'edges' not in source_tag:
        source_tag['edges'] = []
    if 'edges' not in target_tag:
        target_tag['edges'] = []
        
    source_tag['edges'].append(edge_id)
    target_tag['edges'].append(edge_id)
    
    return edge_id

def create_person_variation_edges(original_tag: Dict, variation_tags: List[Dict]) -> List[str]:
    """Create edges between a person and their name variations"""
    edge_ids = []
    for var_tag in variation_tags:
        edge_id = create_edge(original_tag, var_tag, 'raa')
        if edge_id:
            edge_ids.append(edge_id)
    return edge_ids

def create_source_edge(entity_tag: Dict, source_tag: Dict) -> Optional[str]:
    """Create edge between an entity and its source"""
    return create_edge(entity_tag, source_tag, 'sba')

def create_query_result_edge(query_tag: Dict, result_tag: Dict) -> Optional[str]:
    """Create edge between a query and its result"""
    return create_edge(query_tag, result_tag, 'rba')

def get_edge_type(edge_id: str) -> Optional[str]:
    """Extract edge type from edge ID"""
    try:
        return edge_id.split('-')[1]
    except IndexError:
        return None

def get_valid_edge_types(source_tag: Dict, target_tag: Dict) -> List[str]:
    """Get list of valid edge types for a pair of tags"""
    valid_types = []
    
    source_class = source_tag.get('class_')
    target_class = target_tag.get('class_')
    
    # Check each edge type
    for edge_type in EDGE_TYPES:
        # Define valid class pairs for each edge type
        valid_pairs = {
            'sba': [('Entity', 'Source'), ('Query', 'Source')],
            'rba': [('Query', 'Entity'), ('Query', 'Narrative')],
            'raa': [('Entity', 'Entity')],  # For person variations and relationships
            'ccc': [('Entity', 'Entity')]   # For business relationships
        }
        
        if (source_class, target_class) in valid_pairs.get(edge_type, []):
            valid_types.append(edge_type)
            
    return valid_types