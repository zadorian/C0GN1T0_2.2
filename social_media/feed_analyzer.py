import base64
import tempfile
from PIL import Image
import io
from pathlib import Path
from typing import Optional, Dict, List
from AI_models.ai_vision import VisionAnalyzer, claude_client
from tqdm import tqdm
import time

class FeedAnalyzer:
    """Analyzes social media feed screenshots with support for long images"""
    
    def __init__(self, max_height: int = 3000):
        self.max_height = max_height  # Maximum height for single image analysis
        self.vision_analyzer = VisionAnalyzer()
        
    def _split_image(self, image: Image.Image) -> List[Image.Image]:
        """Split a long image into manageable chunks with overlap"""
        if image.height <= self.max_height:
            return [image]
            
        chunks = []
        overlap = 200  # Pixels of overlap between chunks
        current_pos = 0
        
        while current_pos < image.height:
            # Calculate chunk boundaries
            chunk_end = min(current_pos + self.max_height, image.height)
            # If this is not the first chunk, include overlap
            chunk_start = current_pos if current_pos == 0 else current_pos - overlap
            
            # Extract chunk
            chunk = image.crop((0, chunk_start, image.width, chunk_end))
            chunks.append(chunk)
            
            # Move position for next chunk
            current_pos = chunk_end
            
            # Stop if we've processed the whole image
            if chunk_end == image.height:
                break
                
        return chunks

    def _encode_image(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        with io.BytesIO() as buffer:
            image = image.convert("RGB")  # Convert to RGB to ensure JPEG compatibility
            image.save(buffer, format="JPEG", quality=95)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def _analyze_with_claude(self, image_data: str, prompt: str, max_tokens: int = 1000):
        """Claude Vision analysis"""
        try:
            response = claude_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=max_tokens,
                messages=[{
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data
                            }
                        }
                    ]
                }]
            )
            return response.content[0].text if isinstance(response.content, list) else response.content
        except Exception as e:
            return f"Error analyzing image with Claude Vision: {str(e)}"

    def analyze_feed(self, 
                    image_path: str, 
                    prompt: str,
                    model: str = "claude") -> Dict:
        """
        Analyze a social media feed screenshot, handling long images by splitting
        and combining analysis results intelligently.
        """
        try:
            # Load and process image
            with Image.open(image_path) as img:
                # Split image if necessary
                image_chunks = self._split_image(img)
                
                # Analyze each chunk
                chunk_analyses = []
                for i, chunk in enumerate(image_chunks):
                    # Encode chunk
                    chunk_b64 = self._encode_image(chunk)
                    
                    # Modify prompt for chunk context if multiple chunks
                    chunk_prompt = prompt
                    if len(image_chunks) > 1:
                        chunk_prompt = f"""This is part {i+1} of {len(image_chunks)} of a longer social media feed screenshot. 
                        
Previous parts covered earlier posts in the feed. Please analyze this section, focusing on:
1. The content of visible posts
2. Any interactions (likes, comments, shares)
3. Usernames and timestamps if visible
4. Any media content (images, videos, links)

{prompt}"""
                    
                    # Analyze chunk
                    analysis = self.vision_analyzer.analyze(
                        chunk_b64,
                        chunk_prompt,
                        model=model
                    )
                    chunk_analyses.append(analysis)
                
                # Combine analyses intelligently
                if len(chunk_analyses) == 1:
                    return {"analysis": chunk_analyses[0]}
                else:
                    # Combine multiple analyses with Claude
                    combined_prompt = f"""I have {len(chunk_analyses)} consecutive sections of a social media feed that need to be combined into a single coherent analysis. Each section was analyzed separately:

{' '.join(f'Section {i+1}: {analysis}' for i, analysis in enumerate(chunk_analyses))}

Please provide a unified analysis that:
1. Removes any duplicate mentions of posts
2. Maintains chronological order of the feed
3. Preserves all unique interactions and engagement metrics
4. Summarizes the overall themes and discussions
5. Highlights the most significant posts and interactions

Your response should flow naturally as if analyzing a single continuous feed."""
                    
                    combined_analysis = self.vision_analyzer.analyze(
                        self._encode_image(image_chunks[0]),  # Use first image as context
                        combined_prompt,
                        model=model
                    )
                    
                    return {
                        "analysis": combined_analysis,
                        "chunks": len(chunk_analyses)
                    }

        except Exception as e:
            return {"error": f"Error analyzing feed: {str(e)}"}

    def answer_question(self, 
                       image_path: str, 
                       question: str,
                       model: str = "claude") -> str:
        """
        Answer a specific question about a social media feed screenshot
        """
        # Construct a prompt that focuses on answering the specific question
        prompt = f"""Please analyze this social media feed screenshot and answer the following specific question:

{question}

Focus only on providing a clear, direct answer to this question based on the visible content."""

        result = self.analyze_feed(image_path, prompt, model)
        return result.get("analysis", "Error analyzing the feed")

    def analyze_multiple_feeds(self, 
                             folder_path: str, 
                             prompt: str,
                             model: str = "claude") -> Dict[str, Dict]:
        """
        Analyze all supported image files in a folder
        """
        results = {}
        supported_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
        folder = Path(folder_path)
        
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            print(f"Created feeds folder at: {folder}")
            print("Please add your social media screenshots to this folder.")
            return {}
            
        image_files = [f for f in folder.iterdir() 
                      if f.suffix.lower() in supported_extensions]
        
        if not image_files:
            print(f"No supported images found in {folder}")
            print(f"Supported formats: {', '.join(supported_extensions)}")
            return {}
            
        print(f"\nFound {len(image_files)} images to analyze")
        for image_file in image_files:
            print(f"\nAnalyzing: {image_file.name}")
            result = self.analyze_feed(str(image_file), prompt, model)
            results[image_file.name] = result
            
        return results

    def answer_question_across_feeds(self,
                                   folder_path: str,
                                   question: str,
                                   model: str = "claude") -> Dict[str, str]:
        """
        Answer a specific question by analyzing all feeds in the folder
        """
        results = {}
        folder = Path(folder_path)
        
        if not folder.exists() or not any(folder.iterdir()):
            print(f"No images found in {folder}")
            return {}
            
        # Get list of image files
        image_files = [f for f in folder.iterdir() 
                      if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}]
        
        if not image_files:
            print("No supported images found in folder")
            return {}
            
        print(f"\nFound {len(image_files)} images to analyze")
        
        # First analyze each feed individually
        individual_answers = {}
        
        # Create progress bar for individual analyses
        with tqdm(total=len(image_files), desc="Analyzing feeds", unit="feed") as pbar:
            for image_file in image_files:
                pbar.set_description(f"Analyzing {image_file.name}")
                prompt = f"""Please analyze this social media feed screenshot to answer the following question:

{question}

For EVERY piece of information you provide, you MUST:
1. Specify the source file name
2. Include the exact date and time of each post/entry
3. List all individuals mentioned (both regular users and public figures)
4. Highlight any politicians or government entities mentioned
5. Note any potentially adverse or controversial information
6. Quote relevant text directly using quotation marks

Format your response with these sections:
A. BASIC INFORMATION
   - Source file: [filename]
   - Platform: [platform name]
   - Time range: [earliest to latest post]

B. KEY FINDINGS
   - Direct quotes with dates and times
   - Named individuals and their roles
   - Political/government references
   - Adverse information found

C. EVIDENCE
   For each piece of evidence:
   - File: [filename]
   - Date/Time: [exact timestamp]
   - Author: [username/name]
   - Quote: "exact text"
   - Context: [any relevant context]
   - Adverse flags: [if any]

Please be extremely precise with attributions and timestamps."""

                answer = self.answer_question(str(image_file), prompt, model)
                individual_answers[image_file.name] = answer
                pbar.update(1)
        
        # If we have multiple feeds, combine their insights
        if len(individual_answers) > 1:
            print("\nCombining insights across feeds...")
            with tqdm(total=1, desc="Generating combined analysis", unit="analysis") as pbar:
                combined_prompt = f"""I have analyzed {len(individual_answers)} different social media feeds to answer this question: 
"{question}"

Here are the individual analyses:

{chr(10).join(f'[{name}]:\n{answer}\n' for name, answer in individual_answers.items())}

Provide a comprehensive analysis that MUST:
1. Reference specific files for all evidence
2. Include exact dates and times for all posts
3. List ALL mentioned individuals:
   - Regular users
   - Public figures
   - Politicians
   - Government officials
4. Highlight government/political references
5. Flag any adverse or controversial information
6. Use direct quotes with proper attribution

Format your response as follows:

SUMMARY OF FINDINGS
------------------
- Key themes across all feeds
- Notable patterns or contradictions
- Timeline of relevant events

DETAILED ANALYSIS
----------------
[For each major point]:
- Source files: [list relevant files]
- Dates: [specific timestamps]
- People mentioned: [list all names]
- Political references: [if any]
- Adverse information: [if any]
- Evidence: "direct quotes"

ADVERSE INFORMATION LOG
----------------------
List any potentially controversial or adverse information found:
- File: [filename]
- Date: [timestamp]
- Context: [explanation]
- Quote: "exact text"

POLITICAL/GOVERNMENT MENTIONS
---------------------------
List all political or government-related references:
- Entity/Person: [name]
- Role: [position]
- Context: [explanation]
- Files: [source files]
- Dates: [when mentioned]"""
                
                # Use first image as context
                first_image = next(iter(individual_answers.keys()))
                combined_analysis = self.vision_analyzer.analyze(
                    self._encode_image(Image.open(folder / first_image)),
                    combined_prompt,
                    model=model
                )
                pbar.update(1)
            
            results = {
                "individual_answers": individual_answers,
                "combined_analysis": combined_analysis
            }
        else:
            results = {"individual_answers": individual_answers}
            
        return results

