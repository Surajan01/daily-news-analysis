#!/usr/bin/env python3
"""
Sokin Payments News Analyzer
Sophisticated analysis tool for payments industry news with Sokin business context
"""

import requests
import json
import os
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import re
import time

@dataclass
class NewsArticle:
    title: str
    url: str
    content: str
    source: str
    published_date: str
    hash_id: str

@dataclass
class SokinAnalysis:
    title: str
    url: str
    source: str
    published_date: str
    summary_bullets: List[str]
    so_what_bullets: List[str]
    sentiment_category: str
    sentiment_direction: str  # "up", "down", "neutral"
    business_impact_score: int  # 1-5 scale
    key_topics: List[str]
    full_analysis: str

class SokinNewsAnalyzer:
    def __init__(self):
        self.claude_api_key = os.getenv('CLAUDE_API_KEY')
        self.power_automate_url = os.getenv('TEAMS_WEBHOOK_URL')
        
        # Target publications for payments news (with scheduling info)
        self.target_sources = {
            'PYMNTS': {'url': 'https://www.pymnts.com/', 'frequency': 'daily'},
            'Finextra': {'url': 'https://www.finextra.com/', 'frequency': 'daily'},
            'Payments Journal': {'url': 'https://www.paymentsjournal.com/', 'frequency': 'daily'},
            'Fintech Brain Food': {'url': 'https://www.fintechbrainfood.com/', 'frequency': 'weekly'},
            'Fintech Magazine': {'url': 'https://fintechmagazine.com/articles', 'frequency': 'daily'}
        }
        
        # Sokin business context for AI analysis
        self.sokin_context = """
        Sokin simplifies global payments by removing borders, barriers, and burdens for businesses.
        
        Key Value Propositions:
        - Accept multi-currency payments and settle in like-for-like currency accounts
        - Minimize domestic and international transaction fees
        - Support 75+ currencies and 200+ countries
        - Multi-currency IBAN accounts and local currency accounts (USD, GBP, EUR)
        - Bulk payment integration
        
        Target Pain Points Sokin Solves:
        - Complexity of cross-border transactions
        - High costs of international payments
        - Difficulty managing multiple currencies
        - Inefficient global payment processes
        """
        
        # Sentiment categories specific to Sokin's business
        self.sentiment_categories = [
            "Cross-Border Payment Trends",
            "Currency & FX Market", 
            "Multi-Currency Solutions",
            "International Commerce",
            "Payment Cost Pressures",
            "Regulatory Changes",
            "Fintech Competition"
        ]
        
        # File to track processed articles (simple JSON storage)
        self.processed_articles_file = 'processed_articles.json'

    def should_check_source_today(self, source_name: str, source_config: dict) -> bool:
        """Determine if we should check a source today based on its frequency"""
        if source_config['frequency'] == 'daily':
            return True
        elif source_config['frequency'] == 'weekly':
            # Only check weekly sources on Monday (weekday 0)
            return datetime.now().weekday() == 0
        return True
        
    def load_processed_articles(self) -> set:
        """Load list of already processed article hashes"""
        try:
            if os.path.exists(self.processed_articles_file):
                with open(self.processed_articles_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_hashes', []))
            return set()
        except Exception as e:
            print(f"Error loading processed articles: {e}")
            return set()
    
    def save_processed_article(self, article_hash: str):
        """Save article hash to prevent reprocessing"""
        try:
            processed = self.load_processed_articles()
            processed.add(article_hash)
            
            data = {
                'processed_hashes': list(processed),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.processed_articles_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving processed article: {e}")
    
    def create_article_hash(self, title: str, url: str) -> str:
        """Create unique hash for article to prevent duplicates"""
        content = f"{title}|{url}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def scrape_articles_from_source(self, source_name: str, source_url: str, max_articles: int = 3) -> List[NewsArticle]:
        """Scrape recent articles from a news source"""
        articles = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(source_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Generic article extraction (will need refinement per site)
            article_links = []
            
            # Common selectors for article links
            selectors = [
                'a[href*="article"]',
                'a[href*="/news/"]',
                'a[href*="/story/"]',
                '.article-title a',
                '.headline a',
                'h2 a',
                'h3 a'
            ]
            
            for selector in selectors:
                links = soup.select(selector)
                article_links.extend(links)
                if len(article_links) >= max_articles:
                    break
            
            # Process found links
            for link in article_links[:max_articles]:
                try:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    
                    if not href or not title:
                        continue
                    
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = source_url.rstrip('/') + href
                    elif not href.startswith('http'):
                        continue
                    
                    # Create article hash for duplicate detection
                    article_hash = self.create_article_hash(title, href)
                    
                    # Skip if already processed
                    if article_hash in self.load_processed_articles():
                        continue
                    
                    # Scrape article content
                    article_content = self.scrape_article_content(href)
                    
                    if article_content and self.is_payments_related(title + " " + article_content):
                        article = NewsArticle(
                            title=title,
                            url=href,
                            content=article_content,
                            source=source_name,
                            published_date=datetime.now().strftime('%Y-%m-%d'),
                            hash_id=article_hash
                        )
                        articles.append(article)
                        
                        # Small delay to be respectful
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"Error processing article link: {e}")
                    continue
            
        except Exception as e:
            print(f"Error scraping {source_name}: {e}")
        
        return articles
    
    def scrape_article_content(self, url: str) -> str:
        """Extract main content from article URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Try to find main content
            content_selectors = [
                '.article-content',
                '.post-content', 
                '.entry-content',
                'article',
                '.content',
                'main'
            ]
            
            content = ""
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    content = element.get_text(strip=True)
                    break
            
            # Fallback to body text
            if not content:
                content = soup.get_text()
            
            # Clean and truncate content
            content = re.sub(r'\s+', ' ', content).strip()
            return content[:3000]  # Limit content length
            
        except Exception as e:
            print(f"Error scraping article content from {url}: {e}")
            return ""
    
    def is_payments_related(self, text: str) -> bool:
        """Check if article is related to payments/fintech"""
        payments_keywords = [
            'payment', 'fintech', 'financial', 'banking', 'currency', 'cross-border',
            'transaction', 'money', 'digital wallet', 'cryptocurrency', 'blockchain',
            'remittance', 'foreign exchange', 'forex', 'settlement', 'clearing',
            'card', 'visa', 'mastercard', 'paypal', 'stripe', 'regulation', 'compliance'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in payments_keywords)
    
    def analyze_article_with_ai(self, article: NewsArticle) -> Optional[SokinAnalysis]:
        """Analyze article using AI with Sokin business context"""
        try:
            prompt = f"""
            You are a business analyst for Sokin, a global payments company. Analyze this payments industry article:
            
            SOKIN CONTEXT:
            {self.sokin_context}
            
            ARTICLE:
            Title: {article.title}
            Source: {article.source}
            Content: {article.content}
            
            Provide analysis in this JSON format:
            {{
                "summary_bullets": ["bullet 1", "bullet 2", "bullet 3"],
                "so_what_bullets": ["why this matters to Sokin", "business implications", "strategic considerations"],
                "sentiment_category": "one of: {', '.join(self.sentiment_categories)}",
                "sentiment_direction": "up/down/neutral",
                "business_impact_score": 1-5,
                "key_topics": ["topic1", "topic2", "topic3"],
                "full_analysis": "detailed paragraph on what this means for Sokin"
            }}
            
            Focus on:
            - How this impacts cross-border payments
            - Opportunities/threats for multi-currency solutions
            - Market trends affecting international commerce
            - Regulatory changes impacting global payments
            """
            
            # Using Claude API
            headers = {
                'x-api-key': self.claude_api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': 'claude-3-sonnet-20240229',
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            }
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                ai_response = response.json()
                analysis_text = ai_response['content'][0]['text']
                print(f"AI analysis received for: {article.title[:50]}...")
            else:
                print(f"AI API error - Status: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return None
                
                # Parse JSON response
                analysis_data = json.loads(analysis_text)
                
                # Create SokinAnalysis object
                sokin_analysis = SokinAnalysis(
                    title=article.title,
                    url=article.url,
                    source=article.source,
                    published_date=article.published_date,
                    summary_bullets=analysis_data['summary_bullets'],
                    so_what_bullets=analysis_data['so_what_bullets'],
                    sentiment_category=analysis_data['sentiment_category'],
                    sentiment_direction=analysis_data['sentiment_direction'],
                    business_impact_score=analysis_data['business_impact_score'],
                    key_topics=analysis_data['key_topics'],
                    full_analysis=analysis_data['full_analysis']
                )
                
                return sokin_analysis
                
        except Exception as e:
            print(f"Error analyzing article with AI: {e}")
            print(f"Response status: {response.status_code if 'response' in locals() else 'No response'}")
            if 'response' in locals() and hasattr(response, 'text'):
                print(f"Response content: {response.text[:500]}")
            return None
    
    def create_teams_message(self, analyses: List[SokinAnalysis]) -> dict:
        """Create Teams message with proper Adaptive Card format"""
        if not analyses:
            return {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                            "type": "AdaptiveCard",
                            "version": "1.2",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "text": f"📊 Daily Payments Analysis - {datetime.now().strftime('%B %d, %Y')}",
                                    "size": "Large",
                                    "weight": "Bolder"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": "No new relevant payments articles found today."
                                }
                            ]
                        }
                    }
                ]
            }
        
        # Build card body with analyses
        card_body = [
            {
                "type": "TextBlock",
                "text": f"📊 Daily Payments Analysis - {datetime.now().strftime('%B %d, %Y')}",
                "size": "Large",
                "weight": "Bolder"
            },
            {
                "type": "TextBlock",
                "text": f"Found {len(analyses)} relevant articles",
                "wrap": True
            }
        ]
        
        # Add each analysis as simple text blocks
        for i, analysis in enumerate(analyses[:3], 1):
            direction = "⬆️" if analysis.sentiment_direction == "up" else "⬇️" if analysis.sentiment_direction == "down" else "↔️"
            stars = "⭐" * analysis.business_impact_score
            
            # Article title
            card_body.append({
                "type": "TextBlock",
                "text": f"{i}. {analysis.title}",
                "size": "Medium",
                "weight": "Bolder",
                "wrap": True
            })
            
            # Source and metadata
            card_body.append({
                "type": "TextBlock",
                "text": f"Source: {analysis.source} | {analysis.sentiment_category} {direction} | Impact: {stars}",
                "size": "Small",
                "wrap": True
            })
            
            # Summary
            summary_text = "Summary: " + "; ".join(analysis.summary_bullets)
            card_body.append({
                "type": "TextBlock",
                "text": summary_text,
                "wrap": True
            })
            
            # So what
            so_what_text = "So What for Sokin: " + "; ".join(analysis.so_what_bullets)
            card_body.append({
                "type": "TextBlock",
                "text": so_what_text,
                "wrap": True
            })
            
            # Separator
            if i < min(len(analyses), 3):
                card_body.append({
                    "type": "TextBlock",
                    "text": "---",
                    "separator": True
                })
        
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": card_body
                    }
                }
            ]
        }
    
    def send_to_teams(self, message: dict) -> bool:
        """Send analysis to Teams via Power Automate"""
        try:
            response = requests.post(
                self.power_automate_url,
                headers={'Content-Type': 'application/json'},
                json=message,
                timeout=30
            )
            
            if response.status_code in [200, 202]:
                print("✅ Analysis sent to Teams successfully!")
                return True
            else:
                print(f"❌ Failed to send to Teams. Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending to Teams: {e}")
            return False
    
    def run_daily_analysis(self):
        """Main method to run complete daily analysis"""
        print(f"🚀 Starting Sokin daily payments analysis at {datetime.now()}")
        
        all_articles = []
        all_analyses = []
        
        # Scrape articles from all sources
        for source_name, source_config in self.target_sources.items():
            # Check if we should scrape this source today
            if not self.should_check_source_today(source_name, source_config):
                print(f"⏭️ Skipping {source_name} (weekly source, not Monday)")
                continue
                
            print(f"📰 Scraping {source_name}...")
            articles = self.scrape_articles_from_source(source_name, source_config['url'])
            all_articles.extend(articles)
            print(f"Found {len(articles)} new articles from {source_name}")
        
        print(f"📊 Total new articles found: {len(all_articles)}")
        
        # Analyze each article
        for article in all_articles:
            print(f"🔍 Analyzing: {article.title}")
            analysis = self.analyze_article_with_ai(article)
            
            if analysis:
                all_analyses.append(analysis)
                # Mark as processed
                self.save_processed_article(article.hash_id)
            
            # Rate limiting
            time.sleep(2)
        
        # Sort by business impact score
        all_analyses.sort(key=lambda x: x.business_impact_score, reverse=True)
        
        print(f"📈 Completed analysis of {len(all_analyses)} articles")
        
        # Send to Teams
        if all_analyses:
            teams_message = self.create_teams_message(all_analyses)
            self.send_to_teams(teams_message)
        else:
            # Send "no news" message
            no_news_message = {
                "text": f"📰 Daily Payments Analysis - {datetime.now().strftime('%B %d, %Y')}\n\nNo new relevant payments articles found today.",
                "attachments": []
            }
            self.send_to_teams(no_news_message)
        
        print("✅ Daily analysis complete!")

if __name__ == "__main__":
    analyzer = SokinNewsAnalyzer()
    analyzer.run_daily_analysis()
