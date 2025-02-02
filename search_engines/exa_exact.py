import os
from exa_py import Exa
from datetime import datetime
import json
from dotenv import load_dotenv
from pathlib import Path
import asyncio
from typing import Dict, List, Optional, Union
from AI_models.gemini_flash_1_5 import generate_with_retry
from google_docs_footnotes import GoogleDocsFootnotes

# Load environment variables
load_dotenv()

class ExaSearchProcessor:
    def __init__(self):
        """Initialize the Exa search and report processor."""
        # Initialize Exa client
        self.exa = Exa(os.getenv('EXA_API_KEY'))
        
        # Set up directories
        self.root_dir = Path(__file__).parent.parent
        self.ingest_dir = Path("ingest")
        self.output_dir = self.root_dir / "processed_documents"
        self.ingest_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Load template
        template_path = self.root_dir / "template" / "Asia Pharma LLC.txt"
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()
            
        # Load Google Docs template
        self.google_docs_template = "template/Subcontractor Report Template - final 1.docx"

    async def process_query(self, query: str) -> Dict[str, str]:
        """
        Perform complete search and processing workflow for a query.
        
        Args:
            query (str): The search query to process
            
        Returns:
            Dict[str, str]: Paths to output files
        """
        try:
            # 1. Perform Exa search
            search_results = await self._perform_search(query)
            
            # 2. Process results with Gemini
            processed_report = await self._process_with_gemini(search_results, query)
            
            # 3. Save outputs and create Google Doc
            outputs = self._save_outputs(processed_report, query)
            
            return outputs
            
        except Exception as e:
            print(f"Error processing query: {str(e)}")
            raise

    async def _perform_search(self, query: str) -> List[Dict]:
        """Perform Exa search with enhanced parameters."""
        print(f"\nPerforming search for: {query}")
        print("----------------------------------------")

        # Define business/media domains for better coverage
        news_domains = [
            "reuters.com", "apnews.com", "bloomberg.com", 
            "wsj.com", "nytimes.com", "ft.com",
            "cnn.com", "bbc.com", "theguardian.com"
        ]
        
        # Perform two separate searches
        search_results = []
        
        # 1. Company Search
        print("\nPerforming company search...")
        company_response = self.exa.search_and_contents(
            f'"{query}" (company OR corporation OR inc OR ltd)',
            type="keyword",
            use_autoprompt=False,
            num_results=10,
            highlights={"num_sentences": 5, "highlights_per_url": 5},
            text=True
        )
        search_results.extend([{
            "result_type": "company",
            "url": result.url,
            "title": result.title,
            "text": result.text,
            "highlights": result.highlights if hasattr(result, "highlights") else [],
            "published_date": result.published_date,
            "source_type": result.url.split('.')[-2] if '.' in result.url else 'Unknown'
        } for result in company_response.results])
        
        # 2. Media Search
        print("Performing media search...")
        media_response = self.exa.search_and_contents(
            f'"{query}"',
            type="keyword",
            use_autoprompt=False,
            num_results=10,
            highlights={"num_sentences": 5, "highlights_per_url": 5},
            text=True,
            include_domains=news_domains
        )
        search_results.extend([{
            "result_type": "media",
            "url": result.url,
            "title": result.title,
            "text": result.text,
            "highlights": result.highlights if hasattr(result, "highlights") else [],
            "published_date": result.published_date,
            "source_type": result.url.split('.')[-2] if '.' in result.url else 'Unknown'
        } for result in media_response.results])
        
        # Save raw results
        self._save_raw_results(search_results, query)
        
        return search_results

    def _save_raw_results(self, results: List[Dict], query: str) -> str:
        """Save raw search results to ingest directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c if c.isalnum() else "_" for c in query[:50])
        filename = f"{timestamp}_{safe_query}.json"
        filepath = self.ingest_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print(f"\nRaw search results saved to: {filepath}")
        print(f"Found {len(results)} total results:")
        print(f"- Company results: {sum(1 for r in results if r['result_type'] == 'company')}")
        print(f"- Media results: {sum(1 for r in results if r['result_type'] == 'media')}")
        
        return str(filepath)

    async def _process_with_gemini(self, results: List[Dict], query: str) -> Dict:
        """Process search results using Gemini."""
        print("\nProcessing results with Gemini...")
        
        # Prepare content for Gemini
        combined_text = self._prepare_search_results(results)
        
        # Create prompt
        prompt = f"""Analyze these search results and create a report following this template structure:

