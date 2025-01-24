def get_ga_comparison_prompt(results_text: str) -> str:
    """Generate a prompt for comparing Google Analytics connected domains.
    
    Args:
        results_text: Text containing GA-connected sites for multiple domains
        
    Returns:
        A prompt string for the AI to analyze and compare the GA data
    """
    return f"""Please analyze the following Google Analytics connected domains and provide a detailed comparison:

{results_text}

Please structure your analysis as follows:

1. Data Availability
   - Note which domains have GA data available
   - Indicate if any domains are missing data

2. Overlapping Connections
   - List any GA codes or domains that appear in multiple results
   - For each overlap, specify which target domains share the connection

3. Unique Connections
   - For each target domain, list connections that are unique to it
   - Note any patterns in the unique connections

4. Statistical Comparison
   - Compare the number of GA connections per domain
   - Note if any domain has significantly more or fewer connections

5. Pattern Analysis
   - Identify any patterns in the types of connected domains
   - Note any geographical or industry-specific patterns
   - Highlight any interesting relationships or clusters of domains

Please be concise but thorough in your analysis. Focus on meaningful patterns and relationships rather than listing every single domain."""

def get_whois_comparison_prompt(results_text: str, comparison_type: str) -> str:
    """Generate a prompt for comparing WHOIS data with other types of data.
    
    Args:
        results_text: Text containing the data to compare (WHOIS + other data)
        comparison_type: Type of comparison (e.g., 'ner', 'ga', 'backlinks')
        
    Returns:
        A prompt string for the AI to analyze and compare the data
    """
    base_prompt = f"""Please analyze the following data and identify any meaningful relationships or connections:

{results_text}

Please structure your analysis as follows:

1. Data Overview
   - Summarize the WHOIS data available (registrant, organization, location, etc.)
   - Note any missing or redacted information

2. Direct Matches
   - Identify any exact matches between the WHOIS data and the comparison data
   - This includes names, organizations, addresses, or other identifiers
   - Highlight the specific matching elements

3. Partial Matches & Similarities
   - Note any partial matches or similar elements
   - This could include similar names, related addresses, or geographical proximity
   - Explain why these similarities might be significant

4. Contextual Analysis
   - Consider the broader context of any matches or similarities
   - Are there patterns that suggest a relationship?
   - Does the geographical or temporal data provide additional insights?

5. Confidence Assessment
   - Rate the strength of any identified connections
   - Explain what factors support or weaken these connections"""

    if comparison_type == "ner":
        base_prompt += """

For Entity Comparison:
- Pay special attention to person names and organization names
- Look for address matches or similarities
- Consider if extracted entities might be related to the registrant
- Note if entities appear to be from the same region or industry"""
    elif comparison_type == "ga":
        base_prompt += """

For Google Analytics Comparison:
- Check if the WHOIS registrant appears in the GA-connected sites
- Look for geographical patterns between registrant and connected sites
- Note if the organization name appears in connected domains"""
    elif comparison_type == "backlinks":
        base_prompt += """

For Backlinks Comparison:
- Check if the WHOIS registrant owns any of the linking domains
- Look for patterns in the geographical distribution
- Note if the organization name appears in referring domains"""

    base_prompt += """

Please be thorough but concise. Focus on meaningful connections and explain their significance."""
    return base_prompt 