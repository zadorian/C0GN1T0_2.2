"""
Specialized prompts for different AI comparison scenarios.
"""

import json
from typing import List, Dict, Any

# Main system prompt for vision analysis
MAIN_SYSTEM_PROMPT = """You are a helpful AI assistant that can see and analyze screen content. Please describe what you see in a clear, concise manner. Focus on:
1. The main content and purpose of what's visible
2. Any important text, images, or UI elements
3. The layout and organization of the content
Be direct and factual in your observations."""

# Constants for user messages
WELCOME_MESSAGE = """
Welcome to the Company Network Analyzer
=====================================
This tool will help you analyze company networks and relationships.
"""

RATE_LIMIT_MESSAGE = """
Rate limit reached. Please wait a moment before trying again.
"""

DAILY_LIMIT_MESSAGE = """
Daily API limit reached. Please try again tomorrow.
"""

NO_RESULTS_MESSAGE = """
No results found. Please try a different search term.
"""

MULTIPLE_RESULTS_MESSAGE = """
Multiple companies found. Please select the target company:
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

def get_social_media_analysis_prompt(query: str, tweets: list) -> str:
    """
    Generate a prompt for analyzing social media content.
    
    Args:
        query: The search term/phrase
        tweets: List of tweet dictionaries containing url, date, text, and score
    """
    return f"""
Analyze these tweets about "{query}". Structure your analysis into these specific sections:

1. TOPICAL CONTEXT
- What's the dominant context in which {query} is mentioned?
- Are there specific events, news, or trends driving the discussion?
- Quote specific tweets that demonstrate the main contexts

2. SENTIMENT ANALYSIS
- What's the overall mood/tone around {query}?
- Is there a clear positive/negative bias?
- Support with specific tweet quotes showing emotional language or reactions
- Note any regional or demographic variations in sentiment

3. RECENT TRENDS
- What are the most recent tweets about?
- Is there a shift in how {query} is being discussed?
- Quote the most recent relevant tweets and explain their significance

4. TYPICAL CONTENT
- What's the most common type of content about {query}?
- How many tweets deviate significantly from this pattern?
- Provide examples of both typical and standout tweets
- Note any recurring themes or narratives

5. ENGAGEMENT PATTERNS
- Who is tweeting about {query}? (journalists, politicians, public, corporations)
- Are there verified accounts or notable figures?
- What's the mix of institutional vs personal accounts?
- Note any patterns in nationality or language
- Are the accounts using real names or anonymous handles?
- Include specific examples of influential or representative accounts

Use direct quotes from tweets to support each point. For each quote, include:
- The URL for reference
- The date of the tweet
- The relevant text excerpt

Here are the tweets to analyze:
{json.dumps(tweets, indent=2)}

Focus on evidence-based analysis and always cite specific tweets to support your observations.
"""

def get_brand_analysis_prompt(company_name: str) -> str:
    """Generate a prompt for brand name extraction"""
    return f"""
Extract the core brand name from this company name: {company_name}

Rules:
1. Remove generic terms like "Ltd", "Limited", "Consulting", "Services"
2. Focus on the distinctive part of the name
3. Return NONE if no clear brand name exists
4. Return in UPPERCASE

Examples:
"Acme Solutions Ltd" -> "ACME"
"John Smith Consulting Limited" -> "JOHN SMITH"
"Generic Business Services Ltd" -> "NONE"

Return ONLY the brand name or NONE, no other text.
"""

def format_control_nature(control_list: List[str]) -> str:
    """Convert control nature codes into readable text"""
    control_map = {
        'ownership-of-shares-75-to-100-percent': 'Owns 75-100% of shares',
        'ownership-of-shares-50-to-75-percent': 'Owns 50-75% of shares',
        'ownership-of-shares-25-to-50-percent': 'Owns 25-50% of shares',
        'voting-rights-75-to-100-percent': 'Controls 75-100% of voting rights',
        'voting-rights-50-to-75-percent': 'Controls 50-75% of voting rights',
        'voting-rights-25-to-50-percent': 'Controls 25-50% of voting rights',
        'right-to-appoint-and-remove-directors': 'Can appoint/remove directors',
        'significant-influence-or-control': 'Has significant control'
    }
    
    return ', '.join(control_map.get(control, control) for control in control_list)

def get_address_significance_prompt(address: str, company_count: int) -> str:
    """Get prompt for analyzing if an address is a service address"""
    return f"""Analyze this address with {company_count} companies registered there:
    
    Address: {address}
    Number of companies: {company_count}
    
    Determine if this is likely a:
    1. Real operational address (few companies)
    2. Service/virtual office address (many companies)
    3. Professional services address (law firm, accountant)
    
    Return ONLY:
    REAL if it's likely a real operational address
    SERVICE if it's likely a service/virtual office
    PROFESSIONAL if it's likely a professional services firm"""

