import asyncio
import traceback
from typing import List, Tuple
from website_searchers.website_searcher import WebsiteSearcher
from website_searchers.ai_searcher import client as ai_client

class ComparisonSearcher:
    """
    Handles commands using the =? operator to compare search results across multiple targets.
    """

    def __init__(self):
        self.website_searcher = WebsiteSearcher()

    async def handle_comparison_command(self, command: str) -> str:
        """Handle comparison command with =? syntax."""
        try:
            # Split on =? to get parts
            parts = command.split('=?')
            if len(parts) < 2:
                return "Invalid comparison command. Need at least two parts separated by =?"

            # Get results for each part
            results = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                    
                # Process each part as a regular command
                searcher = WebsiteSearcher()
                
                # If this is just a URL (no search type prefix), treat it as a content fetch
                if not any(prefix in part for prefix in ['p!', 'c!', 'l!', '@!', 't!', 'ent!', 'bl!', '!bl', 'ga!', 'whois!']):
                    result = await searcher.process_command(part)
                    results.append((part, result))
                else:
                    # Handle normal search commands
                    result = await searcher.process_command(part)
                    results.append((part, result))

            if len(results) < 2:
                return "Need at least two valid parts to compare"

            # For NER searches, show overlap
            if any('p!' in part[0] or 'c!' in part[0] or 'l!' in part[0] for part in results):
                return self._format_ner_comparison(results)

            # For simple content comparisons or other searches, use AI
            return await self._compare_with_ai(results)

        except Exception as e:
            traceback.print_exc()
            return f"Error in handle_comparison_command: {str(e)}"

    async def _compare_with_ai(self, results: List[tuple]) -> str:
        """Uses AI to compare the outcomes from each target."""
        try:
            comparison_input = []
            for domain, res in results:
                comparison_input.append(f"--- Content from {domain} ---\n{res}\n")

            combined_results_text = "\n".join(comparison_input)

            # Determine if this is a temporal comparison (same target, different years)
            is_temporal = False
            if len(results) == 2:
                target1, target2 = results[0][0], results[1][0]
                # Check if one target is a year-specific version of the other
                if ('!' in target1 and target1.split('!')[1].strip() == target2.strip()) or \
                   ('!' in target2 and target2.split('!')[1].strip() == target1.strip()):
                    is_temporal = True

            # Choose appropriate prompt based on content type
            if any(marker in results[0][0] for marker in ['p!', 'c!', 'l!', '@!', 't!', 'ent!']):
                from prompts import get_ner_comparison_prompt
                prompt = get_ner_comparison_prompt(results[0][0], combined_results_text, is_temporal)
            else:
                # For simple content comparisons
                from prompts import get_content_comparison_prompt
                prompt = get_content_comparison_prompt(combined_results_text, is_temporal)

            # Use OpenAI client for comparison
            response = ai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI that compares website content. "
                            "Focus first on identifying key similarities and overlaps, "
                            "then note significant differences. Be concise and conversational. "
                            "If you spot patterns or connections, mention them briefly."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return response.choices[0].message.content

        except Exception as e:
            traceback.print_exc()
            return f"Error during AI comparison: {str(e)}"

    def _format_ner_comparison(self, results: List[Tuple[str, str]]) -> str:
        """Format NER comparison results to show original results and simple analysis."""
        output = []
        
        # First show original results for each URL
        for cmd, result in results:
            output.append(f"\n=== Results for {cmd} ===")
            output.append(result)
        
        # Then find common entities and analyze patterns
        all_entities = []
        for cmd, result in results:
            entities = set()
            lines = result.split('\n')
            for line in lines:
                if line.startswith('- '):
                    entities.add(line[2:])
            all_entities.append((cmd, entities))
        
        # Find overlap and add simple analysis
        if len(all_entities) >= 2:
            common = all_entities[0][1]
            for _, entities in all_entities[1:]:
                common = common & entities
            
            output.append("\n=== Analysis ===")
            
            # Build analysis message
            analysis = []
            
            # First priority: overlaps
            if common:
                names = sorted(common)
                if len(names) == 1:
                    analysis.append(f"{names[0]} appears on both sites.")
                else:
                    analysis.append(f"{', '.join(names)} appear on both sites.")
            else:
                analysis.append("There's no overlap in people between these sites.")
            
            # Second priority: notable contrasts
            site1_unique = all_entities[0][1] - all_entities[1][1]
            site2_unique = all_entities[1][1] - all_entities[0][1]
            
            if len(site1_unique) == 0 and len(site2_unique) > 0:
                analysis.append(f"The second site mentions {len(site2_unique)} additional people not found on the first site.")
            elif len(site2_unique) == 0 and len(site1_unique) > 0:
                analysis.append(f"The first site mentions {len(site1_unique)} additional people not found on the second site.")
            elif abs(len(site1_unique) - len(site2_unique)) > 3:
                analysis.append(f"The second site lists significantly more people ({len(all_entities[1][1])}) than the first site ({len(all_entities[0][1])}).")
            
            # Look for patterns in names (e.g., similar surnames or regions)
            all_names = all_entities[0][1] | all_entities[1][1]
            hungarian_count = sum(1 for name in all_names if any(suffix in name.lower() for suffix in ['szabo', 'radnoti', 'mester']))
            if hungarian_count >= 2:
                analysis.append("Several of the names appear to be Hungarian.")
            
            output.append(" ".join(analysis))
                
        return "\n".join(output)

async def demo():
    """
    Simple demo usage if you run 'comparison.py' directly:
    python comparison.py "p! :company1.com! =? company2.com?"
    """
    import sys
    if len(sys.argv) < 2:
        print("Usage: python comparison.py \"<search-object> : <target1> =? <target2>\"")
        return

    command = sys.argv[1]
    comp = ComparisonSearcher()
    result = await comp.handle_comparison_command(command)
    print("\n=== Final Comparison Output ===\n")
    print(result)

if __name__ == "__main__":
    asyncio.run(demo()) 