{self.template}

Search results to analyze:

{combined_text}

Important instructions:
1. Use the EXACT same section headings and structure as the template
2. Maintain professional tone and detail level
3. If a section would be empty, include it but state "No information available"
4. Format dates and numbers consistently
5. Include source citations
6. This is research about {query}
7. Return in JSON format:
{{
  "sections": {{
    "ASSIGNMENT": "string",
    "COMPANY BACKGROUND INFORMATION": {{
      "Company Overview": "string",
      "Key Personnel": "string",
      "Operations": "string",
      "Financial Information": "string",
      "Regulatory Status": "string"
    }}
  }},
  "footnotes": ["string"]
}}"""

        # Get Gemini's response
        response = generate_with_retry(prompt, temperature=0.3)
        
        if response:
            try:
                structured_response = json.loads(response)
            except json.JSONDecodeError:
                print("Warning: Could not parse response as JSON")
                structured_response = {"sections": {"raw": response}}
        else:
            structured_response = {}
            
        return {
            'metadata': {
                'processed_datetime': datetime.now().isoformat(),
                'model': 'gemini-pro',
                'template_used': 'Asia Pharma LLC template'
            },
            'report': structured_response,
            'raw_results': results
        }

    def _prepare_search_results(self, results: List[Dict]) -> str:
        """Format search results for Gemini's analysis."""
        formatted_results = []
        for result in results:
            formatted_result = (
                f"Type: {result['result_type'].upper()}\n"
                f"Title: {result['title']}\n"
                f"Source: {result['source_type']}\n"
                f"URL: {result['url']}\n"
                f"Date: {result['published_date']}\n\n"
                f"{result['text']}\n"
            )
            formatted_results.append(formatted_result)
            
        return "\n\n".join(formatted_results)

    def _save_outputs(self, processed_data: Dict, query: str) -> Dict[str, str]:
        """Save all outputs and create Google Doc."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = "".join(c if c.isalnum() else "_" for c in query[:50])
            outputs = {}

            # Save JSON
            json_path = self.output_dir / f"{safe_query}_{timestamp}_report.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
            outputs['json'] = str(json_path)

            # Save formatted report
            report_path = self.output_dir / f"{safe_query}_{timestamp}_report.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                self._write_report(f, processed_data['report'])

            outputs['report'] = str(report_path)

            # Create Google Doc
            try:
                print("\nCreating Google Doc...")
                gdocs = GoogleDocsFootnotes(self.google_docs_template)
                doc_url = gdocs.create_doc_from_template(
                    title=f"Search Report - {query}",
                    sections=processed_data['report']['sections']
                )
                outputs['google_doc'] = doc_url
                print(f"Created Google Doc: {doc_url}")
            except Exception as e:
                print(f"Error creating Google Doc: {str(e)}")
            
            print("\nSaved files:")
            print(f"1. Structured JSON: {json_path.name}")
            print(f"2. Formatted Report: {report_path.name}")

            return outputs

        except Exception as e:
            print(f"Error saving outputs: {str(e)}")
            raise

    def _write_report(self, file, report: Dict):
        """Write formatted report to file."""
        sections = report.get('sections', {})
        
        # Write Assignment section
        file.write("A. ASSIGNMENT\n\n")
        file.write(f"{sections.get('ASSIGNMENT', 'No assignment information available')}\n\n")
        
        # Write Background Information section
        file.write("B. BACKGROUND INFORMATION\n\n")
        background = sections.get('COMPANY BACKGROUND INFORMATION', {})
        for subsection, content in background.items():
            file.write(f"### {subsection}\n")
            file.write(f"{content}\n\n")
            
        # Write Sources
        footnotes = report.get('footnotes', [])
        if footnotes:
            file.write("\nSOURCES:\n")
            for i, footnote in enumerate(footnotes, 1):
                file.write(f"[{i}] {footnote}\n")

async def main():
    """Main execution function."""
    print("\nExa Search and Report Generator")
    print("==============================")
    
    # Get search query
    query = input("\nEnter your search query: ").strip()
    if not query:
        print("Error: Search query cannot be empty")
        return
        
    # Process query
    processor = ExaSearchProcessor()
    outputs = await processor.process_query(query)
    
    print("\nProcessing complete!")
    if 'google_doc' in outputs:
        print(f"\nView your report at: {outputs['google_doc']}")

if __name__ == "__main__":
    asyncio.run(main())