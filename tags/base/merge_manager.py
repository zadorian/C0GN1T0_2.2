from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import uuid

class MergeManager:
    """Handles merging of duplicate/related tags and tracks merge history"""
    
    def __init__(self):
        self.tags_file = Path(__file__).parent.parent / 'tags.json'
        self.merge_history_file = Path(__file__).parent.parent / 'merge_history.json'

    def merge_tags(self, older_tag: Dict, newer_tag: Dict) -> Dict:
        """Merge two tags, preserving older ID and combining attributes"""
        try:
            merged_tag = older_tag.copy()
            
            # Combine variations
            all_variations = set(older_tag.get('variations', []))
            all_variations.update(newer_tag.get('variations', []))
            all_variations.add(older_tag['name'])
            all_variations.add(newer_tag['name'])
            merged_tag['variations'] = list(all_variations)
            
            # Combine notes
            if 'note' in newer_tag:
                merged_tag['note'] = f"{merged_tag.get('note', '')}\n{newer_tag['note']}".strip()
                
            # Combine edges
            merged_tag['edges'] = list(set(
                merged_tag.get('edges', []) + newer_tag.get('edges', [])
            ))
            
            # Record merge in history
            self.record_merge(newer_tag, older_tag, "auto", "Matching name or variation")
            
            return merged_tag
            
        except Exception as e:
            print(f"Error merging tags: {str(e)}")
            return older_tag

    def record_merge(self, source_tag: Dict, target_tag: Dict, merge_type: str, reason: str):
        """Record a merge in the history"""
        try:
            history = []
            if self.merge_history_file.exists():
                with open(self.merge_history_file, 'r') as f:
                    history = json.load(f)
            
            merge_record = {
                'merge_id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'merge_type': merge_type,
                'source_tag': source_tag['name'],
                'target_tag': target_tag['name'],
                'reason': reason
            }
            
            history.append(merge_record)
            
            with open(self.merge_history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            print(f"Error recording merge: {str(e)}")

    def find_mergeable_tag(self, new_tag: Dict, existing_tags: List[Dict]) -> Optional[Dict]:
        """Find if new tag should be merged with any existing tag"""
        new_name = new_tag['name'].lower()
        new_variations = {v.lower() for v in new_tag.get('variations', [])}
        new_variations.add(new_name)
        
        for existing_tag in existing_tags:
            existing_name = existing_tag['name'].lower()
            existing_variations = {v.lower() for v in existing_tag.get('variations', [])}
            existing_variations.add(existing_name)
            
            # Check for any overlap in names or variations
            if new_variations & existing_variations:
                return existing_tag
                
        return None