def get_relationship_analysis_prompt(data: Dict) -> str:
    """Generate a prompt for analyzing company relationships"""
    return f"""
Analyze these company relationships:

TARGET COMPANY:
{json.dumps(data['target_company'], indent=2)}

DIRECTOR SEARCH RESULTS:
{json.dumps(data['director_companies'], indent=2)}

BRAND SEARCH RESULTS:
{json.dumps(data['brand_companies'], indent=2)}

ADDRESS SEARCH RESULTS:
{json.dumps(data['address_companies'], indent=2)}
Address type: {data['address_type']}

RELATIONSHIP RULES:
1. HIGH PRIORITY - Companies with ANY TWO OR MORE of:
   - Shared current directors (must verify exact name match)
   - Similar brand name to target company
   - Same address (if not a service address)
   
2. MEDIUM PRIORITY - Companies with ONE strong connection:
   - Multiple shared current directors
   - Exact brand match
   - Same address (if only few companies share it)
   
3. LOW PRIORITY - Companies with ONE weaker connection:
   - Single shared director
   - Similar business type words only
   - Same address (if many companies share it)

IMPORTANT:
- Director matches must be exact name matches, not partial matches
- Address matches alone should be lowest priority if it's a service address
- Ignore generic business words like "CONSULTING", "LIMITED", "LTD"

Structure your response EXACTLY like this:

RELATED ENTITIES:

HIGH PRIORITY:
[List each company with 2+ verified shared dimensions]
- Company Name (Number)
  * Shared Dimensions: [list the specific shared properties]

MEDIUM PRIORITY:
[List each company with 1 strong verified connection]
- Company Name (Number)
  * Connection: [describe the specific strong connection]

LOW PRIORITY:
[List each company with 1 weak connection]
- Company Name (Number)
  * Connection: [describe the weak connection]

NOTES:
[Only if needed: notes about address being a service address, name being too generic, etc.]"""

def get_ownership_analysis_prompt(text: str, company_name: str, doc_date: str, doc_type: str) -> str:
    """Generate a focused prompt for analyzing Companies House beneficial ownership documents"""
    return f"""
Analyze this Companies House filing for beneficial ownership information.
Return a valid JSON object showing the ownership structure.

Company: {company_name}
Document: {doc_type} filed on {doc_date}

Document text:
{text}

Return ONLY a valid JSON object in this EXACT format:
{{
    "owners": [
        {{
            "name": "string",  // Person or company name
            "type": "individual|corporate|other",  // Type of owner
            "percentage": number|null,  // Ownership percentage or null if unknown
            "shares": string|null,      // Number of shares or null if unknown
            "nature_of_control": [      // List of control types from document
                "ownership-of-shares-25-to-50-percent",
                "voting-rights-25-to-50-percent",
                "right-to-appoint-remove-directors",
                etc...
            ],
            "details": {{               // Additional details if available
                "nationality": string|null,
                "country_of_residence": string|null,
                "company_number": string|null,  // For corporate owners
                "incorporation_country": string|null  // For corporate owners
            }}
        }}
    ],
    "total_shares": string|null,  // Total shares in company or null if unknown
    "share_classes": [            // List of share classes if specified
        {{
            "class": "string",    // e.g., "Ordinary"
            "number": "string",   // Number of shares in this class
            "currency": "string", // e.g., "GBP"
            "value": "string"     // Nominal value per share
        }}
    ],
    "doc_date": "{doc_date}",
    "doc_type": "{doc_type}"
}}

If no ownership information is found, return:
{{
    "owners": [],
    "total_shares": null,
    "share_classes": [],
    "doc_date": "{doc_date}",
    "doc_type": "{doc_type}"
}}

Return ONLY the JSON object, no other text."""

