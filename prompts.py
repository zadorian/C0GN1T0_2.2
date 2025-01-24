"""
Specialized prompts for different AI comparison scenarios.
"""

def get_backlinks_comparison_prompt(results_text: str, is_domain_comparison: bool = True) -> str:
    """
    Generate a prompt for comparing backlinks results.
    
    Args:
        results_text: The combined results from all targets
        is_domain_comparison: Whether we're comparing referring domains (True) or individual backlinks (False)
    """
    if is_domain_comparison:
        return f"""
We have backlinks analysis results from multiple targets. Your task is to:
1. First, check if each target has any backlinks data. If a target has no backlinks, clearly state this fact.
2. For targets with backlinks:
   - Identify EXACTLY which referring domains appear in both targets (the overlap)
   - Compare the Domain Ratings (DR) of overlapping domains between the targets
   - List SPECIFICALLY which referring domains are unique to each target
3. Compare the total numbers (backlinks, referring domains) between targets
4. Analyze any patterns in the differences
5. If one or both targets have no backlinks, explain what this might indicate about the domains

Here are the results to compare:

{results_text}

Please structure your response clearly with sections for:
- Data Availability (whether each target has backlink data)
- Overlapping Referring Domains (if any exist)
- Domains Unique to Each Target (if any exist)
- Statistical Comparison
- Analysis and Implications
"""
    else:
        return f"""
We have individual backlink results from multiple targets. Your task is to:
1. First, check if each target has any backlinks data. If a target has no backlinks, clearly state this fact.
2. For targets with backlinks:
   - Identify EXACTLY which URLs link to both targets (the overlap)
   - Compare the anchor text used in overlapping backlinks
   - Compare the link types (DoFollow/NoFollow) in overlapping backlinks
   - List SPECIFICALLY which linking URLs are unique to each target
3. If one or both targets have no backlinks, explain what this might indicate
4. Analyze patterns in the differences (if applicable)

Here are the results to compare:

{results_text}

Please structure your response clearly with sections for:
- Data Availability (whether each target has backlink data)
- Overlapping Backlinks (if any exist)
- Unique Backlinks per Target (if any exist)
- Link Type Analysis (if applicable)
- Analysis and Implications
"""

def get_content_comparison_prompt(content: str, is_temporal: bool = False) -> str:
    """Get prompt for comparing website content."""
    if is_temporal:
        return f"""
Compare these two versions of the same content from different time periods.
Focus first on what has stayed the same, then note what has changed.
Be conversational and highlight anything interesting you notice.

{content}

Pay special attention to and ALWAYS note any overlap or differences in:
1. People mentioned
2. Companies/organizations mentioned
3. Locations mentioned

If there are multiple pages on either side:
1. First identify pages that serve similar purposes (e.g., contact pages, about pages)
2. Compare those similar pages specifically
3. Then give an overall comparison of how the sites differ

Please provide a brief, natural analysis focusing on:
1. Specific comparisons between similar pages you identified
2. Key content that appears in both versions, especially people, companies, and locations
3. Notable changes or differences
4. Any interesting patterns or evolution in the content
"""
    else:
        return f"""
Compare the content from these different sources.
Focus first on overlapping or similar content, then note key differences.
Be conversational and highlight anything interesting you notice.

{content}

Pay special attention to and ALWAYS note any overlap or differences in:
1. People mentioned
2. Companies/organizations mentioned
3. Locations mentioned

If there are multiple pages on either side:
1. First identify pages that serve similar purposes (e.g., contact pages, about pages)
2. Compare those similar pages specifically
3. Then give an overall comparison of how the sites differ

Please provide a brief, natural analysis focusing on:
1. Specific comparisons between similar pages you identified
2. Overall similarities between the sources, especially people, companies, and locations
3. Key differences in what each source covers
4. Any interesting patterns or connections you notice

Keep your response conversational and prioritize the most interesting findings, but always include entity overlaps."""

def get_ner_comparison_prompt(search_type: str, content: str, is_temporal: bool = False) -> str:
    """Get prompt for comparing NER results."""
    if is_temporal:
        return f"""
We have run the following entity extraction: "{search_type}"

Below are entity extraction results from different time periods. Compare them, focusing on:
1. Which entities appear in both time periods
2. Which entities are unique to each period
3. Any patterns in how the entities have changed over time

{content}

Please be conversational and focus first on overlaps, then changes."""
    else:
        return f"""
We have run the following entity extraction: "{search_type}"

Below are entity extraction results from different targets. Your task is to:
1. Identify which entities appear in both targets (the overlap)
2. Note which entities are unique to each target
3. Point out any interesting patterns you notice

{content}

Please be conversational and focus first on overlaps, then differences."""

def get_ga_backlinks_comparison_prompt(results_text: str) -> str:
    """
    Generate a prompt for comparing backlinks with Google Analytics related domains.
    
    Args:
        results_text: The combined results containing backlinks and GA-connected domains
    """
    return f"""
We have backlinks data from one target and Google Analytics connected domains from another. Your task is to:
1. First, check the data availability for both sources
2. For the comparison:
   - Identify EXACTLY which domains appear in both lists (overlap between backlinks and GA-connected sites)
   - List SPECIFICALLY which domains are unique to the backlinks list
   - List SPECIFICALLY which domains are unique to the GA-connected sites list
3. Compare the total numbers between both lists
4. Analyze any patterns or relationships between the overlapping domains
5. Consider what the overlap (or lack thereof) might indicate about potential relationships between the sites

Here are the results to compare:

{results_text}

Please structure your response clearly with sections for:
- Data Availability (for both backlinks and GA-connected sites)
- Overlapping Domains (if any exist)
- Domains Unique to Backlinks List
- Domains Unique to GA-Connected Sites
- Statistical Comparison
- Analysis and Implications
""" 