def main():
    analyzer = FeedAnalyzer()
    
    # Create feeds folder in social_media directory
    feeds_folder = Path(__file__).parent / "social_media_feeds"
    feeds_folder.mkdir(exist_ok=True)
    
    print("\nSocial Media Feed Analyzer")
    print("=========================")
    print(f"Feeds folder: {feeds_folder}")
    print("Add your screenshots to the folder: " + str(feeds_folder))
    print("\nThis tool will analyze all social media screenshots in the folder to answer your questions.")
    print("It will provide evidence from specific posts and reference which screenshot each piece of evidence comes from.")
    
    while True:
        print("\nOptions:")
        print("1. Ask a question about the feeds")
        print("2. Exit")
        
        choice = input("\nSelect option (1-2): ")
        
        if choice == "1":
            question = input("\nWhat would you like to know about these social media feeds?: ")
            
            print("\nStarting analysis...")
            results = analyzer.answer_question_across_feeds(feeds_folder, question)
            
            print("\nAnalysis Results:")
            print("================")
            
            for feed_name, answer in results["individual_answers"].items():
                print(f"\nEvidence from {feed_name}:")
                print("-" * (len(feed_name) + 14))
                print(answer)
                print()
            
            if "combined_analysis" in results:
                print("\nCombined Analysis:")
                print("=================")
                print(results["combined_analysis"])
                
        elif choice == "2":
            print("\nGoodbye!")
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main() 