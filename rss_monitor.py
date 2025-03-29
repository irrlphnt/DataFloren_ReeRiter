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

class RSSMonitor:
    """
    A class to monitor RSS feeds and extract article information.
    """
    
    def __init__(self, feed_urls: List[str] = None, max_entries: int = 10, max_retries: int = 3, retry_delay: int = 5):
        """
        Initialize the RSS monitor.
        
        Args:
            feed_urls (List[str], optional): List of RSS feed URLs to monitor
            max_entries (int): Maximum number of entries to process per feed
            max_retries (int): Maximum number of retries for failed requests
            retry_delay (int): Delay between retries in seconds
        """
        self.max_entries = max_entries
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.db = Database()
        self._cached_entries = []  # Cache for entries
        
        # Load configuration
        with open('config.json', 'r') as f:
            config = json.load(f)
            self.config = config.get('monitor', {})
        
        # Add feeds to database if provided
        if feed_urls:
            for url in feed_urls:
                self.db.add_feed(url)
    
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
                    logging.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                
                logging.info(f"Fetching {'RSS feed' if is_feed else 'article'}: {url} (attempt {attempt + 1}/{self.max_retries})")
                response = requests.get(url, timeout=timeout, headers=headers)
                
                # Handle common status codes
                if response.status_code == 403:
                    logging.warning(f"Access forbidden to {url}. Site may have anti-scraping measures.")
                    # Try with a different user agent on next attempt
                    headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
                    continue
                elif response.status_code == 429:
                    logging.warning(f"Rate limited by {url}. Waiting longer before retry...")
                    time.sleep(self.retry_delay * 5)  # Wait 5 times longer
                    continue
                elif response.status_code == 404:
                    logging.error(f"Page not found: {url}")
                    return None
                
                response.raise_for_status()
                
                # Check if we got a valid response
                content_type = response.headers.get('content-type', '').lower()
                if not is_feed and 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
                    logging.warning(f"Unexpected content type from {url}: {content_type}")
                    if attempt < self.max_retries - 1:
                        continue
                    return None
                
                return response.content
                
            except RequestException as e:
                logging.error(f"Error fetching {'feed' if is_feed else 'article'} {url}: {e}")
                if attempt < self.max_retries - 1:
                    continue
                return None
            except Exception as e:
                logging.error(f"Unexpected error fetching {'feed' if is_feed else 'article'} {url}: {e}")
                if attempt < self.max_retries - 1:
                    continue
                return None
        
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
            logging.error(f"Error parsing feed {url}: {feed_data.bozo_exception}")
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
            List[str]: List of paragraphs
        """
        paragraphs = []
        min_length = self.config.get('rss_min_paragraph_length', 20)
        content_classes = self.config.get('rss_content_classes', ['entry-content', 'post-content', 'article-content'])
        
        # For article pages, try to find the main article container first
        if is_article_page:
            main_content = None
            for container in soup.find_all(['article', 'main', 'div'], class_=content_classes):
                if container.find_all(['p', 'div']):
                    main_content = container
                    break
            
            if main_content:
                soup = main_content
        
        # First try to find paragraphs in article content
        for p in soup.find_all(['p', 'div', 'article', 'span'], class_=content_classes):
            text = p.get_text().strip()
            if text and len(text) > min_length:  # Only include substantial paragraphs
                paragraphs.append(text)
        
        # If no paragraphs found, try all paragraphs
        if not paragraphs:
            for p in soup.find_all(['p', 'div', 'article', 'span']):
                text = p.get_text().strip()
                if text and len(text) > min_length:  # Only include substantial paragraphs
                    paragraphs.append(text)
        
        # If still no paragraphs, try to extract from raw text
        if not paragraphs:
            text = soup.get_text().strip()
            if text:
                # Split text into paragraphs by newlines and periods
                raw_paragraphs = []
                for p in text.split('\n'):
                    p = p.strip()
                    if p:
                        # Split by periods if the text is long
                        if len(p) > 150:
                            sentences = [s.strip() + '.' for s in p.split('.') if s.strip()]
                            raw_paragraphs.extend(sentences)
                        else:
                            raw_paragraphs.append(p)
                
                paragraphs = [p for p in raw_paragraphs if len(p) > min_length]
        
        # Clean up paragraphs
        cleaned_paragraphs = []
        for p in paragraphs:
            # Remove any remaining HTML tags
            p = BeautifulSoup(p, 'html.parser').get_text()
            # Remove any remaining quotes and special characters
            p = p.replace('"', '').replace('"', '').replace('"', '')
            p = p.replace('​', '')  # Remove zero-width space
            # Remove any text that looks like a footer
            if not any(x in p.lower() for x in ['first appeared on', 'the post']):
                p = p.strip()
                if p and len(p) > min_length:
                    cleaned_paragraphs.append(p)
        
        return cleaned_paragraphs
    
    def _detect_paywall(self, content: str, url: str) -> bool:
        """
        Detect if content is behind a paywall.
        
        Args:
            content (str): The HTML content to check
            url (str): The URL being checked
            
        Returns:
            bool: True if content appears to be paywalled
        """
        # Common paywall indicators
        paywall_indicators = [
            'subscribe now',
            'subscribe to read',
            'paywall',
            'premium content',
            'premium article',
            'premium subscriber',
            'subscriber exclusive',
            'subscriber only',
            'members only',
            'sign up to read',
            'sign up to continue',
            'continue reading',
            'read more',
            'unlimited access',
            'digital subscription',
            'subscribe for full access',
            'subscribe to continue',
            'subscribe to view',
            'subscribe to read more',
            'subscribe to access',
            'subscribe to unlock',
            'subscribe to get access',
            'subscribe to read the full article',
            'subscribe to read the full story',
            'subscribe to read the full text',
            'subscribe to read the full content',
            'subscribe to read the full version',
            'subscribe to read the full piece',
            'subscribe to read the full report',
            'subscribe to read the full analysis',
            'subscribe to read the full interview',
            'subscribe to read the full feature',
            'subscribe to read the full investigation',
            'subscribe to read the full coverage',
            'subscribe to read the full story',
            'subscribe to read the full article',
            'subscribe to read the full text',
            'subscribe to read the full content',
            'subscribe to read the full version',
            'subscribe to read the full piece',
            'subscribe to read the full report',
            'subscribe to read the full analysis',
            'subscribe to read the full interview',
            'subscribe to read the full feature',
            'subscribe to read the full investigation',
            'subscribe to read the full coverage'
        ]
        
        # Check for paywall indicators in the content
        content_lower = content.lower()
        for indicator in paywall_indicators:
            if indicator in content_lower:
                logging.info(f"Paywall detected in {url} using indicator: {indicator}")
                return True
        
        # Check for common paywall class names and IDs
        soup = BeautifulSoup(content, 'html.parser')
        paywall_classes = ['paywall', 'premium', 'subscriber', 'members-only', 'subscribe']
        paywall_ids = ['paywall', 'premium', 'subscriber', 'members-only', 'subscribe']
        
        for element in soup.find_all(class_=paywall_classes):
            if element.get_text().strip():
                logging.info(f"Paywall detected in {url} using class: {element.get('class')}")
                return True
        
        for element in soup.find_all(id=paywall_ids):
            if element.get_text().strip():
                logging.info(f"Paywall detected in {url} using ID: {element.get('id')}")
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
            logging.warning(f"Feed {feed_url} has hit paywall {recent_hits} times in the last week")
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
            
            # Extract paragraphs
            paragraphs = self._extract_paragraphs(soup, is_article_page=True)
            
            return {
                'title': title,
                'author': author,
                'paragraphs': paragraphs,
                'content': content.decode('utf-8') if isinstance(content, bytes) else content
            }
            
        except Exception as e:
            logging.error(f"Error extracting content from article {url}: {e}")
            return None
    
    def get_entries(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch and parse entries from all configured RSS feeds.
        
        Args:
            force_refresh (bool): Whether to force refresh the cache
        
        Returns:
            List[Dict[str, Any]]: List of article entries with their metadata
        """
        if self._cached_entries and not force_refresh:
            return self._cached_entries
            
        all_entries = []
        active_feeds = self.db.get_active_feeds()
        
        for feed in active_feeds:
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
                            'published': entry.get('published', ''),
                            'author': entry.get('author', ''),
                            'summary': entry.get('summary', ''),
                            'tags': [tag.get('term', '') for tag in entry.get('tags', [])],
                            'source_feed': feed['url'],
                            'feed_title': feed_data.feed.get('title', feed['title']),
                            'feed_link': feed_data.feed.get('link', ''),
                            'entry_id': entry.get('id', entry.get('link', '')),
                            'feed_id': feed['id']
                        }
                        
                        # Convert published date to ISO format if available
                        if article_data['published']:
                            try:
                                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                    parsed_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                                    article_data['published'] = parsed_date.isoformat()
                            except Exception as e:
                                logging.warning(f"Could not parse date '{article_data['published']}': {e}")
                        
                        # Extract content
                        content = None
                        if hasattr(entry, 'content'):
                            content = entry.content[0].value
                        elif hasattr(entry, 'description'):
                            content = entry.description
                        elif hasattr(entry, 'summary'):
                            content = entry.summary
                        
                        # Process content with BeautifulSoup
                        if content:
                            content = self._clean_content(content)
                            soup = BeautifulSoup(content, 'html.parser')
                            
                            # Extract paragraphs
                            article_data['paragraphs'] = self._extract_paragraphs(soup)
                            article_data['content'] = content
                            
                            # If no substantial paragraphs found, try fetching from the article URL
                            if not article_data['paragraphs'] and article_data['link']:
                                logging.info(f"No content found in feed, fetching from article URL: {article_data['link']}")
                                article_content = self._extract_article_content(article_data['link'], feed_id=feed['id'], feed_url=feed['url'])
                                if article_content:
                                    article_data['paragraphs'] = article_content['paragraphs']
                                    article_data['content'] = article_content['content']
                                    # Update title and author if not already present
                                    if not article_data['title'] and article_content['title']:
                                        article_data['title'] = article_content['title']
                                    if not article_data['author'] and article_content['author']:
                                        article_data['author'] = article_content['author']
                        else:
                            article_data['content'] = ''
                            article_data['paragraphs'] = []
                            # Try fetching from the article URL as a fallback
                            if article_data['link']:
                                logging.info(f"No content in feed, fetching from article URL: {article_data['link']}")
                                article_content = self._extract_article_content(article_data['link'], feed_id=feed['id'], feed_url=feed['url'])
                                if article_content:
                                    article_data['paragraphs'] = article_content['paragraphs']
                                    article_data['content'] = article_content['content']
                                    # Update title and author if not already present
                                    if not article_data['title'] and article_content['title']:
                                        article_data['title'] = article_content['title']
                                    if not article_data['author'] and article_content['author']:
                                        article_data['author'] = article_content['author']
                        
                        all_entries.append(article_data)
                        
                    except Exception as e:
                        logging.error(f"Error processing entry from feed {feed['url']}: {e}")
                        continue
                    
            except Exception as e:
                logging.error(f"Error processing feed {feed['url']}: {e}")
                continue
        
        self._cached_entries = all_entries
        return all_entries
    
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
                return {
                    'title': entry['title'],
                    'link': entry['link'],
                    'published': entry['published'],
                    'author': entry['author'],
                    'summary': entry['summary'],
                    'tags': entry['tags'],
                    'paragraphs': entry['paragraphs'],
                    'content': entry['content'],
                    'source_feed': entry['source_feed'],
                    'feed_title': entry['feed_title']
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