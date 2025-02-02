from typing import Dict, List, Optional
from datetime import datetime
from .base_tag import BaseTag

class NarrativeTag(BaseTag):
    """Base class for narrative tags (AI responses, summaries, etc)"""
    
    NARRATIVE_TYPES = {
        'QA': 'Question_Answer',
        'SUMMARY': 'Summary',
        'ANALYSIS': 'Analysis'
    }
    
    def __init__(self):
        super().__init__()

    def create(
        self, 
        title: str, 
        content: str, 
        narrative_type: str = 'QA',
        variations: List[str] = None,
        source_url: str = None,
        note: str = ""
    ) -> Dict:
        """Create a new narrative tag"""
        try:
            # Map narrative type
            mapped_type = self.NARRATIVE_TYPES.get(narrative_type, 'Question_Answer')
            
            # Create notes structure
            notes = [{
                "text": content,
                "source": source_url or "AI Response to Query",
                "timestamp": datetime.now().isoformat()
            }]
            
            # Create base tag
            tag = self.create_base_tag(
                name=title,
                class_type="Narrative",
                sub_type=mapped_type,
                variations=variations or [title],
                note=note
            )
            
            # Add narrative-specific fields
            tag['notes'] = notes
            
            return tag
            
        except Exception as e:
            print(f"Error creating narrative tag: {str(e)}")
            return None

    def add_response(
        self, 
        narrative_tag: Dict, 
        content: str, 
        source_url: str = None
    ) -> Dict:
        """Add a new response to an existing narrative tag"""
        try:
            note_entry = {
                "text": content,
                "source": source_url or "AI Response",
                "timestamp": datetime.now().isoformat()
            }
            
            if 'notes' not in narrative_tag:
                narrative_tag['notes'] = []
                
            narrative_tag['notes'].append(note_entry)
            return narrative_tag
            
        except Exception as e:
            print(f"Error adding response to narrative tag: {str(e)}")
            return narrative_tag

    def find_by_question(self, question: str, existing_tags: List[Dict]) -> Optional[Dict]:
        """Find a narrative tag by its question/title"""
        try:
            return next((tag for tag in existing_tags 
                        if tag['class_'] == 'Narrative' 
                        and tag['type_'] == 'Question_Answer'
                        and tag['name'] == question), None)
                        
        except Exception as e:
            print(f"Error finding narrative tag: {str(e)}")
            return None

    def merge_responses(
        self, 
        existing_tag: Dict, 
        new_content: str, 
        source_url: str = None
    ) -> Dict:
        """Merge new response into existing narrative tag"""
        try:
            # Add new response
            self.add_response(existing_tag, new_content, source_url)
            
            # Update timestamp
            existing_tag['track'] = datetime.now().isoformat()
            
            return existing_tag
            
        except Exception as e:
            print(f"Error merging responses: {str(e)}")
            return existing_tag 