import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import json
from datetime import datetime
from anthropic import Anthropic
import io
from PyPDF2 import PdfReader, PdfWriter
from google_docs_footnotes import GoogleDocsFootnotes

class ReportProcessor:
    def __init__(self, template_path: Optional[str] = None, google_docs_template: Optional[str] = None):
        """Initialize the report processor with template and output paths."""
        self.root_dir = Path(__file__).parent.parent
        self.output_dir = self.root_dir / "processed_documents"
        self.output_dir.mkdir(exist_ok=True)
        
        # Load text template for Claude
        template_path = template_path or (self.root_dir / "template" / "Asia Pharma LLC.txt")
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()
            
        # Store Google Docs template path
        self.google_docs_template = google_docs_template or "template/Subcontractor Report Template - final 1.docx"
            
        # Initialize Anthropic client
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-sonnet-20240229"
        self.max_tokens = 4096
        self.max_pages_per_chunk = 25

    def _split_pdf(self, pdf_bytes: bytes) -> list[bytes]:
        """Split PDF into smaller chunks."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        total_pages = len(reader)
        chunks = []
        
        for start in range(0, total_pages, self.max_pages_per_chunk):
            end = min(start + self.max_pages_per_chunk, total_pages)
            writer = PdfWriter()
            
            for page_num in range(start, end):
                writer.add_page(reader.pages[page_num])
            
            output = io.BytesIO()
            writer.write(output)
            chunks.append(output.getvalue())
            
        return chunks

    async def process_results(self, results: List[Dict], query: str, source_type: str = "dd_report") -> Dict:
        """Process search results into a structured report using Claude."""
        try:
            # Prepare the content for Claude based on source type
            if source_type == "clipboard_image":
                combined_text = self._prepare_image_results(results)
            else:  # dd_report or other sources
                combined_text = self._prepare_search_results(results)
            
            # Create prompt for Claude
            prompt = f"""Please analyze the following {source_type} results and create a report following EXACTLY the same structure, sections, and formatting style as this template:

{self.template}

Here are the results to analyze:

{combined_text}

Important instructions:
1. Use the EXACT same section headings and structure as the template
2. Maintain the same level of detail and professional tone
3. Organize information into the appropriate sections as shown in the template
4. If a section would be empty, include it but state "No information available"
5. Format all dates, numbers, and lists consistently with the template
6. Include source citations as footnotes in the same style as the template
7. The ASSIGNMENT section should mention that this is research about {query}
8. Return the response in JSON format with the following structure:
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

            # Get Claude's response
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Process response and structure output
            structured_response = self._process_claude_response(response)
            
            # Return formatted output
            return {
                'metadata': {
                    'processed_datetime': datetime.now().isoformat(),
                    'model': self.model,
                    'source_type': source_type,
                    'template_used': 'Asia Pharma LLC template',
                    'usage': {
                        'input_tokens': response.usage.input_tokens,
                        'output_tokens': response.usage.output_tokens
                    }
                },
                'report': structured_response,
                'raw_results': results
            }

        except Exception as e:
            print(f"Error processing results with Claude: {str(e)}")
            raise

    def _prepare_image_results(self, results: List[Dict]) -> str:
        """Prepare image analysis results for Claude."""
        formatted_results = []
        for result in results:
            formatted_result = (
                f"IMAGE ANALYSIS RESULT\n"
                f"Title: {result.get('title', 'Image Analysis')}\n"
                f"Source: {result.get('source_type', 'Image')}\n"
                f"Date: {result.get('published_date', datetime.now().isoformat())}\n\n"
                f"Analysis:\n{result.get('text', 'No analysis available')}\n"
            )
            formatted_results.append(formatted_result)
        return "\n\n".join(formatted_results)

    def _process_claude_response(self, response) -> Dict:
        """Process Claude's response into structured format."""
        if response.content:
            response_text = response.content[0].text
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse response as JSON: {str(e)}")
                return {"sections": {"raw": response_text}}
        return {}

    def _prepare_search_results(self, results: List[Dict]) -> str:
        """Prepare search results for Claude's analysis."""
        formatted_results = []
        for result in results:
            formatted_result = (
                f"Type: {result.get('result_type', 'Unknown').upper()}\n"
                f"Title: {result.get('title', 'Untitled')}\n"
                f"Source: {result.get('source_type', 'Unknown source')}\n"
                f"URL: {result.get('url', 'No URL')}\n"
                f"Date: {result.get('published_date', 'No date')}\n\n"
                f"{result.get('text', 'No content')}\n"
            )
            formatted_results.append(formatted_result)
            
        return "\n\n".join(formatted_results)

    def save_outputs(self, processed_data: Dict, query: str) -> Dict[str, str]:
        """Save processed results in both JSON and formatted text formats."""
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
                report = processed_data.get('report', {})
                
                # Write sections in template order
                self._write_sections(f, report)
                
                # Write footnotes
                self._write_footnotes(f, report)

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
            
            print("\nSaved files in processed_documents/:")
            print(f"1. Structured JSON: {json_path.name}")
            print(f"2. Formatted Report: {report_path.name}")

            return outputs

        except Exception as e:
            print(f"Error saving outputs: {str(e)}")
            raise

    def _write_sections(self, file, report: Dict):
        """Write report sections in correct order."""
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

    def _write_footnotes(self, file, report: Dict):
        """Write footnotes in correct format."""
        footnotes = report.get('footnotes', [])
        if footnotes:
            file.write("\nSOURCES:\n")
            for i, footnote in enumerate(footnotes, 1):
                file.write(f"[{i}] {footnote}\n")


# Example usage in exa_search.py:
async def process_exa_results(search_results: List[Dict], query: str):
    """Process Exa search results into a formatted report."""
    try:
        print("\nProcessing results with Claude...")
        processor = ReportProcessor()
        
        # Process results
        report = await processor.process_results(search_results, query)
        
        # Save outputs
        outputs = processor.save_outputs(report, query)
        
        return outputs
        
    except Exception as e:
        print(f"Error processing Exa results: {str(e)}")
        raise

if __name__ == "__main__":
    # This can be used for testing the processor directly
    import asyncio
    
    async def test_processor():
        # Sample test data
        test_results = [
            {
                "result_type": "company",
                "title": "Test Company Profile",
                "source_type": "company_website",
                "url": "https://example.com",
                "published_date": "2024-01-01",
                "text": "This is a test company profile..."
            }
        ]
        
        processor = ReportProcessor()
        report = await processor.process_results(test_results, "Test Company")
        outputs = processor.save_outputs(report, "Test Company")
        print("Test complete. Outputs:", outputs)

    asyncio.run(test_processor())