import feedparser
import logging
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin
from database import Database
from time import mktime
from bs4 import BeautifulSoup
import requests
from requests.exceptions import RequestException
from logger import rss_logger as logger
import sqlite3

class RSSMonitor:
    """
    A class to monitor RSS feeds and extract article information.
    """
    
    def __init__(self, db: Database, max_entries: int = 10, max_retries: int = 3, retry_delay: int = 5):
        """
        Initialize the RSS monitor.
        
        Args:
            db (Database): Database instance for storing feed information
            max_entries (int): Maximum number of entries to process per feed
            max_retries (int): Maximum number of retries for failed requests
            retry_delay (int): Delay between retries in seconds
        """
        self.max_entries = max_entries
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.db = db
        self._cached_entries = []  # Cache for entries
        
        # Load configuration
        with open('config.json', 'r') as f:
            config = json.load(f)
            self.config = config.get('monitor', {})
        
        logger.info("RSS Monitor initialized")
    
    def _fetch_url(self, url: str, is_feed: bool = True) -> Optional[str]:
        """
        Fetch content from a URL with retry logic.
        
        Args:
            url (str): The URL to fetch
            is_feed (bool): Whether this is an RSS feed URL (affects error handling)
            
        Returns:
            Optional[str]: The content or None if failed
        """
        timeout = self.config.get('rss_timeout', 10)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    # Add increasing delay between retries
                    delay = self.retry_delay * (attempt + 1)
                    logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                
                logger.info(f"Fetching {'RSS feed' if is_feed else 'article'}: {url} (attempt {attempt + 1}/{self.max_retries})")
                response = requests.get(url, timeout=timeout, headers=headers)
                
                # Handle common status codes
                if response.status_code == 403:
                    logger.warning(f"Access forbidden to {url}. Site may have anti-scraping measures.")
                    # Try with a different user agent on next attempt
                    headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
                    continue
                elif response.status_code == 429:
                    logger.warning(f"Rate limited by {url}. Waiting longer before retry...")
                    time.sleep(self.retry_delay * 5)  # Wait 5 times longer
                    continue
                elif response.status_code == 404:
                    logger.error(f"Page not found: {url}")
                    return None
                
                response.raise_for_status()
                
                # Check if we got a valid response
                content_type = response.headers.get('content-type', '').lower()
                if not is_feed and 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                    logger.warning(f"Unexpected content type from {url}: {content_type}")
                    if attempt < self.max_retries - 1:
                        continue
                    return None
                
                return response.content
                
            except RequestException as e:
                logger.error(f"Error fetching {'feed' if is_feed else 'article'} {url}: {e}")
                if attempt < self.max_retries - 1:
                    continue
                return None
            except Exception as e:
                logger.error(f"Unexpected error fetching {'feed' if is_feed else 'article'} {url}: {e}")
                if attempt < self.max_retries - 1:
                    continue
                return None
        
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    def _fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse an RSS feed with retry logic.
        
        Args:
            url (str): The feed URL to fetch
            
        Returns:
            Optional[feedparser.FeedParserDict]: The parsed feed data or None if failed
        """
        content = self._fetch_url(url, is_feed=True)
        if not content:
            return None
            
        feed_data = feedparser.parse(content)
        if feed_data.bozo:  # Feed parsing error
            logger.error(f"Error parsing feed {url}: {feed_data.bozo_exception}")
            return None
            
        return feed_data
    
    def _fetch_article(self, url: str) -> Optional[str]:
        """
        Fetch article content from URL.
        
        Args:
            url (str): The article URL to fetch
            
        Returns:
            Optional[str]: The article HTML content or None if failed
        """
        return self._fetch_url(url, is_feed=False)
    
    def _clean_content(self, content: str) -> str:
        """
        Clean the content by removing JSON-like formatting and other artifacts.
        
        Args:
            content (str): The content to clean
            
        Returns:
            str: The cleaned content
        """
        try:
            # Try to parse as JSON if it looks like JSON
            if content.strip().startswith('[[{') and content.strip().endswith('}]]'):
                data = json.loads(content.strip('[]'))
                if isinstance(data, dict) and 'value' in data:
                    content = data['value']
        except json.JSONDecodeError:
            pass
        
        # Remove any remaining JSON-like artifacts
        content = content.replace('[[{', '').replace('}]]', '')
        content = content.replace('"value":', '')
        content = content.replace('""', '')
        
        # Remove any HTML comments
        content = content.replace('<!--', '').replace('-->', '')
        
        # Remove any remaining quotes and special characters
        content = content.replace('"', '').replace('"', '').replace('"', '')
        content = content.replace('​', '')  # Remove zero-width space
        
        # Remove any remaining HTML tags
        content = BeautifulSoup(content, 'html.parser').get_text()
        
        # Remove any text that looks like a footer
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if not any(x in line.lower() for x in ['first appeared on', 'the post']):
                cleaned_lines.append(line)
        content = ' '.join(cleaned_lines)
        
        return content.strip()
    
    def _extract_paragraphs(self, soup: BeautifulSoup, is_article_page: bool = False) -> List[str]:
        """
        Extract paragraphs from BeautifulSoup object.
        
        Args:
            soup (BeautifulSoup): The parsed HTML
            is_article_page (bool): Whether this is a full article page (affects content extraction)
            
        Returns:
            List[str]: List of extracted paragraphs
        """
        paragraphs = []
        
        # Find the main content area
        content_classes = self.config.get('rss_content_classes', [
            'entry-content',
            'post-content',
            'article-content',
            'content',
            'post',
            'article',
            'entry',
            'description',
            'summary',
            'text'
        ])
        
        # Try to find the main content area
        main_content = None
        for class_name in content_classes:
            main_content = soup.find(class_=class_name)
            if main_content:
                break
        
        # If no main content area found, try to find the article body
        if not main_content:
            main_content = soup.find('article') or soup.find('main') or soup.find('body')
        
        if main_content:
            # Remove unwanted elements
            for element in main_content.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Extract paragraphs
            for p in main_content.find_all('p'):
                text = p.get_text().strip()
                if text and len(text) >= self.config.get('rss_min_paragraph_length', 20):
                    paragraphs.append(text)
        
        # If no paragraphs found, try a more general approach
        if not paragraphs:
            for p in soup.find_all('p'):
                text = p.get_text().strip()
                if text and len(text) >= self.config.get('rss_min_paragraph_length', 20):
                    paragraphs.append(text)
        
        # Clean up paragraphs
        cleaned_paragraphs = []
        for p in paragraphs:
            # Remove any remaining HTML tags
            p = BeautifulSoup(p, 'html.parser').get_text()
            
            # Remove any text that looks like a footer or header
            if not any(x in p.lower() for x in [
                'first appeared on',
                'the post',
                'all rights reserved',
                'copyright',
                'follow us',
                'subscribe',
                'newsletter',
                'advertisement',
                'sponsored',
                'related articles',
                'share this',
                'comments',
                'login',
                'register'
            ]):
                cleaned_paragraphs.append(p)
        
        return cleaned_paragraphs
    
    def _detect_paywall(self, content: str, url: str) -> bool:
        """
        Detect if content is behind a paywall.
        Returns True if paywall detected, False otherwise.
        """
        # Only check if we have actual content
        if not content or len(content.strip()) < 100:
            return True
        
        # Common paywall indicators that actually block content
        paywall_indicators = [
            "subscribe to continue reading",
            "subscribe to read the full article",
            "subscribe to access",
            "premium content",
            "subscribers only",
            "for subscribers",
            "sign in to read"
        ]
        
        # Check for definitive paywall blocks
        content_lower = content.lower()
        for indicator in paywall_indicators:
            if indicator in content_lower:
                # Only consider it a paywall if we have very little content
                # This helps ignore subscription prompts on articles we can still read
                paragraphs = [p for p in content.split('\n') if len(p.strip()) > 50]
                if len(paragraphs) < 3:  # Less than 3 substantial paragraphs
                    return True
        
        return False
    
    def _handle_paywall(self, feed_id: int, feed_url: str, article_url: str) -> None:
        """
        Handle detection of a paywalled article.
        
        Args:
            feed_id (int): The ID of the feed
            feed_url (str): The URL of the feed
            article_url (str): The URL of the paywalled article
        """
        # Record the paywall hit
        self.db.record_paywall_hit(feed_id, article_url)
        
        # Check if feed should be flagged as paywalled
        recent_hits = self.db.get_recent_paywall_hits(feed_id, days=7)
        if recent_hits >= 5:
            logger.warning(f"Feed {feed_url} has hit paywall {recent_hits} times in the last week")
            print(f"\nWARNING: Feed {feed_url} has hit paywalls {recent_hits} times in the last week.")
            print("This feed may be paywalled. Would you like to:")
            print("1. Keep monitoring this feed")
            print("2. Mark this feed as paywalled and skip it in the future")
            print("3. Remove this feed completely")
            
            while True:
                try:
                    choice = input("Enter your choice (1-3): ").strip()
                    if choice in ['1', '2', '3']:
                        break
                    print("Please enter 1, 2, or 3")
                except KeyboardInterrupt:
                    print("\nOperation cancelled. Feed will continue to be monitored.")
                    return
            
            if choice == '2':
                self.db.mark_feed_as_paywalled(feed_id)
                print(f"Feed {feed_url} has been marked as paywalled and will be skipped in the future.")
            elif choice == '3':
                self.db.remove_feed(feed_id)
                print(f"Feed {feed_url} has been removed.")
            else:
                print(f"Feed {feed_url} will continue to be monitored.")
    
    def _extract_article_content(self, url: str, feed_id: int = None, feed_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Extract article content by scraping the article page directly.
        
        Args:
            url (str): The article URL to scrape
            feed_id (int, optional): The ID of the feed this article belongs to
            feed_url (str, optional): The URL of the feed
            
        Returns:
            Optional[Dict[str, Any]]: Article content data or None if failed
        """
        content = self._fetch_article(url)
        if not content:
            return None
        
        try:
            # Check for paywall if feed tracking is enabled
            if feed_id and feed_url:
                content_str = content.decode('utf-8') if isinstance(content, bytes) else content
                if self._detect_paywall(content_str, url):
                    self._handle_paywall(feed_id, feed_url, url)
                    return None
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Try to extract title
            title = None
            title_tag = soup.find('h1') or soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Try to extract author
            author = None
            author_tag = soup.find(['a', 'span', 'p'], class_=['author', 'byline'])
            if author_tag:
                author = author_tag.get_text().strip()
            
            # Find the main content area
            content_classes = self.config.get('rss_content_classes', [
                'entry-content',
                'post-content',
                'article-content',
                'content',
                'post',
                'article',
                'entry',
                'description',
                'summary',
                'text'
            ])
            
            # Try to find the main content area
            main_content = None
            for class_name in content_classes:
                main_content = soup.find(class_=class_name)
                if main_content:
                    break
            
            # If no main content area found, try to find the article body
            if not main_content:
                main_content = soup.find('article') or soup.find('main') or soup.find('body')
            
            # Extract and clean paragraphs
            paragraphs = []
            if main_content:
                # Remove unwanted elements
                for element in main_content.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'div']):
                    if any(x in element.get('class', []) for x in ['social-share', 'related-posts', 'comments', 'advertisement']):
                        element.decompose()
                
                # Extract paragraphs
                for p in main_content.find_all('p'):
                    text = p.get_text().strip()
                    if text and len(text) >= self.config.get('rss_min_paragraph_length', 20):
                        # Clean up the text
                        text = BeautifulSoup(text, 'html.parser').get_text()
                        text = text.replace('\n', ' ').replace('\r', '')
                        text = ' '.join(text.split())  # Normalize whitespace
                        
                        # Skip if it looks like a footer or header
                        if not any(x in text.lower() for x in [
                            'first appeared on',
                            'the post',
                            'all rights reserved',
                            'copyright',
                            'follow us',
                            'subscribe',
                            'newsletter',
                            'advertisement',
                            'sponsored',
                            'related articles',
                            'share this',
                            'comments',
                            'login',
                            'register',
                            'follow us everywhere',
                            'bulgarianmilitary.com',
                            'manifesto',
                            'ethical principles'
                        ]):
                            paragraphs.append(text)
            
            # Limit to first 5 paragraphs
            paragraphs = paragraphs[:5]
            
            # Combine paragraphs into content
            content = '\n\n'.join(paragraphs)
            
            return {
                'title': title,
                'author': author,
                'paragraphs': paragraphs,
                'content': content
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from article {url}: {e}")
            return None
    
    def get_entries(self, feed_url: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get entries from active feeds.
        
        Args:
            feed_url (str, optional): Specific feed URL to fetch. If None, fetches all active feeds.
            limit (int, optional): Maximum number of entries to return
            
        Returns:
            List[Dict[str, Any]]: List of feed entries
        """
        entries = []
        
        # If a specific feed URL is provided, only fetch that feed
        if feed_url:
            try:
                feed_data = self._fetch_feed(feed_url)
                if not feed_data:
                    return []
                
                # Process entries
                for entry in feed_data.entries[:self.max_entries]:
                    try:
                        # Extract article data
                        article_data = {
                            'title': entry.get('title', ''),
                            'link': entry.get('link', ''),
                            'published_date': entry.get('published', ''),
                            'author': entry.get('author', ''),
                            'summary': entry.get('summary', ''),
                            'tags': [tag.get('term', '') for tag in entry.get('tags', [])],
                            'source_feed': feed_url
                        }
                        
                        # Convert published date to ISO format if available
                        if article_data['published_date']:
                            try:
                                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                    parsed_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                                    article_data['published_date'] = parsed_date.isoformat()
                            except Exception as e:
                                logger.warning(f"Could not parse date '{article_data['published_date']}': {e}")
                        
                        entries.append(article_data)
                        
                    except Exception as e:
                        logger.error(f"Error processing entry from feed {feed_url}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error fetching feed {feed_url}: {e}")
                return []
        else:
            # Fetch all active feeds
            feeds = self.db.get_active_feeds()
            for feed in feeds:
                try:
                    feed_data = self._fetch_feed(feed['url'])
                    if not feed_data:
                        continue
                    
                    # Process entries
                    for entry in feed_data.entries[:self.max_entries]:
                        try:
                            # Extract article data
                            article_data = {
                                'title': entry.get('title', ''),
                                'link': entry.get('link', ''),
                                'published_date': entry.get('published', ''),
                                'author': entry.get('author', ''),
                                'summary': entry.get('summary', ''),
                                'tags': [tag.get('term', '') for tag in entry.get('tags', [])],
                                'source_feed': feed['url'],
                                'feed_id': feed['id']
                            }
                            
                            # Convert published date to ISO format if available
                            if article_data['published_date']:
                                try:
                                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                        parsed_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                                        article_data['published_date'] = parsed_date.isoformat()
                                except Exception as e:
                                    logger.warning(f"Could not parse date '{article_data['published_date']}': {e}")
                            
                            entries.append(article_data)
                            
                        except Exception as e:
                            logger.error(f"Error processing entry from feed {feed['url']}: {e}")
                            continue
                        
                except Exception as e:
                    logger.error(f"Error fetching feed {feed['url']}: {e}")
                    continue
        
        # Sort entries by date (newest first) and apply limit
        entries.sort(key=lambda x: x.get('published_date', ''), reverse=True)
        if limit:
            entries = entries[:limit]
        
        return entries
    
    def get_article_links(self) -> List[str]:
        """
        Get a list of article links from all feeds.
        
        Returns:
            List[str]: List of article URLs
        """
        entries = self.get_entries()
        return [entry['link'] for entry in entries if entry.get('link')]
    
    def get_article_by_link(self, link: str) -> Optional[Dict[str, Any]]:
        """
        Get article data for a specific link.
        
        Args:
            link (str): The article link to fetch
            
        Returns:
            Optional[Dict[str, Any]]: Article data or None if not found
        """
        entries = self.get_entries()
        for entry in entries:
            if entry['link'] == link:
                # Extract article content
                content = self._extract_article_content(link)
                if not content:
                    return None
                    
                return {
                    'url': link,
                    'title': entry['title'],
                    'content': content['content'],
                    'author': entry['author'],
                    'published': entry['published_date'],
                    'tags': entry['tags'],
                    'processed': False,
                    'source_feed': entry['source_feed'],
                    'feed_id': entry['feed_id']
                }
        return None
    
    def add_feed(self, url: str) -> bool:
        """
        Add a new RSS feed to monitor.
        
        Args:
            url (str): The RSS feed URL
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db.add_feed(url)
    
    def get_feed_stats(self) -> Dict[str, Any]:
        """
        Get statistics about feeds and processed entries.
        
        Returns:
            Dict[str, Any]: Dictionary containing statistics
        """
        return self.db.get_feed_stats()
    
    def update_feed_status(self, feed_id: int, is_active: bool) -> bool:
        """
        Update the active status of a feed.
        
        Args:
            feed_id (int): The ID of the feed
            is_active (bool): Whether the feed is active
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db.update_feed_status(feed_id, is_active)
    
    def get_articles(self, limit: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get articles from RSS feeds.
        
        Args:
            limit (int, optional): Maximum number of articles to return
            
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of articles by URL
        """
        articles = {}
        
        # Get feeds from database
        feeds = self.db.list_feeds()
        if not feeds:
            logger.warning("No feeds found in database")
            return articles
            
        for feed in feeds:
            try:
                feed_url = feed['url']
                logger.info(f"Fetching RSS feed: {feed} (attempt 1/{self.max_retries})")
                
                # Fetch feed content
                feed_content = self._fetch_url(feed_url, is_feed=True)
                if not feed_content:
                    continue
                    
                # Parse feed
                feed = feedparser.parse(feed_content)
                if feed.bozo:  # Feed parsing error
                    logger.error(f"Error parsing feed {feed_url}: {feed.bozo_exception}")
                    continue
                    
                # Process entries
                entries = feed.entries[:self.max_entries]
                if limit:
                    entries = entries[:limit]
                    
                for entry in entries:
                    try:
                        url = entry.get('link')
                        if not url:
                            continue
                            
                        # Skip if already processed
                        if url in articles:
                            continue
                            
                        # Extract article content
                        content = self._extract_article_content(url)
                        if not content:
                            continue
                            
                        # Add to articles dictionary
                        articles[url] = content
                        
                    except Exception as e:
                        logger.error(f"Error processing entry from feed {feed_url}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing feed {feed_url}: {str(e)}")
                continue
                
        return articles
    
    def save_articles(self, articles: Dict[str, Dict[str, Any]]) -> None:
        """
        Save processed articles to the database.
        
        Args:
            articles (Dict[str, Dict[str, Any]]): Dictionary of articles to save
        """
        try:
            saved_count = 0
            for url, article in articles.items():
                if article.get('processed'):
                    if self.db.save_article(article):
                        saved_count += 1
                    
            logger.info(f"Saved {saved_count} processed articles to database")
            
        except Exception as e:
            logger.error(f"Error saving articles to database: {e}")
    
    def get_feed_articles(self, feed_id: int) -> List[Dict[str, Any]]:
        """
        Get all articles for a specific feed.
        
        Args:
            feed_id (int): The feed ID
            
        Returns:
            List[Dict[str, Any]]: List of articles for the feed
        """
        return self.db.get_feed_articles(feed_id)
    
    def remove_feed(self, feed_id: int) -> bool:
        """
        Remove a feed from the database.
        
        Args:
            feed_id (int): The feed ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db.remove_feed(feed_id) 