def get_ownership_history_prompt(documents: str) -> str:
    """Generate a prompt for analyzing chronological beneficial ownership history"""
    return f"""
Analyze these Companies House filings and create a chronological record of beneficial ownership changes.
Return a valid JSON object showing the ownership history.

Documents to analyze:
{documents}

Return ONLY a valid JSON object in this EXACT format:
{{
    "changes": [
        {{
            "date": "YYYY-MM-DD",
            "events": [
                {{
                    "name": "string",  // Person or company name
                    "type": "individual|corporate|other",
                    "action": "gained|lost|modified",
                    "percentage": number|null,
                    "shares": string|null,
                    "nature_of_control": [
                        "ownership-of-shares-25-to-50-percent",
                        "voting-rights-25-to-50-percent",
                        etc...
                    ],
                    "details": {{
                        "nationality": string|null,
                        "country_of_residence": string|null,
                        "company_number": string|null,
                        "incorporation_country": string|null
                    }}
                }}
            ],
            "total_shares_after": string|null
        }}
    ],
    "current_ownership": [
        {{
            "name": "string",
            "type": "individual|corporate|other",
            "percentage": number|null,
            "shares": string|null,
            "nature_of_control": [...],
            "details": {{...}}
        }}
    ],
    "total_shares": string|null,
    "share_classes": [
        {{
            "class": "string",
            "number": "string",
            "currency": "string",
            "value": "string"
        }}
    ]
}}

Return ONLY the JSON object, no other text."""

def get_beneficial_ownership_analysis_prompt(text: str, company_name: str, doc_date: str, doc_type: str) -> str:
    """Generate a prompt specifically for beneficial ownership (PSC) analysis"""
    return f"""
Analyze this Companies House filing for persons with significant control (PSC) and beneficial ownership.
Return a valid JSON object showing the beneficial ownership structure.

Company: {company_name}
Document: {doc_type} filed on {doc_date}

Document text:
{text}

Return ONLY a valid JSON object in this EXACT format:
{{
    "beneficial_owners": [
        {{
            "name": "string",
            "type": "individual|corporate|legal_entity|government|trust",
            "nature_of_control": [
                "ownership-of-shares-25-to-50-percent",
                "ownership-of-shares-50-to-75-percent",
                "ownership-of-shares-75-to-100-percent",
                "voting-rights-25-to-50-percent",
                "voting-rights-50-to-75-percent",
                "voting-rights-75-to-100-percent",
                "right-to-appoint-remove-directors",
                "significant-influence-or-control"
            ],
            "details": {{
                "nationality": string|null,
                "country_of_residence": string|null,
                "company_number": string|null,
                "registration_country": string|null,
                "legal_form": string|null,
                "governing_law": string|null,
                "start_date": "YYYY-MM-DD"|null,
                "ceased_date": "YYYY-MM-DD"|null
            }}
        }}
    ],
    "doc_date": "{doc_date}",
    "doc_type": "{doc_type}",
    "notification_date": "YYYY-MM-DD"|null
}}

If no PSC/beneficial ownership information is found, return:
{{
    "beneficial_owners": [],
    "doc_date": "{doc_date}",
    "doc_type": "{doc_type}",
    "notification_date": null
}}

Return ONLY the JSON object, no other text."""

def get_beneficial_ownership_history_prompt(documents: str) -> str:
    """Generate a prompt for analyzing beneficial ownership history"""
    return f"""
Analyze these Companies House filings and create a chronological record of PSC/beneficial ownership changes.
Return a valid JSON object showing the beneficial ownership history.

Documents to analyze:
{documents}

Return ONLY a valid JSON object in this EXACT format:
{{
    "changes": [
        {{
            "date": "YYYY-MM-DD",
            "notification_date": "YYYY-MM-DD"|null,
            "events": [
                {{
                    "name": "string",
                    "type": "individual|corporate|legal_entity|government|trust",
                    "action": "appointed|ceased|changed",
                    "nature_of_control": [
                        "ownership-of-shares-25-to-50-percent",
                        "voting-rights-25-to-50-percent",
                        etc...
                    ],
                    "details": {{
                        "nationality": string|null,
                        "country_of_residence": string|null,
                        "company_number": string|null,
                        "registration_country": string|null,
                        "legal_form": string|null,
                        "governing_law": string|null
                    }}
                }}
            ]
        }}
    ],
    "current_beneficial_owners": [
        {{
            "name": "string",
            "type": "individual|corporate|legal_entity|government|trust",
            "nature_of_control": [...],
            "details": {{...}}
        }}
    ]
}}

Return ONLY the JSON object, no other text."""

def get_corporate_owners_prompt(ownership_text: str) -> str:
    """Generate a prompt for extracting corporate owners from ownership text"""
    return f"""
Extract ALL corporate/company owners from this ownership structure.
Return in JSON format like:
{{
    "corporate_owners": [
        {{"name": "COMPANY NAME", "percentage": "XX%"}}
    ]
}}

Ownership structure to analyze:
{ownership_text}

Return ONLY the JSON object, no other text."""

