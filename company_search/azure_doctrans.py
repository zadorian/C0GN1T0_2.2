import os
import json
import asyncio
import aiohttp
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

class AzureTranslator:
    def __init__(self):
        self.key = "4AYFPSyb1zDnlB0GVYuGIgGnKcWKnlzQ0ozB3vH6w3iYsSlH8ekuJQQJ99ALAC5RqLJXJ3w3AAAbACOGBGGL"
        self.endpoint = "https://api.cognitive.microsofttranslator.com"
        self.location = "eastus"

    async def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        if not text.strip():
            return text

        url = f"{self.endpoint}/translate"
        
        # Detect source language if not provided
        if not source_language:
            # Detect based on first letter unicode range
            first_char = text[0]
            if '\u0600' <= first_char <= '\u06FF':  # Arabic range
                source_language = 'ar'
            elif all(ord(c) < 128 for c in text):  # ASCII/English
                source_language = 'en'

        params = {
            'api-version': '3.0',
            'to': target_language,
            'from': source_language,
            'textType': 'plain'
        }

        headers = {
            'Ocp-Apim-Subscription-Key': self.key,
            'Ocp-Apim-Subscription-Region': self.location,
            'Content-type': 'application/json'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    params=params,
                    headers=headers,
                    json=[{'text': text}],
                    timeout=30
                ) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 1))
                        await asyncio.sleep(retry_after)
                        return await self.translate_text(text, target_language, source_language)
                    
                    response.raise_for_status()
                    translation = await response.json()
                    return translation[0]['translations'][0]['text']

        except Exception as e:
            print(f"Translation error for text '{text[:30]}...': {str(e)}")
            return f"{text}"  # Return original text instead of error message

    async def translate_batch(self, texts: List[str], target_language: str, 
                            source_language: Optional[str] = None, use_custom: bool = False) -> List[str]:
        results = []
        for i, text in enumerate(texts):
            if i > 0 and i % 25 == 0:
                await asyncio.sleep(1)
            result = await self.translate_text(text, target_language, source_language)
            results.append(result)
        return results

    async def translate_document_content(self, content: Dict, target_language: str, source_language: Optional[str] = None) -> Dict:
        """Translate document content maintaining structure"""
        if 'pages' in content:
            for page in content['pages']:
                if 'lines' in page:
                    texts = [line['text'] for line in page['lines']]
                    translations = await self.translate_batch(texts, target_language, source_language)
                    for line, translation in zip(page['lines'], translations):
                        line['translated_text'] = translation

        if 'tables' in content:
            for table in content['tables']:
                if 'data' in table:
                    flattened = [cell for row in table['data'] for cell in row if cell.strip()]
                    translations = await self.translate_batch(flattened, target_language, source_language)
                    
                    translated_data = []
                    translation_idx = 0
                    for row in table['data']:
                        translated_row = []
                        for cell in row:
                            if cell.strip():
                                translated_row.append(translations[translation_idx])
                                translation_idx += 1
                            else:
                                translated_row.append(cell)
                        translated_data.append(translated_row)
                    table['translated_data'] = translated_data

        return content

class DocumentTranslator:
    def __init__(self):
        self.translator = AzureTranslator()
        self.output_dir = Path("translated_documents")
        self.output_dir.mkdir(exist_ok=True)

    async def translate_document(self, content: Dict, target_language: str, 
                               source_language: Optional[str] = None) -> Dict:
        """Translate document content and save results"""
        try:
            # Translate the document content
            translated_content = await self.translator.translate_document_content(
                content, 
                target_language, 
                source_language
            )
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"translated_{timestamp}.json"
            
            # Save translated content
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(translated_content, f, ensure_ascii=False, indent=2)
                
            return translated_content
            
        except Exception as e:
            print(f"Error translating document: {str(e)}")
            raise

    async def translate_text_batch(self, texts: List[str], target_language: str,
                                 source_language: Optional[str] = None) -> List[str]:
        """Translate a batch of texts"""
        return await self.translator.translate_batch(texts, target_language, source_language)