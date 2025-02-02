from PIL import ImageGrab, Image
import tempfile
import os
import base64
from openai import OpenAI
from company_search.claude_processor import ReportProcessor
from website_searchers.report_generator import ExactStyleReportGenerator
import asyncio
from datetime import datetime

async def analyze_clipboard_image(conversation_history=None):
    """
    Analyzes clipboard image and generates a report using the full pipeline.
    Returns both the analysis and a formatted report.
    """
    try:
        # Initialize OpenAI client with the correct key
        client = OpenAI(
            api_key="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",
            organization='org-ATN9LuhPklzEu1L8tM0pxWyG'
        )
        
        # Get image from clipboard
        clipboard_image = ImageGrab.grabclipboard()
        
        if not isinstance(clipboard_image, Image.Image):
            print("No image found in clipboard. Please copy an image first.")
            return None
            
        # Save to temporary file as JPEG
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            clipboard_image = clipboard_image.convert("RGB")
            clipboard_image.save(tmp_file.name, format='JPEG', quality=95)
            filename = tmp_file.name

        # Read and encode the image
        with open(filename, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Clean up the temporary file
        os.remove(filename)

        # Get initial analysis from GPT-4O
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image in detail for a due diligence report."},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }}
                    ]
                }
            ],
            max_tokens=4096
        )
        
        initial_analysis = response.choices[0].message.content

        # Format the analysis for the report pipeline
        results = [{
            "result_type": "image_analysis",
            "title": "Clipboard Image Analysis",
            "source_type": "image",
            "text": initial_analysis,
            "published_date": datetime.now().isoformat(),
            "url": "clipboard://image"
        }]

        # Process with Claude
        print("\nGenerating detailed report...")
        claude_processor = ReportProcessor()
        report_data = await claude_processor.process_results(results, "Image Analysis Report")

        # Generate formatted report
        print("\nFormatting final report...")
        report_generator = ExactStyleReportGenerator()
        report_files = report_generator.generate_report(report_data['report'])

        print("\nReport generation complete!")
        print(f"Initial analysis: {initial_analysis[:200]}...")
        print(f"\nReport files generated:")
        print(f"1. Word document: {report_files['initial_word_path']}")
        print(f"2. Google Doc: {report_files['gdoc_url']}")
        print(f"3. Final Word: {report_files['final_word_path']}")

        return {
            'initial_analysis': initial_analysis,
            'report_data': report_data,
            'report_files': report_files
        }

    except Exception as e:
        print(f"Error during analysis and report generation: {e}")
        return None

if __name__ == "__main__":
    print("Analyzing clipboard image and generating report...")
    result = asyncio.run(analyze_clipboard_image())
    if result:
        print("\nProcess completed successfully!") 