def get_ownership_chain_summary_prompt(chain_data: str) -> str:
    """Generate a prompt for summarizing the complete ownership chain"""
    return f"""
Analyze this ownership chain data and provide a clear summary of the complete ownership structure.
Show the relationships between companies and their ownership percentages in a clear, hierarchical format.

Chain data:
{chain_data}

Return a clear, structured summary showing who owns what, with percentages.
Focus on making the ownership chain and corporate relationships clear.
Use indentation or bullet points to show the hierarchy.
"""

def get_ownership_structure_prompt(file_path: str) -> str:
    """Get prompt for extracting structured ownership data from a Companies House filing"""
    return """You are a JSON API. Your ONLY purpose is to extract ownership information and return it in this EXACT format:
{
    "owners": [
        {
            "name": "COMPANY NAME",
            "type": "corporate",
            "percentage": 75,
            "shares": null,
            "nature_of_control": ["ownership-of-shares-75-to-100-percent"],
            "details": {
                "company_number": "12345678",
                "incorporation_country": "ENGLAND"
            }
        }
    ]
}

DO NOT include any explanatory text, summaries, or analysis.
DO NOT wrap the JSON in backticks or quotes.
ONLY return the raw JSON object.

If no ownership information is found, return:
{
    "owners": []
}"""

def get_psc_ownership_prompt(file_path: str) -> str:
    """Get prompt for extracting PSC (Person with Significant Control) data"""
    return """You are a JSON API endpoint. You ONLY return valid JSON objects, never explanatory text.
Your ONLY purpose is to extract PSC information and return it in this EXACT format:

{
    "owners": [
        {
            "name": "COMPANY NAME",
            "type": "corporate",
            "percentage": 75,
            "nature_of_control": [
                "ownership-of-shares-75-to-100-percent",
                "voting-rights-75-to-100-percent"
            ],
            "details": {
                "company_number": "12345678",
                "registration_country": "ENGLAND",
                "legal_form": "LTD",
                "governing_law": "COMPANIES ACT 2006",
                "notification_date": "2020-09-09"
            }
        }
    ],
    "doc_date": "2020-09-08",
    "doc_type": "PSC02"
}

Rules:
1. ONLY return the JSON object
2. NO explanatory text or summaries
3. NO backticks or quotes around the JSON
4. If no ownership found, return {"owners": []}
5. Valid nature_of_control values:
   - ownership-of-shares-25-to-50-percent
   - ownership-of-shares-50-to-75-percent
   - ownership-of-shares-75-to-100-percent
   - voting-rights-25-to-50-percent
   - voting-rights-50-to-75-percent
   - voting-rights-75-to-100-percent
   - right-to-appoint-remove-directors
   - significant-influence-or-control
6. Valid type values:
   - individual
   - corporate
   - legal_entity
   - government
   - trust

This is a machine interface. Human-readable text will cause errors."""

def get_financial_report_prompt(pdf_base64: str) -> str:
    """
    Generate a prompt for summarizing a financial report from Companies House.
    The user specifically wants:
      1) Key financial information (like turnover, profit, assets, liabilities, etc.)
      2) Any individuals mentioned and the context
      3) Any companies mentioned and their relationship to the target
      4) Any references to legal proceedings or potential adverse info
    We'll embed the base64 PDF in the prompt as 'document'.
    """
    return f"""
You are analyzing a Companies House financial report.
The base64-encoded PDF is below. Summarize it focusing on:
1) Key financial figures (turnover, profits, net assets, liabilities, etc.)
2) Any individuals mentioned (directors, auditors, etc.) and the context
3) Any companies mentioned, especially if there's a group relationship or intercompany dealings
4) Any references to legal proceedings or potential adverse info

Return a concise textual summary. 
Do NOT provide disclaimers. 
Output only the analysis, no JSON.

DOCUMENT (base64 PDF):
{pdf_base64}
"""

