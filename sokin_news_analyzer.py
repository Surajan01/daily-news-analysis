def send_detailed_to_teams(self, message: dict) -> bool:
        """Send detailed analysis to comprehensive Teams channel"""
        try:
            response = requests.post(
                self.detailed_webhook_url,
                headers={'Content-Type': 'application/json'},
                json=message,
                timeout=30
            )
            
            if response.status_code in [200, 202]:
                print("✅ Detailed analysis sent to Teams successfully!")
                return True
            else:
                print(f"❌ Failed to send detailed analysis to Teams. Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending detailed analysis to Teams: {e}")
            return False    def create_detailed_teams_message(self, analyses: List[SokinAnalysis]) -> dict:
        """Create comprehensive Teams message with ALL analyses"""
        if not analyses:
            return {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [{
                            "type": "TextBlock",
                            "text": "📈 Comprehensive Daily Analysis - No articles found today",
                            "size": "Large",
                            "weight": "Bolder"
                        }]
                    }
                }]
            }
        
        # Build comprehensive card body
        card_body = [{
            "type": "TextBlock",
            "text": f"📈 Comprehensive Daily Analysis - {datetime.now().strftime('%B %d, %Y')}",
            "size": "Large",
            "weight": "Bolder"
        }, {
            "type": "TextBlock",
            "text": f"Complete analysis of all {len(analyses)} articles found today",
            "wrap": True,
            "color": "Accent"
        }]
        
        # Add all analyses
        for i, analysis in enumerate(analyses, 1):
            direction = "⬆️" if analysis.sentiment_direction == "up" else "⬇️" if analysis.sentiment_direction == "down" else "↔️"
            stars = "⭐" * analysis.business_impact_score
            
            # Article title
            card_body.append({
                "type": "TextBlock",
                "text": f"**{i}. {analysis.title}**",
                "size": "Medium",
                "weight": "Bolder",
                "wrap": True,
                "spacing": "Medium"
            })
            
            # Source and metadata
            card_body.append({
                "type": "TextBlock",
                "text": f"**Source:** {analysis.source} | **Category:** {analysis.sentiment_category} {direction} | **Impact:** {stars}",
                "size": "Small",
                "wrap": True,
                "color": "Accent"
            })
            
            # Summary
            summary_text = "**Summary:** " + "; ".join(analysis.summary_bullets)
            card_body.append({
                "type": "TextBlock",
                "text": summary_text,
                "wrap": True,
                "size": "Default"
            })
            
            # So what
            so_what_text = "**So What for Sokin:** " + "; ".join(analysis.so_what_bullets)
            card_body.append({
                "type": "TextBlock",
                "text": so_what_text,
                "wrap": True,
                "size": "Default"
            })
            
            # Article link
            card_body.append({
                "type": "ActionSet",
                "actions": [{
                    "type": "Action.OpenUrl",
                    "title": "📖 Read Full Article",
                    "url": analysis.url
                }],
                "spacing": "Small"
            })
            
            # Separator
            if i < len(analyses):
                card_body.append({
                    "type": "TextBlock",
                    "text": "---",
                    "separator": True,
                    "spacing": "Medium"
                })
        
        return {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": card_body
                }
            }]
        }#!/usr/bin/env python3
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
        self.power_automate_url = os.getenv('TEAMS_WEBHOOK_URL')  # Main briefing channel
        self.detailed_webhook_url = os.getenv('TEAMS_DETAILED_WEBHOOK_URL')  # Detailed analysis channel
        
        # Claude model - easily updatable
        self.claude_model = os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
        
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
        
        # Sentiment categories specific to Sokin's business - more diverse
        self.sentiment_categories = [
            "Cross-Border Payment Competition",
            "Multi-Currency Solution Demand", 
            "SME Payment Pain Points",
            "Regulatory & Compliance Changes",
            "Currency Market Volatility",
            "Digital Payment Adoption",
            "Banking Infrastructure Changes",
            "Fintech Partnership Opportunities",
            "International Trade Volumes",
            "Payment Cost Pressures"
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
            # Fallback: use date-based filtering if file tracking fails
            return self.get_processed_articles_fallback()
    
    def get_processed_articles_fallback(self) -> set:
        """Fallback method: assume articles from today are already processed after first run"""
        # Simple time-based deduplication as fallback
        # In production, this prevents reprocessing within the same day
        today = datetime.now().strftime('%Y-%m-%d')
        return set() if not hasattr(self, '_daily_run_marker') else set(['daily_run_completed'])
    
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
        """Scrape recent articles from a news source with anti-blocking measures"""
        articles = []
        
        try:
            # Rotate user agents to appear more human
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
            ]
            
            import random
            selected_user_agent = random.choice(user_agents)
            
            headers = {
                'User-Agent': selected_user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            
            # Random delay before request
            time.sleep(random.uniform(2, 5))
            
            response = requests.get(source_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Site-specific selectors for better accuracy - updated for current site structures
            article_links = []
            
            if 'pymnts.com' in source_url.lower():
                # PYMNTS uses these structures
                selectors = [
                    'h2 a[href*="/news/"]',
                    'h3 a[href*="/news/"]', 
                    '.post-title a',
                    '.entry-title a',
                    'a[href*="/article/"]',
                    'a[href*="pymnts.com"]',
                    'h2 a',
                    'h3 a'
                ]
            elif 'finextra.com' in source_url.lower():
                # Finextra structures
                selectors = [
                    'a[href*="/newsarticle/"]',
                    'a[href*="/news/"]',
                    '.headline a',
                    '.newsheadline a',
                    'h2 a',
                    'h3 a',
                    '.title a'
                ]
            elif 'paymentsjournal.com' in source_url.lower():
                # Payments Journal structures
                selectors = [
                    '.entry-title a',
                    '.post-title a',
                    'h2 a',
                    'h1 a',
                    'article h2 a',
                    'article h3 a'
                ]
            elif 'fintechmagazine.com' in source_url.lower():
                # Fintech Magazine structures
                selectors = [
                    'a[href*="/articles/"]',
                    '.article-title a',
                    '.headline a',
                    'h2 a',
                    'h3 a',
                    '.title a'
                ]
            elif 'fintechbrainfood.com' in source_url.lower():
                # Fintech Brain Food structures
                selectors = [
                    '.post-title a',
                    'h1 a',
                    'h2 a',
                    '.entry-title a',
                    'article a'
                ]
            else:
                # Much broader generic selectors
                selectors = [
                    'a[href*="article"]',
                    'a[href*="/news/"]',
                    'a[href*="/story/"]',
                    'a[href*="/post/"]',
                    'a[href*="/blog/"]',
                    '.article-title a',
                    '.post-title a',
                    '.entry-title a',
                    '.headline a',
                    '.title a',
                    'h1 a',
                    'h2 a',
                    'h3 a',
                    'article a',
                    '.content a',
                    'main a'
                ]
            
            print(f"🔍 Trying {len(selectors)} different selectors for {source_name}...")
            
            for i, selector in enumerate(selectors):
                try:
                    links = soup.select(selector)
                    print(f"   Selector {i+1} ('{selector}'): found {len(links)} links")
                    
                    # Filter for likely article links
                    filtered_links = []
                    for link in links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        
                        # Must have href and meaningful text
                        if not href or not text or len(text) < 10:
                            continue
                            
                        # Skip obvious non-articles
                        skip_words = ['home', 'about', 'contact', 'privacy', 'terms', 'subscribe', 'login', 'register']
                        if any(word in text.lower() for word in skip_words):
                            continue
                            
                        # Skip navigation links
                        if any(word in href.lower() for word in ['menu', 'nav', 'footer', 'header', 'sidebar']):
                            continue
                            
                        filtered_links.append(link)
                    
                    print(f"   After filtering: {len(filtered_links)} potential articles")
                    article_links.extend(filtered_links)
                    
                    if len(article_links) >= max_articles * 3:  # Get enough to work with
                        break
                        
                except Exception as e:
                    print(f"   Error with selector '{selector}': {e}")
                    continue
            
            # Process found links with better error handling
            processed_count = 0
            print(f"🔍 Processing {len(article_links)} potential article links...")
            
            for link in article_links:
                if processed_count >= max_articles:
                    break
                    
                try:
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    
                    if not href or not title or len(title) < 10:
                        continue
                    
                    print(f"📝 Found potential article: {title[:60]}...")
                    
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = source_url.rstrip('/') + href
                    elif not href.startswith('http'):
                        continue
                    
                    # Skip if URL looks like pagination or non-article
                    skip_patterns = ['page=', 'category=', 'tag=', 'author=', '#comment']
                    if any(pattern in href for pattern in skip_patterns):
                        print(f"⏭️ Skipping non-article URL: {href}")
                        continue
                    
                    # Create article hash for duplicate detection
                    article_hash = self.create_article_hash(title, href)
                    
                    # Skip if already processed
                    if article_hash in self.load_processed_articles():
                        print(f"⏭️ Skipping already processed: {title[:50]}...")
                        continue
                    
                    print(f"🔍 Scraping content for: {title[:50]}...")
                    
                    # Add delay between article scrapes
                    time.sleep(random.uniform(3, 6))
                    
                    # Scrape article content with retries
                    article_content = self.scrape_article_content_with_retry(href)
                    
                    if not article_content:
                        print(f"❌ No content extracted for: {title[:50]}...")
                        continue
                    
                    if not self.is_payments_related(title + " " + article_content):
                        print(f"⏭️ Not payments-related: {title[:50]}...")
                        continue
                    
                    article = NewsArticle(
                        title=title,
                        url=href,
                        content=article_content,
                        source=source_name,
                        published_date=datetime.now().strftime('%Y-%m-%d'),
                        hash_id=article_hash
                    )
                    articles.append(article)
                    processed_count += 1
                    print(f"✅ Successfully scraped: {title[:50]}...")
                        
                except Exception as e:
                    print(f"❌ Error processing article link: {e}")
                    continue
            
        except Exception as e:
            print(f"Error scraping {source_name}: {e}")
        
        return articles
    
    def scrape_article_content_with_retry(self, url: str, max_retries: int = 3) -> str:
        """Extract main content from article URL with retry logic"""
        for attempt in range(max_retries):
            try:
                # Different user agents for retries
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
                
                import random
                headers = {
                    'User-Agent': random.choice(user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Referer': 'https://www.google.com/',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                # Progressive delay for retries
                if attempt > 0:
                    time.sleep(random.uniform(5, 10) * attempt)
                
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove unwanted elements
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
                    element.decompose()
                
                # Try multiple content selectors in order of preference
                content_selectors = [
                    '[data-module="ArticleBody"]',  # Common in news sites
                    '.article-content',
                    '.post-content', 
                    '.entry-content',
                    '.article-body',
                    '.content-body',
                    'article .content',
                    'article',
                    '.content',
                    'main .text',
                    'main'
                ]
                
                content = ""
                for selector in content_selectors:
                    element = soup.select_one(selector)
                    if element:
                        content = element.get_text(strip=True)
                        if len(content) > 200:  # Ensure we got substantial content
                            break
                
                # Fallback to body text if nothing found
                if not content or len(content) < 100:
                    content = soup.get_text()
                
                # Clean and truncate content
                content = re.sub(r'\s+', ' ', content).strip()
                
                # Remove common noise
                noise_patterns = [
                    r'Subscribe to.*?newsletter',
                    r'Follow us on.*?social media',
                    r'Share this article',
                    r'Comments.*?below',
                    r'Cookie policy',
                    r'Privacy policy'
                ]
                
                for pattern in noise_patterns:
                    content = re.sub(pattern, '', content, flags=re.IGNORECASE)
                
                return content[:4000]  # Increased limit for better analysis
                
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_retries - 1:
                    print(f"All attempts failed for {url}")
                    return ""
            except Exception as e:
                print(f"Error scraping article content from {url}: {e}")
                return ""
        
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
            
            IMPORTANT SENTIMENT DIRECTION GUIDELINES:
            - UP ⬆️: Trend is INCREASING (more competition, higher demand, growing adoption, rising costs, etc.)
            - DOWN ⬇️: Trend is DECREASING (less competition, declining demand, reduced adoption, falling costs, etc.)
            - NEUTRAL ↔️: Trend is stable, mixed, or unclear direction
            
            EXAMPLES:
            - New cross-border payment competitor launches = UP ⬆️ (increased competition)
            - Demand for multi-currency solutions grows = UP ⬆️ (increased demand)
            - SME payment costs rising = UP ⬆️ (increased cost pressures)
            - Regulatory barriers being removed = DOWN ⬇️ (decreased barriers)
            - International trade volumes declining = DOWN ⬇️ (decreased trade)
            - Currency volatility increasing = UP ⬆️ (increased volatility)
            
            The arrow shows TREND DIRECTION, not whether it's good/bad for Sokin.
            
            IMPORTANT SCORING GUIDELINES:
            - Business Impact Score: 1=minimal relevance, 2=low relevance, 3=moderate relevance, 4=high relevance, 5=critical for Sokin
            - Be critical and realistic with scoring - use the full 1-5 range
            
            SOKIN IMPACT SCORING CRITERIA:
            Score 5 (Critical): Direct competitive threats, major regulatory changes affecting cross-border payments, significant multi-currency market shifts
            Score 4 (High): New competitors in cross-border space, relevant fintech partnerships, SME payment trends, currency regulation changes
            Score 3 (Moderate): General fintech trends affecting payments, banking infrastructure changes, broader market movements
            Score 2 (Low): Tangentially related financial news, general tech trends, distant market developments  
            Score 1 (Minimal): General business news with minimal payment relevance, unrelated financial topics
            
            EXAMPLES:
            - New cross-border payment platform launch = Score 4-5
            - Major bank entering SME payments = Score 4-5  
            - General fintech funding news = Score 2-3
            - Cryptocurrency regulation changes = Score 3-4 (depending on impact on cross-border)
            - Banking merger with no payment focus = Score 1-2
            
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
                'model': self.claude_model,
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
                "text": f"📊 Daily Payments Briefing - {datetime.now().strftime('%B %d, %Y')}",
                "size": "Large",
                "weight": "Bolder"
            },
            {
                "type": "TextBlock",
                "text": f"Top 3 insights from {len(analyses)} articles analyzed",
                "wrap": True,
                "color": "Accent"
            }
        ]
        
        # Add each analysis as simple text blocks
        for i, analysis in enumerate(analyses[:3], 1):
            direction = "⬆️" if analysis.sentiment_direction == "up" else "⬇️" if analysis.sentiment_direction == "down" else "↔️"
            stars = "⭐" * analysis.business_impact_score
            
            # Article title with proper spacing
            card_body.append({
                "type": "TextBlock",
                "text": f"**{i}. {analysis.title}**",
                "size": "Medium",
                "weight": "Bolder",
                "wrap": True,
                "spacing": "Medium"
            })
            
            # Source and metadata
            card_body.append({
                "type": "TextBlock",
                "text": f"**Source:** {analysis.source} | **Category:** {analysis.sentiment_category} {direction} | **Impact:** {stars}",
                "size": "Small",
                "wrap": True,
                "color": "Accent"
            })
            
            # Summary with bullet points
            card_body.append({
                "type": "TextBlock",
                "text": "**Summary:**",
                "weight": "Bolder",
                "size": "Small",
                "spacing": "Small"
            })
            
            for bullet in analysis.summary_bullets:
                card_body.append({
                    "type": "TextBlock",
                    "text": f"• {bullet}",
                    "size": "Default",
                    "wrap": True
                })
            
            # So what with bullet points  
            card_body.append({
                "type": "TextBlock",
                "text": "**So What for Sokin:**",
                "weight": "Bolder",
                "size": "Small",
                "spacing": "Small"
            })
            
            for bullet in analysis.so_what_bullets:
                card_body.append({
                    "type": "TextBlock",
                    "text": f"• {bullet}",
                    "size": "Default",
                    "wrap": True
                })
            
            # Add article link button
            card_body.append({
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "📖 Read Full Article",
                        "url": analysis.url
                    }
                ],
                "spacing": "Small"
            })
            
            # Separator between articles
            if i < min(len(analyses), 3):
                card_body.append({
                    "type": "TextBlock",
                    "text": "---",
                    "separator": True,
                    "spacing": "Medium"
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
            print(f"📍 URL: {source_config['url']}")
            articles = self.scrape_articles_from_source(source_name, source_config['url'])
            print(f"📊 Raw articles found: {len(articles)}")
            all_articles.extend(articles)
            print(f"✅ Found {len(articles)} new articles from {source_name}")
        
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
            print(f"📊 Sending analysis of {len(all_analyses)} articles to Teams...")
            
            # Send brief summary to main channel
            teams_message = self.create_teams_message(all_analyses)
            success_main = self.send_to_teams(teams_message)
            
            # Check for detailed webhook configuration
            print(f"🔍 Checking for detailed webhook... Configured: {bool(self.detailed_webhook_url)}")
            
            # Send detailed analysis to comprehensive channel (if configured)
            if self.detailed_webhook_url:
                print("📈 Sending detailed analysis to comprehensive channel...")
                detailed_message = self.create_detailed_teams_message(all_analyses)
                success_detailed = self.send_detailed_to_teams(detailed_message)
                print(f"📈 Detailed analysis sent: {'✅' if success_detailed else '❌'}")
            else:
                print("📝 Detailed webhook not configured - skipping comprehensive analysis")
                print("💡 To enable: Add TEAMS_DETAILED_WEBHOOK_URL to GitHub secrets")
                
        else:
            print("📭 No articles to analyze - sending 'no news' message")
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
