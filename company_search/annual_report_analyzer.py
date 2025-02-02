import os
import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv

# Import existing functionality
from company_search.uk_cr_reports import is_financial_report, summarize_financial_report
from ch_ownership import CompaniesHouseFilingFetcher, ClaudeProcessor
from company_search.company_resolver import resolve_company_interactive

class AnnualReportAnalyzer:
    def __init__(self):
        self.output_dir = Path(__file__).parent / "company_documents"
        self.output_dir.mkdir(exist_ok=True)
        
        # Load environment variables
        load_dotenv()
        self.ch_api_key = os.getenv('CH_API_KEY')
        if not self.ch_api_key:
            raise ValueError("CH_API_KEY not found in environment")
            
        self.fetcher = CompaniesHouseFilingFetcher(self.ch_api_key)
        self.claude = ClaudeProcessor()
        
    async def analyze_company_reports(self, query: str) -> None:
        """Main entry point for analyzing a company's annual reports."""
        cnum, cname = resolve_company_interactive(self.fetcher, query)
        if not cnum:
            print("Could not resolve company.")
            return

        print(f"\n==== Analyzing Annual Reports for {cname} ({cnum}) ====")
        reports = await self.get_financial_reports(cnum)
        if not reports:
            return

        await self.interactive_report_analysis(cnum, reports)
        
    async def get_financial_reports(self, company_number: str) -> List[dict]:
        """Fetch and filter financial reports for a company."""
        hist = self.fetcher.get_company_filing_history(company_number)
        if not hist or not hist.get("items"):
            print("No filings found.")
            return []

        items = hist["items"]
        items.sort(key=lambda x: x.get('date', ''), reverse=True)
        financial_reports = [f for f in items if is_financial_report(f)]

        if not financial_reports:
            print("No financial/annual accounts found.")
            return []

        print(f"\nFound {len(financial_reports)} financial reports:")
        for idx, f in enumerate(financial_reports, 1):
            date = f.get("date", "unknown-date")
            ftype = f.get("type", "??")
            desc = f.get("description", "no description")
            print(f"{idx:3d}. {date} | {ftype} | {desc}")

        return financial_reports

    async def interactive_report_analysis(self, company_number: str, reports: List[dict]) -> None:
        """Let user choose which reports to analyze."""
        summaries: Dict[str, Any] = {
            "company_number": company_number,
            "reports": []
        }
        
        while True:
            choice = input("\nEnter report number to analyze or 'q' to quit: ").strip().lower()
            if choice == 'q':
                break
                
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(reports):
                    report = reports[idx]
                    date = report.get("date", "unknown-date")
                    ftype = report.get("type", "??")
                    
                    print(f"\n--- Analyzing {date} {ftype} ---")
                    summary = await summarize_financial_report(
                        self.fetcher,
                        self.claude,
                        company_number,
                        report,
                        self.output_dir
                    )
                    
                    if summary:
                        print("\n=== Financial Report Summary ===\n")
                        print(summary)
                        
                        # Save to our collection
                        summaries["reports"].append({
                            "date": date,
                            "type": ftype,
                            "summary": summary
                        })
                    else:
                        print("Failed to analyze this report.")
                else:
                    print("Invalid report number.")
            except ValueError:
                print("Please enter a valid number or 'q'.")
        
        # Save all summaries to a JSON file
        if summaries["reports"]:
            output_file = self.output_dir / f"{company_number}_financial_summaries.json"
            with open(output_file, 'w') as f:
                json.dump(summaries, f, indent=2)
            print(f"\nSaved all summaries to: {output_file}")

async def main():
    """CLI entry point."""
    analyzer = AnnualReportAnalyzer()
    
    print("Enter company name or number to analyze annual reports.")
    print("Type 'quit' to exit.")
    
    while True:
        query = input("\nCompany: ").strip()
        if query.lower() in ('quit', 'exit', 'q'):
            break
            
        if query:
            await analyzer.analyze_company_reports(query)

if __name__ == "__main__":
    asyncio.run(main()) 