def get_company_network_analysis_prompt(network_data: Dict) -> str:
    return f"""
    Analyze this corporate network data to identify ALL meaningful connections and patterns.
    Compare ALL lists against each other to find overlaps and relationships.

    TARGET COMPANY:
    {json.dumps(network_data['target_company'], indent=2)}

    INITIAL SEARCH RESULTS:
    {json.dumps(network_data['initial_search_results'], indent=2)}

    BRAND-RELATED COMPANIES:
    {json.dumps(network_data['brand_companies'], indent=2)}

    COMPANIES AT SAME ADDRESS:
    {json.dumps(network_data['address_companies'], indent=2)}

    Your task is to analyze ALL possible connections between these companies and compare ALL lists against each other.

    1. LIST COMPARISON:
       - Compare each list against every other list to find overlaps
       - Identify companies that appear in multiple lists
       - Note which companies are unique to each list
       - Calculate overlap percentages between lists

    2. CROSS-REFERENCE ALL COMPANIES to find:
       - Shared directors (exact name matches only)
       - Shared beneficial owners
       - Address matches
       - Brand name similarities
       - Temporal patterns (dates of appointments, registrations)

    3. IDENTIFY CONNECTION PATTERNS:
       - Direct connections (same directors/owners)
       - Indirect connections (companies connected through intermediaries)
       - Temporal connections (sequential appointments or registrations)
       - Geographic connections (address patterns)
       - Brand family connections (similar names or naming patterns)

    4. MAP THE NETWORK STRUCTURE:
       - Central companies (most connections)
       - Subsidiary relationships
       - Sister company relationships
       - Control chains
       - Isolated entities

    5. FLAG SIGNIFICANT PATTERNS:
       - Multiple companies registered on same dates
       - Directors serving across multiple companies
       - Address patterns suggesting group structure
       - Brand name patterns suggesting related operations
       - Ownership structure complexity

    Format your response as:

    LIST OVERLAPS:
    [For each pair of lists, show:
     - Number of overlapping companies
     - Names of overlapping companies
     - Percentage overlap]

    DIRECT CONNECTIONS:
    [List each company with direct links to others, specifying exact shared properties]

    INDIRECT CONNECTIONS:
    [List companies connected through intermediaries, showing the connection chain]

    TEMPORAL PATTERNS:
    [List any significant timing patterns in registrations/appointments]

    NETWORK STRUCTURE:
    [Describe the overall network shape and key relationships]

    KEY FINDINGS:
    [List the most significant patterns and potential relationships discovered]

    IMPORTANT:
    - Verify ALL connections with specific evidence
    - Show the exact data points that support each connection
    - Include dates and specific details for all connections
    - Cross-reference ALL companies against each other
    - Calculate and show exact overlap statistics between lists
    """

def format_company_info(company: Dict, api: Any) -> str:
    """Format company information for display.
    
    Args:
        company (dict): Company data from OpenCorporates API
        api: OpenCorporates API instance for additional data fetching
    
    Returns:
        str: Formatted company information
    """
    company_data = company.get('company', {})
    
    # Basic company info
    formatted = f"""
Company: {company_data.get('name', 'Unknown')}
Number: {company_data.get('company_number', 'Unknown')}
Jurisdiction: {company_data.get('jurisdiction_code', 'Unknown').upper()}
Status: {company_data.get('current_status', 'Unknown')}
Address: {company_data.get('registered_address_in_full', 'Unknown')}"""

    # Try to get officers if available
    try:
        officers = api.get_company_officers(
            company_data.get('jurisdiction_code'),
            company_data.get('company_number')
        )
        
        if officers and 'results' in officers and 'officers' in officers['results']:
            formatted += "\n\nDirectors:"
            for officer in officers['results']['officers']:
                officer_data = officer.get('officer', {})
                formatted += f"\n- {officer_data.get('name', 'Unknown')}"
                formatted += f"\n  Position: {officer_data.get('position', 'Unknown')}"
                formatted += f"\n  Appointed: {officer_data.get('start_date', 'Unknown')}"
                if officer_data.get('end_date'):
                    formatted += f"\n  Ended: {officer_data.get('end_date')}"
    except Exception as e:
        formatted += f"\nError getting officers: {str(e)}"

    return formatted 

def get_company_summary_prompt() -> str:
    """Generate a prompt for comprehensive company website analysis"""
    return """Analyze this company's website content and provide a comprehensive summary focusing on:

1. Company History & Track Record:
   - Founding date and key milestones
   - Major developments and achievements

2. Business Activities:
   - Core products/services
   - Industry sectors
   - Key business lines

3. Geographical Presence:
   - Headquarters location
   - Operating regions/countries
   - Market coverage

4. Financial Performance:
   - Any public financial information
   - Growth indicators
   - Revenue/profit figures if available

5. Ownership & Management:
   - Company structure
   - Key executives
   - Board members
   - Parent company or subsidiaries

6. Risk Factors & Adverse Information:
   - Any regulatory issues
   - Legal proceedings
   - Negative press
   - Business risks
   - Compliance concerns

Be thorough and factual. Include specific dates and details when available.
If information in any category is not found, explicitly note its absence.
""" 