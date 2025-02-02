import asyncio
from typing import Dict, List, Any
from search_engines.exa_exact import ExaSearchProcessor
from search_engines.socialsearcher import SocialSearcher
from AI_models.gemini_flash_1_5 import generate_with_retry
from website_searchers.report_generator import ExactStyleReportGenerator
from company_search.aleph_entities import AlephAPI, print_network_info
from company_search.aleph_doc_ocr import AlephPDFProcessor
from company_search.opencorporates import OpenCorporatesAPI, format_company_info
from website_searchers.ai_searcher import handle_ai_search_two_step
from scraping.current_scraping import content_controller
import json
from datetime import datetime
import os
from scraping.scrapers.firecrawl import get_content
from AI_models.visionintel import analyze_screen_silently
from pathlib import Path
import google.generativeai as genai
from config import config
from google_docs_footnotes import GoogleDocsFootnotes

class DueDiligenceReport:
    def __init__(self):
        """Initialize search engines and processors."""
        # Initialize search engines
        self.exa_search = ExaSearchProcessor()
        self.social_searcher = SocialSearcher()
        self.aleph_api = OpenCorporatesAPI()
        self.opencorporates_api = OpenCorporatesAPI()
        
        # Initialize report generator
        self.report_generator = ExactStyleReportGenerator()
        
        # Configure Gemini
        genai.configure(api_key=config.GEMINI_API_KEY)

        # Create necessary directories
        for directory in ["reports", "ingest", "company_documents", "aleph_data"]:
            os.makedirs(directory, exist_ok=True)

    def _format_report_header(self, query: str) -> str:
        """Format the report header following the template."""
        today = datetime.now().strftime("%d %B %Y")
        
        return f"""

SUBCONTRACTOR'S REPORT

Date report is completed: {today}

{query}

"""

    def _format_assignment_section(self, query: str) -> str:
        """Format the assignment section following the template."""
        today = datetime.now().strftime("%d %B %Y")
        
        return f"""A. ASSIGNMENT

I was given an assignment to conduct checks on the following subjects:

Date assigned: 
Date due: {today}
Country: 

Subject\tEntity type\tOther details\tScope
{query}\t\t\tGeneral and Full Negative Media Check

"""

    def _format_background_section(self, analysis: Dict) -> str:
        """Format the background section following the template."""
        background = analysis.get('sections', {}).get('COMPANY BACKGROUND INFORMATION', {})
        
        # Format company details table if available
        company_details = ""
        if background.get('Company Overview'):
            company_details = """
Company Background Details1

Name
Short Name
Business Addresses
Registration Number
Registered Capital
Company Type
Company Status
Telephone
Email
Corporate Website
Social Media
"""
        
        # Format shareholders table if available
        shareholders = ""
        if background.get('Key Personnel'):
            shareholders = """

Shareholder2

Name\tInvestment Amount (XX)\tPercentage (%)\tSearches Conducted
"""
        
        # Format management table if available
        management = """

Management

Name\tPosition\tIdentifier(s)\tSearches Conducted
"""
        
        # Format findings section
        findings = "\n\nGENERAL AND NEGATIVE MEDIA FINDINGS\n\n"
        
        # Combine all sections
        background_section = "B. BACKGROUND INFORMATION\n"
        background_section += company_details
        background_section += shareholders
        background_section += management
        background_section += findings
        
        return background_section

    def _format_findings_section(self, analysis: Dict) -> str:
        """Format the findings section with content from analysis."""
        sections = analysis.get('sections', {})
        background = sections.get('COMPANY BACKGROUND INFORMATION', {})
        
        content = []
        
        # Add overview
        if background.get('Company Overview'):
            content.append(background['Company Overview'])
            
        # Add operations
        if background.get('Operations'):
            content.append(background['Operations'])
            
        # Add key personnel
        if background.get('Key Personnel'):
            content.append(background['Key Personnel'])
            
        # Add financial info
        if background.get('Financial Information'):
            content.append(background['Financial Information'])
            
        # Add regulatory status
        if background.get('Regulatory Status'):
            content.append(background['Regulatory Status'])
            
        return "\n\n".join(content)

    def _format_sources(self, analysis: Dict) -> str:
        """Format the sources section following the template."""
        footnotes = analysis.get('footnotes', [])
        if not footnotes:
            return ""
            
        sources = []
        for i, footnote in enumerate(footnotes, 1):
            sources.append(f"{i} {footnote}")
            
        return "\n".join(sources)

    async def perform_aleph_searches(self, query: str) -> Dict:
        """Perform both Aleph entity and document searches"""
        print("\nPerforming Aleph searches...")
        results = {
            'entity_results': {},
            'document_results': [],
            'network_data': {}
        }

        try:
            print("\nSearching Aleph for entity information...")
            network = self.aleph_api.search_entity(query)
            if network:
                results['entity_results'] = network.get('entity', {})
                results['network_data'] = network
                
                # Get relationships if entity found
                if entity_id := network.get('entity', {}).get('id'):
                    print("\nGathering relationship data...")
                    relationships = self.aleph_api.get_entity_relationships(entity_id)
                    results['network_data']['relationships'] = relationships
                
                print("\nEntity information found in Aleph:")
                print_network_info(network)
            else:
                print("No entity information found in Aleph")

        except Exception as e:
            print(f"Error in Aleph entity search: {str(e)}")

        # Search for documents
        try:
            print("\nSearching Aleph for documents...")
            documents = await self.aleph_api.search_documents(query)
            if documents:
                print(f"Found {len(documents)} documents in Aleph")
                # Download and process documents
                for doc in documents[:5]:  # Limit to 5 documents
                    doc_info = await self.aleph_api.download_document(doc)
                    if doc_info:
                        await self.aleph_api.process_document(doc_info['path'])
                        results['document_results'].append({
                            'title': doc.get('properties', {}).get('title', ['Untitled'])[0],
                            'content': doc_info,
                            'metadata': doc
                        })
            else:
                print("No documents found in Aleph")
        except Exception as e:
            print(f"Error in Aleph document search: {str(e)}")

        return results

    async def perform_opencorporates_search(self, query: str) -> Dict:
        """Perform comprehensive OpenCorporates search"""
        print("\nSearching OpenCorporates...")
        results = {
            'company_results': [],
            'officer_results': [],
            'network_results': []
        }
        
        try:
            # 1. Search for companies
            print("Searching for company matches...")
            company_search = self.opencorporates_api.search_companies(query=query)
            if company_search and 'results' in company_search and 'companies' in company_search['results']:
                companies = company_search['results']['companies']
                print(f"Found {len(companies)} matching companies")
                
                # Get detailed info for each company
                for company in companies[:5]:  # Limit to top 5 matches
                    company_data = company['company']
                    jurisdiction = company_data.get('jurisdiction_code')
                    number = company_data.get('company_number')
                    
                    if jurisdiction and number:
                        # Get full company details
                        details = self.opencorporates_api.get_company_details(jurisdiction, number)
                        if details and 'results' in details:
                            formatted_info = format_company_info(details['results'], self.opencorporates_api)
                            results['company_results'].append({
                                'basic_info': company_data,
                                'detailed_info': details['results'],
                                'formatted_info': formatted_info
                            })
                            
                            # Get company network info
                            network = self.opencorporates_api.search_company_network(jurisdiction, number)
                            if network and 'results' in network:
                                results['network_results'].append({
                                    'company_name': company_data.get('name'),
                                    'network_data': network['results']
                                })
                            
                            # Get officers/directors
                            officers = self.opencorporates_api.search_officers(
                                jurisdiction_code=jurisdiction,
                                position="director"
                            )
                            if officers and 'results' in officers and 'officers' in officers['results']:
                                results['officer_results'].extend([
                                    {
                                        'company_name': company_data.get('name'),
                                        'officer_data': officer['officer']
                                    }
                                    for officer in officers['results']['officers']
                                    if officer['officer'].get('company_number') == number
                                ])
            
            print(f"Processed {len(results['company_results'])} companies with detailed information")
            if results['network_results']:
                print(f"Found corporate network information for {len(results['network_results'])} companies")
            if results['officer_results']:
                print(f"Found {len(results['officer_results'])} officers/directors")
                
            return results
            
        except Exception as e:
            print(f"Error in OpenCorporates search: {str(e)}")
            return results

    async def process_with_gemini(self, full_results: List[Dict], query: str) -> Dict:
        """Process results with Gemini to generate structured report."""
        try:
            # Combine all content for analysis
            combined_content = "\n\n".join([
                f"Source: {r.get('source_type', 'Unknown')}\n"
                f"Title: {r.get('title', '')}\n"
                f"Content: {r.get('full_content', '')}\n"
                f"URL: {r.get('url', '')}"
                for r in full_results
            ])

            # Load template and prepare prompt
            template_path = Path("template") / "Asia Pharma LLC.txt"
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()

            # Create prompt parts separately
            prompt_part1 = "Study this EXAMPLE REPORT format carefully:\n\n"
            prompt_part2 = "\n\nUsing the EXACT SAME STYLE AND FORMAT as this example report, analyze this content about "
            prompt_part3 = """

CRITICAL REQUIREMENTS:
1. Match the exact structure and formatting of the example
2. Include all sections in the same order
3. Use the same style for company details table
4. Follow the exact same footnoting system
5. Every fact must have a footnote with the source URL
6. Format dates and headers identically
7. Present findings in the same structured way

Your output must be valid JSON matching this structure:
{
    "sections": {
        "ASSIGNMENT": "string",
        "COMPANY_BACKGROUND_INFORMATION": {
            "Company_Overview": "string",
            "Key_Personnel": "string",
            "Operations": "string",
            "Financial_Information": "string",
            "Regulatory_Status": "string"
        }
    },
    "footnotes": [
        "string (full source URLs)"
    ]
}"""

            # Combine prompt parts without nested f-strings
            prompt = prompt_part1 + template + prompt_part2 + query + ":\n\n" + combined_content + prompt_part3

            # Generate report with Gemini
            report_json = await generate_with_retry(
                prompt,
                temperature=0.3,
                json_response=True
            )

            if not report_json:
                raise Exception("Failed to generate report")

            try:
                # Parse the JSON response
                report_data = json.loads(report_json)
                
                # Save JSON report
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_path = Path(f"{query.replace(' ', '_')}_{timestamp}_report.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(report_data, f, indent=2)
                
                # Save text report
                report_path = Path(f"{query.replace(' ', '_')}_{timestamp}_report.txt")
                with open(report_path, 'w', encoding='utf-8') as f:
                    # Write Assignment section
                    f.write("A. ASSIGNMENT\n\n")
                    f.write(f"{report_data['sections']['ASSIGNMENT']}\n\n")
                    
                    # Write Background Information section
                    f.write("B. BACKGROUND INFORMATION\n\n")
                    background = report_data['sections']['COMPANY_BACKGROUND_INFORMATION']
                    for subsection, content in background.items():
                        f.write(f"### {subsection}\n")
                        f.write(f"{content}\n\n")
                    
                    # Write Sources
                    if 'footnotes' in report_data:
                        f.write("\nSOURCES:\n")
                        for i, footnote in enumerate(report_data['footnotes'], 1):
                            f.write(f"[{i}] {footnote}\n")

                # Create Google Doc
                gdoc = GoogleDocsFootnotes()
                doc_url = gdoc.create_doc_from_template(
                    title=f"Due Diligence Report - {query}",
                    assignment=report_data['sections']['ASSIGNMENT'],
                    background_info=report_data['sections']['COMPANY_BACKGROUND_INFORMATION'],
                    footnotes=report_data['footnotes']
                )

                return {
                    'json_path': str(json_path),
                    'report_path': str(report_path),
                    'google_doc': doc_url if doc_url else None
                }

            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse response as JSON: {e}")
                # Save raw response as text
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = Path(f"{query.replace(' ', '_')}_{timestamp}_report.txt")
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_json)
                return {'report_path': str(report_path)}

        except Exception as e:
            print(f"Error processing with Gemini: {str(e)}")
            raise

    async def search_and_analyze(self, query: str):
        """Search and analyze a single query with simplified content retrieval."""
        try:
            print(f"\nSearching for: {query}")
            
            # 1. Perform searches across all sources
            web_results = await self.search_web(query)
            social_results = await self.search_social(query)
            exa_results = await self.exa_search.process_query(query)
            aleph_results = await self.perform_aleph_searches(query)
            opencorp_results = await self.perform_opencorporates_search(query)
            
            # Combine all results
            all_results = []
            if web_results: all_results.extend(web_results)
            if social_results: all_results.extend(social_results)
            if exa_results: all_results.extend(exa_results)
            if aleph_results: all_results.extend(aleph_results)
            if opencorp_results: all_results.extend(opencorp_results)
            
            if not all_results:
                print("No results found.")
                return None
            
            # Sort and filter URLs for analysis
            urls_to_analyze = self.filter_urls(all_results)
            
            print("\nRetrieving full content from selected URLs...")
            
            full_results = []
            for url_info in urls_to_analyze:
                try:
                    print(f"\nProcessing: {url_info['title']}")
                    print(f"URL: {url_info['url']}")
                    source_type = url_info.get('source_type', 'web')
                    
                    # Handle different source types
                    if source_type in ['social', 'exa', 'aleph', 'opencorporates']:
                        result = url_info['result']
                        result['full_content'] = result.get('content', result.get('snippet', ''))
                        result['source_type'] = source_type.capitalize()
                        full_results.append(result)
                        print(f"✓ {source_type.capitalize()} content retrieved")
                        continue
                    
                    # For web content, try FireCrawl first
                    try:
                        content_data = await get_content(url_info['url'])
                        if content_data and content_data.get('pages'):
                            result = url_info['result']
                            result['full_content'] = content_data['pages'][0]['content']
                            result['source_type'] = 'FireCrawl'
                            full_results.append(result)
                            print("✓ FireCrawl successful")
                            continue
                    except Exception as e:
                        print(f"× FireCrawl failed: {str(e)}")
                    
                    # If FireCrawl fails, try vision analysis
                    print("Attempting vision analysis...")
                    try:
                        # Open URL in default browser for screenshot
                        import webbrowser
                        webbrowser.open(url_info['url'])
                        
                        # Wait for page to load (you might want to adjust this)
                        import time
                        time.sleep(5)  # Wait 5 seconds for page load
                        
                        # Capture and analyze screen
                        vision_content = analyze_screen_silently(model="gemini")
                        if vision_content:
                            result = url_info['result']
                            result['full_content'] = vision_content
                            result['source_type'] = 'Vision Analysis'
                            full_results.append(result)
                            print("✓ Vision analysis successful")
                        else:
                            print("× Vision analysis failed - no content returned")
                    except Exception as e:
                        print(f"× Vision analysis error: {str(e)}")
                    
                except Exception as url_error:
                    print(f"! Error processing URL {url_info['url']}: {str(url_error)}")
                    continue

            # Generate final report using Gemini
            if full_results:
                print(f"\nSuccessfully retrieved content from {len(full_results)} sources:")
                print(f"- Web (FireCrawl): {sum(1 for r in full_results if r['source_type'] == 'FireCrawl')}")
                print(f"- Web (Vision): {sum(1 for r in full_results if r['source_type'] == 'Vision Analysis')}")
                print(f"- Social media: {sum(1 for r in full_results if r['source_type'] == 'Social')}")
                print(f"- Exa: {sum(1 for r in full_results if r['source_type'] == 'Exa')}")
                print(f"- Aleph: {sum(1 for r in full_results if r['source_type'] == 'Aleph')}")
                print(f"- OpenCorporates: {sum(1 for r in full_results if r['source_type'] == 'Opencorporates')}")
                print("\nGenerating final report...")
                analysis = await self.process_with_gemini(full_results, query)
                return analysis
            else:
                print("\n⚠ No content could be retrieved for analysis.")
                return None

        except Exception as e:
            print(f"\n⚠ Error during search and analysis: {str(e)}")
            return None

    async def search_occrp(self, query: str) -> List[Dict]:
        """Search OCCRP database."""
        try:
            print("Searching OCCRP...")
            # Implement OCCRP search here
            # Return results with source_type: 'occrp'
            occrp_results = []  # Your OCCRP implementation
            return occrp_results
        except Exception as e:
            print(f"OCCRP search error: {str(e)}")
            return []

    async def search_web(self, query: str) -> List[Dict]:
        """Search using web search engines."""
        try:
            print("Searching web sources...")
            results = []
            
            # Exa search
            exa_results = await self.exa_search.process_query(query)
            if exa_results:
                results.extend(exa_results)
            
            return results
        except Exception as e:
            print(f"Web search error: {str(e)}")
            return []

    async def search_social(self, query: str) -> List[Dict]:
        """Search social media platforms."""
        try:
            print("Searching social media...")
            results = self.social_searcher.search(query)
            return results if results else []
        except Exception as e:
            print(f"Social media search error: {str(e)}")
            return []

    async def search_aleph(self, query: str) -> List[Dict]:
        """Search OCCRP Aleph database."""
        try:
            print("Searching OCCRP Aleph...")
            results = await self.aleph_api.search_entities(query)
            return results if results else []
        except Exception as e:
            print(f"Aleph search error: {str(e)}")
            return []

    async def search_opencorporates(self, query: str) -> List[Dict]:
        """Search OpenCorporates database."""
        try:
            print("Searching OpenCorporates...")
            results = await self.opencorporates_api.search_companies(query)
            return results if results else []
        except Exception as e:
            print(f"OpenCorporates search error: {str(e)}")
            return []

async def main():
    print("\nDue Diligence Report Generator")
    print("============================")
    
    while True:
        query = input("\nEnter company name (or 'quit' to exit): ").strip()
        if query.lower() == 'quit':
            break
            
        if not query:
            print("Company name cannot be empty")
            continue
            
        try:
            searcher = DueDiligenceReport()
            await searcher.search_and_analyze(query)
                
        except Exception as e:
            print(f"Error: {str(e)}")
            continue
            
        print("\nReady for next company...")
    
    print("\nGoodbye!")

if __name__ == "__main__":
    asyncio.run(main()) 