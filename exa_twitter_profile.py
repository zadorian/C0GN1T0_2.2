import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from exa_py import Exa
from dataclasses import dataclass
import pandas as pd
from collections import Counter, defaultdict
import re
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from textblob import TextBlob
import json
import numpy as np
from pathlib import Path
import uuid

@dataclass
class UserAnalysis:
    username: str
    total_posts: int
    post_frequency: str
    topics: List[tuple]
    sentiment_analysis: Dict[str, float]
    interaction_patterns: Dict[str, int]
    top_mentions: List[tuple]
    hashtag_usage: List[tuple]
    content_categories: Dict[str, int]
    urls: List[str]
    posting_timeline: Dict[str, int]
    tweets: List[Dict]
    languages: Dict[str, int]

class TwitterUserAnalyzer:
    def __init__(self):
        self.exa = Exa("ecd713df-48c2-4fb7-b99a-55f3472478b1")
        self.domains = ["twitter.com", "x.com"]
        
        # Azure Translator configuration
        self.translator_key = "YOUR_KEY_HERE"  # Replace with your key
        self.translator_location = "eastus"  # Your Azure region
        
        try:
            nltk.download('vader_lexicon', quiet=True)
        except:
            pass
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

    def translate_text(self, text: str, target_lang: str = 'en') -> Dict:
        """
        Translates text using Azure AI Translator service with improved error handling
        """
        if not text or not text.strip():
            return {
                "text": text,
                "detected_language": "unknown"
            }

        # Extract actual text content before metadata
        content = text.split('| created_at:')[0] if '| created_at:' in text else text
        # Remove URLs from content
        content = re.sub(r'https?://\S+', '', content).strip()
        
        if not content:  # If no content after cleaning
            return {
                "text": text,
                "detected_language": "unknown"
            }

        # Updated headers with correct configuration
        headers = {
            'Ocp-Apim-Subscription-Key': self.translator_key,
            'Ocp-Apim-Subscription-Region': self.translator_location,
            'Content-type': 'application/json'
        }

        body = [{
            'text': content
        }]

        params = {
            'api-version': '3.0',
            'to': target_lang
        }

        try:
            # Construct proper endpoint URL
            endpoint = f"https://{self.translator_location}.api.cognitive.microsofttranslator.com/translate"
            
            response = requests.post(
                endpoint,
                params=params,
                headers=headers,
                json=body
            )
            
            # Detailed error logging
            if response.status_code != 200:
                print(f"Translation failed with status {response.status_code}")
                print("Request details:")
                print(f"Endpoint: {endpoint}")
                print(f"Headers: {headers}")
                print(f"Params: {params}")
                print(f"Body: {body}")
                print(f"Response: {response.text}")
                
                return {
                    "text": text,
                    "detected_language": "unknown",
                    "error": f"Translation failed: {response.text}"
                }

            translation = response.json()[0]
            translated_text = translation['translations'][0]['text']
            detected_lang = translation.get('detectedLanguage', {}).get('language', 'unknown')
            
            # Reconstruct with metadata if present
            if '| created_at:' in text:
                metadata = text[text.index('| created_at:'):]
                final_text = f"{translated_text} {metadata}"
            else:
                final_text = translated_text

            return {
                "text": final_text,
                "detected_language": detected_lang
            }

        except Exception as e:
            print(f"Translation error: {str(e)}")
            return {
                "text": text,
                "detected_language": "unknown",
                "error": str(e)
            }

    def clean_text(self, text: str) -> str:
        text = re.sub(r'http\S+|www.\S+', '', text)
        return text.lower()

    def extract_mentions(self, text: str) -> List[str]:
        mentions = re.findall(r'@(\w+)', text)
        return mentions

    def extract_hashtags(self, text: str) -> List[str]:
        hashtags = re.findall(r'#(\w+)', text)
        return hashtags

    def analyze_tweets(self, username: str, query: str, num_results: int, start_date: str, translate: bool = False) -> UserAnalysis:
        search_response = self.exa.search_and_contents(
            query,
            include_domains=self.domains,
            num_results=num_results,
            use_autoprompt=False,
            text=True,
            highlights=True,
            start_published_date=start_date
        )
        results = search_response.results
        if not results:
            raise ValueError(f"No posts found for user {username}")
        texts = [r.text for r in results if r.text]
        urls = [r.url for r in results]
        dates = [r.published_date for r in results if r.published_date]
        all_mentions = []
        all_hashtags = []
        sentiments = []
        content_types = defaultdict(int)
        tweets_data = []
        languages = defaultdict(int)
        
        for result in results:
            text = result.text or ''
            
            if translate:
                translation = self.translate_text(text)
                translated_text = translation["text"]
                detected_lang = translation["detected_language"]
                languages[detected_lang] += 1
            else:
                translated_text = text
                detected_lang = "unknown"
                
            tweet_data = {
                'url': result.url,
                'original_text': text,
                'translated_text': translated_text if translate and detected_lang != 'en' else None,
                'language': detected_lang,
                'date': result.published_date,
                'score': result.score,
                'media': result.metadata.get('media', []) if hasattr(result, 'metadata') else [],
                'highlights': result.highlights if hasattr(result, 'highlights') else []
            }
            tweets_data.append(tweet_data)
            mentions = self.extract_mentions(text)
            hashtags = self.extract_hashtags(text)
            all_mentions.extend(mentions)
            all_hashtags.extend(hashtags)
            
            if 'RT @' in text:
                content_types['Retweets'] += 1
            elif text.startswith('@'):
                content_types['Replies'] += 1
            elif 'http' in text:
                content_types['With links'] += 1
            elif any(ext in text.lower() for ext in ['.jpg', '.png', '.gif', 'photo', 'video']):
                content_types['With media'] += 1
            else:
                content_types['Text only'] += 1

            clean_text = self.clean_text(text)
            sentiment = TextBlob(clean_text).sentiment.polarity
            sentiments.append(sentiment)

        timeline = defaultdict(int)
        for date in dates:
            if date:
                month = datetime.fromisoformat(date).strftime('%Y-%m')
                timeline[month] += 1

        if dates:
            days_span = (datetime.fromisoformat(max(dates)) - datetime.fromisoformat(min(dates))).days
            posts_per_day = len(texts) / (days_span if days_span > 0 else 1)
            frequency = f"{posts_per_day:.1f} posts per day"
        else:
            frequency = "Unable to determine"

        sentiment_analysis = {
            'average_sentiment': np.mean(sentiments) if sentiments else 0,
            'positive_posts': len([s for s in sentiments if s > 0]),
            'negative_posts': len([s for s in sentiments if s < 0]),
            'neutral_posts': len([s for s in sentiments if s == 0])
        }

        clean_texts = [self.clean_text(text) for text in texts]
        words = []
        stop_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have'}
        for text in clean_texts:
            text = re.sub(r'@\w+|#\w+', '', text)
            words.extend([w for w in text.split() if w not in stop_words and len(w) > 3])

        return UserAnalysis(
            username=username,
            total_posts=len(texts),
            post_frequency=frequency,
            topics=Counter(words).most_common(10),
            sentiment_analysis=sentiment_analysis,
            interaction_patterns=dict(content_types),
            top_mentions=Counter(all_mentions).most_common(10),
            hashtag_usage=Counter(all_hashtags).most_common(10),
            content_categories=dict(content_types),
            urls=urls,
            posting_timeline=dict(timeline),
            tweets=tweets_data,
            languages=dict(languages)
        )

    def export_tweets(self, analysis: UserAnalysis, format: str = 'json') -> str:
        # Get absolute path to C0GN1T0-main directory
        project_dir = Path('/Users/brain/Desktop/REST/C0GN1T0-main')
        export_dir = project_dir / 'twitter_exports'
        export_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = export_dir / f"{analysis.username}_tweets_{timestamp}.{format}"
        
        if format == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(analysis.tweets, f, indent=2, ensure_ascii=False)
        else:
            df = pd.DataFrame(analysis.tweets)
            df.to_csv(filename, index=False, encoding='utf-8')
        
        print(f"\nTweets exported to: {filename}")
        return str(filename)

    def generate_report(self, analysis: UserAnalysis, show_tweets: bool = False) -> str:
        report_lines = [
            f"\nUser Analysis Report for {analysis.username}",
            "=" * 50,
            f"\nTotal Posts: {analysis.total_posts}",
            f"Posting Frequency: {analysis.post_frequency}",
            "\nContent Categories:",
            *[f"- {k}: {v} posts" for k, v in analysis.content_categories.items()],
            "\nSentiment Analysis:",
            f"- Average sentiment: {'Positive' if analysis.sentiment_analysis['average_sentiment'] > 0 else 'Negative'}",
            f"- Positive posts: {analysis.sentiment_analysis['positive_posts']}",
            f"- Negative posts: {analysis.sentiment_analysis['negative_posts']}",
            f"- Neutral posts: {analysis.sentiment_analysis['neutral_posts']}",
            "\nTop Topics:",
            *[f"- {topic}: {count} times" for topic, count in analysis.topics[:5]],
            "\nMost Mentioned Users:",
            *[f"- {user}: {count} times" for user, count in analysis.top_mentions[:5]],
            "\nMost Used Hashtags:",
            *[f"- {tag}: {count} times" for tag, count in analysis.hashtag_usage[:5]],
            "\nPosting Timeline:",
            *[f"- {month}: {count} posts" for month, count in sorted(analysis.posting_timeline.items())]
        ]
        
        if analysis.languages:
            report_lines.extend([
                "\nLanguage Distribution:",
                *[f"- {lang}: {count} posts" for lang, count in analysis.languages.items()]
            ])
            
        if show_tweets:
            report_lines.extend(["\nFull Tweets:", "=" * 50])
            for i, tweet in enumerate(analysis.tweets, 1):
                report_lines.extend([
                    f"\nTweet {i}:",
                    f"URL: {tweet['url']}",
                    f"Date: {tweet['date']}",
                    f"Language: {tweet['language']}",
                    f"Original: {tweet['original_text']}"
                ])
                if tweet.get('translated_text'):
                    report_lines.append(f"Translated: {tweet['translated_text']}")
                if tweet['media']:
                    report_lines.append(f"Media: {tweet['media']}")
                if tweet['highlights']:
                    report_lines.extend([
                        "Highlights:",
                        *[f"- {h}" for h in tweet['highlights']]
                    ])
                report_lines.append("-" * 40)
        return "\n".join(report_lines)

    def analyze_user(self, username: str, days_back: int = 90, num_results: int = 100, translate: bool = False, start_cursor: str = None) -> Tuple[UserAnalysis, str]:
        """Analyze user tweets with pagination support"""
        query = f"from:{username}"
        start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        search_response = self.exa.search_and_contents(
            query,
            include_domains=self.domains,
            num_results=num_results,
            use_autoprompt=False,
            text=True,
            highlights=True,
            start_published_date=start_date,
            cursor=start_cursor  # Add cursor for pagination
        )
        
        # Get next cursor for pagination
        next_cursor = search_response.next_cursor if hasattr(search_response, 'next_cursor') else None
        
        results = search_response.results
        if not results:
            raise ValueError(f"No posts found for user {username}")

        texts = [r.text for r in results if r.text]
        urls = [r.url for r in results]
        dates = [r.published_date for r in results if r.published_date]
        
        all_mentions = []
        all_hashtags = []
        sentiments = []
        content_types = defaultdict(int)
        tweets_data = []
        languages = defaultdict(int)
        
        for result in results:
            text = result.text or ''
            
            if translate:
                translation = self.translate_text(text)
                translated_text = translation["text"]
                detected_lang = translation["detected_language"]
                languages[detected_lang] += 1
            else:
                translated_text = text
                detected_lang = "unknown"
            
            tweet_data = {
                'url': result.url,
                'original_text': text,
                'translated_text': translated_text if translate and detected_lang != 'en' else None,
                'language': detected_lang,
                'date': result.published_date,
                'score': result.score,
                'media': result.metadata.get('media', []) if hasattr(result, 'metadata') else [],
                'highlights': result.highlights if hasattr(result, 'highlights') else []
            }
            tweets_data.append(tweet_data)
            
            mentions = self.extract_mentions(text)
            hashtags = self.extract_hashtags(text)
            all_mentions.extend(mentions)
            all_hashtags.extend(hashtags)
            
            if 'RT @' in text:
                content_types['Retweets'] += 1
            elif text.startswith('@'):
                content_types['Replies'] += 1
            elif 'http' in text:
                content_types['With links'] += 1
            elif any(ext in text.lower() for ext in ['.jpg', '.png', '.gif', 'photo', 'video']):
                content_types['With media'] += 1
            else:
                content_types['Text only'] += 1

            clean_text = self.clean_text(translated_text if translate else text)
            sentiment = TextBlob(clean_text).sentiment.polarity
            sentiments.append(sentiment)

        timeline = defaultdict(int)
        for date in dates:
            if date:
                month = datetime.fromisoformat(date).strftime('%Y-%m')
                timeline[month] += 1

        if dates:
            days_span = (datetime.fromisoformat(max(dates)) - datetime.fromisoformat(min(dates))).days
            posts_per_day = len(texts) / (days_span if days_span > 0 else 1)
            frequency = f"{posts_per_day:.1f} posts per day"
        else:
            frequency = "Unable to determine"

        sentiment_analysis = {
            'average_sentiment': np.mean(sentiments) if sentiments else 0,
            'positive_posts': len([s for s in sentiments if s > 0]),
            'negative_posts': len([s for s in sentiments if s < 0]),
            'neutral_posts': len([s for s in sentiments if s == 0])
        }

        clean_texts = [self.clean_text(text) for text in texts]
        words = []
        stop_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have'}
        for text in clean_texts:
            text = re.sub(r'@\w+|#\w+', '', text)
            words.extend([w for w in text.split() if w not in stop_words and len(w) > 3])

        analysis = UserAnalysis(
            username=username,
            total_posts=len(texts),
            post_frequency=frequency,
            topics=Counter(words).most_common(10),
            sentiment_analysis=sentiment_analysis,
            interaction_patterns=dict(content_types),
            top_mentions=Counter(all_mentions).most_common(10),
            hashtag_usage=Counter(all_hashtags).most_common(10),
            content_categories=dict(content_types),
            urls=urls,
            posting_timeline=dict(timeline),
            tweets=tweets_data,
            languages=dict(languages)
        )
        
        return analysis, next_cursor

def main():
    analyzer = TwitterUserAnalyzer()
    username = input("Enter Twitter/X username (without @): ")
    show_content = input("Show full tweets in report? (y/n): ").lower() == 'y'
    translate = input("Enable translation for non-English tweets? (y/n): ").lower() == 'y'
    export = input("Export tweets? (json/csv/n): ").lower()
    
    cursor = None
    all_analyses = []
    
    while True:
        try:
            analysis, next_cursor = analyzer.analyze_user(
                username, 
                translate=translate,
                start_cursor=cursor
            )
            
            all_analyses.append(analysis)
            report = analyzer.generate_report(analysis, show_tweets=show_content)
            print(report)
            
            if export in ['json', 'csv']:
                filepath = analyzer.export_tweets(analysis, format=export)
                print(f"\nTweets exported to: {filepath}")
            
            if not next_cursor:
                print("\nNo more tweets available.")
                break
                
            continue_fetch = input("\nFetch next 100 tweets? (y/n): ").lower() == 'y'
            if not continue_fetch:
                break
                
            cursor = next_cursor
            
        except Exception as e:
            print(f"Error: {str(e)}")
            break

if __name__ == "__main__":
    main()
