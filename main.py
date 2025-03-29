from bs4 import BeautifulSoup  # Import BeautifulSoup for parsing HTML
from selenium import webdriver  # Import Selenium WebDriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin  # Import urljoin to handle relative URLs
from article_scraper import HeadlineGrabber, ArticleScraper  # Import from article_scraper.py
from wordpress_poster import WordPressPoster  # Import the WordPressPoster class
from rss_monitor import RSSMonitor  # Import the RSSMonitor class
from webdriver_manager.chrome import ChromeDriverManager  # Import ChromeDriverManager
from logger import main_logger as logger
import logging
import time
import json
import os
import argparse
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import traceback
from pathlib import Path
from database import Database
from lm_studio import LMStudio
from tag_manager import TagManager
import requests

# Load configuration from config.json
def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load config.json - {e}")
        return {
            "monitor": {
                "website_url": "https://datafloren.net",
                "link_limit": 5,
                "use_rss": False,
                "rss_feeds": [],
                "rss_max_entries": 10
            },
            "openai": {},
            "wordpress": {},
            "general": {"auto_rewrite": True, "auto_post": False, "log_level": "INFO"},
            "lm_studio": {}
        }

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Article Monitor & Rewriter')
    parser.add_argument('--limit', type=int, help='Process only N articles')
    parser.add_argument('--skip-rewrite', action='store_true', help='Skip article rewriting')
    parser.add_argument('--skip-wordpress', action='store_true', help='Skip WordPress posting')
    parser.add_argument('--add-feed', type=str, help='Add a new RSS feed')
    parser.add_argument('--remove-feed', type=int, help='Remove an RSS feed by its ID')
    parser.add_argument('--list-feeds', action='store_true', help='List all configured feeds')
    return parser.parse_args()

# Config variables
CONFIG = load_config()

# Configure logging level from config
log_level = CONFIG["general"].get("log_level", "INFO")
logger.setLevel(getattr(logging, log_level, logging.INFO))

# Define the website URL to monitor from config
website_url = CONFIG["monitor"]["website_url"]

@dataclass
class ProcessingState:
    """Tracks the state of article processing for recovery purposes."""
    start_time: str
    processed_links: list
    failed_links: list
    current_stage: str  # 'monitoring', 'scraping', 'rewriting', 'posting'
    last_successful_link: Optional[str] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    source_type: str = "website"  # 'website' or 'rss'

class ProcessingError(Exception):
    """Custom exception for processing errors with recovery information."""
    def __init__(self, message: str, state: ProcessingState):
        super().__init__(message)
        self.state = state

def save_state(state: ProcessingState, filename: str = 'processing_state.json'):
    """Save the current processing state to a file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(asdict(state), f, indent=4)

def load_state(filename: str = 'processing_state.json') -> Optional[ProcessingState]:
    """Load the processing state from a file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return ProcessingState(**data)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        return None

def handle_error(error: Exception, state: ProcessingState, driver: Optional[webdriver.Chrome] = None):
    """Handle errors during processing and attempt recovery."""
    state.error_message = str(error)
    state.error_traceback = traceback.format_exc()
    save_state(state)
    
    if driver:
        try:
            driver.save_screenshot(f"error_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        except Exception as e:
            logger.error(f"Failed to save error screenshot: {e}")
    
    logger.error(f"Error occurred during {state.current_stage}: {error}")
    logger.error(f"Traceback: {state.error_traceback}")

def recover_from_error(state: ProcessingState, driver: webdriver.Chrome) -> Dict[str, Any]:
    """Attempt to recover from a processing error."""
    logger.info(f"Attempting to recover from error in stage: {state.current_stage}")
    
    if state.current_stage == 'monitoring':
        # Retry monitoring from scratch
        return monitor_website(driver)
    elif state.current_stage == 'scraping':
        # Skip failed links and continue with remaining ones
        remaining_links = [link for link in state.processed_links if link not in state.failed_links]
        return process_links(driver, remaining_links)
    elif state.current_stage == 'rewriting':
        # Load existing articles and retry failed ones
        try:
            with open('articles_data.json', 'r', encoding='utf-8') as f:
                articles = json.load(f)
            return articles
        except FileNotFoundError:
            logger.error("No articles data found for recovery")
            return {}
    elif state.current_stage == 'posting':
        # Load rewritten articles and retry failed ones
        try:
            with open('rewritten_articles.json', 'r', encoding='utf-8') as f:
                articles = json.load(f)
            return articles
        except FileNotFoundError:
            logger.error("No rewritten articles found for recovery")
            return {}
    
    return {}

def add_ai_disclosure(article_data: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """Add AI generation disclosure to article data."""
    article_data['ai_metadata'] = {
        'generated_by': model_name,
        'generation_date': datetime.now().isoformat(),
        'is_ai_generated': True,
        'original_source': article_data.get('url', ''),
        'original_title': article_data.get('title', '')
    }
    return article_data

def setup_selenium():
    """
    Sets up the Selenium WebDriver with headless Chrome.

    Returns:
        WebDriver: A configured Selenium WebDriver instance.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Use ChromeDriverManager to automatically download and configure ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def monitor_website(driver):
    """
    Monitors the specified website and extracts all unique external links from the main posts loop,
    excluding tag cloud items and navigation links.

    Args:
        driver (WebDriver): The Selenium WebDriver instance.

    Returns:
        list: A list of unique external links found in the main posts loop.
    """
    logger.info(f"Monitoring website: {website_url}")
    driver.get(website_url)  # Open the website in the browser
    soup = BeautifulSoup(driver.page_source, 'html.parser')  # Parse the page source with BeautifulSoup
    links = set()  # Use a set to store unique links

    # Find the main content area (usually contains the posts loop)
    main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('div', class_='posts')
    
    if main_content:
        # Find all article links within the main content area
        for article in main_content.find_all(['article', 'div'], class_=['post', 'entry', 'article']):
            link = article.find('a', href=True)
            if link:
        # Convert relative URLs to absolute URLs
        absolute_url = urljoin(website_url, link['href'])
                # Only add external links that are not navigation or tag-related
                if (not absolute_url.startswith(website_url) or 
                    not any(tag in absolute_url.lower() for tag in ['/tag/', '/category/', '/author/', '#', 'page'])):
                    links.add(absolute_url)
    else:
        # Fallback: look for article links anywhere, but still exclude navigation and tag-related links
        for link in soup.find_all('a', href=True):
            absolute_url = urljoin(website_url, link['href'])
            if (not absolute_url.startswith(website_url) or 
                not any(tag in absolute_url.lower() for tag in ['/tag/', '/category/', '/author/', '#', 'page'])):
                links.add(absolute_url)

    # Filter out any remaining navigation or utility links
    filtered_links = {link for link in links if not any(x in link.lower() for x in ['#', 'page=', 'feed', '/wp-', '/tag/', '/category/', '/author/'])}
    
    logger.info(f"Found {len(filtered_links)} unique article links")
    return list(filtered_links)  # Convert the set back to a list and return it

def get_article_links() -> List[str]:
    """
    Get article links either from website scraping or RSS feeds based on configuration.
    
    Returns:
        List[str]: List of article URLs
    """
    if CONFIG["monitor"].get("use_rss", False):
        # Use RSS feeds
        rss_monitor = RSSMonitor(
            feed_urls=CONFIG["monitor"].get("rss_feeds", []),
            max_entries=CONFIG["monitor"].get("rss_max_entries", 10)
        )
        
        # Print feed statistics
        stats = rss_monitor.get_feed_stats()
        logger.info(f"RSS Feed Statistics:")
        logger.info(f"- Total feeds: {stats['total_feeds']}")
        logger.info(f"- Active feeds: {stats['active_feeds']}")
        logger.info(f"- Total processed entries: {stats['total_entries']}")
        if stats['top_feeds']:
            logger.info("Top feeds by entry count:")
            for feed in stats['top_feeds']:
                logger.info(f"  - {feed['url']}: {feed['entry_count']} entries")
        
        # Get article links with detailed logging
        links = rss_monitor.get_article_links()
        logger.info(f"Found {len(links)} unique article links from RSS feeds")
        
        # Log feed health status
        active_feeds = rss_monitor.db.get_active_feeds()
        for feed in active_feeds:
            try:
                feed_data = rss_monitor._fetch_feed(feed['url'])
                if feed_data:
                    logger.info(f"Feed {feed['url']} is healthy with {len(feed_data.entries)} entries")
                else:
                    logger.warning(f"Feed {feed['url']} is not responding or has errors")
            except Exception as e:
                logger.error(f"Error checking feed health for {feed['url']}: {e}")
        
        return links
    else:
        # Use website scraping
        driver = setup_selenium()
        try:
            return monitor_website(driver)
        finally:
            driver.quit()

def process_links(driver: Optional[webdriver.Chrome], links: List[str], rss_monitor: Optional[RSSMonitor] = None) -> Dict[str, Any]:
    """
    Processes a list of links by fetching and extracting article data from each link.
    If using RSS, the driver parameter will be None.

    Args:
        driver (Optional[WebDriver]): The Selenium WebDriver instance (None for RSS).
        links (list): A list of URLs to process.
        rss_monitor (Optional[RSSMonitor]): The RSSMonitor instance to use for RSS feeds.

    Returns:
        dict: A dictionary where keys are URLs and values are article data dictionaries.
    """
    articles_by_link = {}  # Initialize a dictionary to store article data by link
    processed_count = 0
    failed_count = 0

    for link in links:
        try:
            if CONFIG["monitor"].get("use_rss", False):
                # For RSS feeds, get the article data directly
                logger.info(f"Processing RSS article: {link}")
                article_data = rss_monitor.get_article_by_link(link) if rss_monitor else None
                if article_data:
                    articles_by_link[link] = {
                        'title': article_data['title'],
                        'paragraphs': article_data['paragraphs'],
                        'author': article_data['author'],
                        'date': article_data['published'],
                        'tags': article_data['tags'],
                        'source_feed': article_data['source_feed'],
                        'feed_title': article_data['feed_title']
                    }
                    processed_count += 1
                    logger.info(f"Successfully extracted article: {article_data['title']}")
                    logger.info(f"Found {len(article_data['paragraphs'])} paragraphs")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to extract article data for link: {link}")
            else:
                # For website scraping, use the existing process
                driver.set_page_load_timeout(10)
                logger.info(f"Processing website link: {link}")
            driver.get(link)
                article_data = ArticleScraper(driver.page_source, link)
                articles_by_link[link] = article_data
                processed_count += 1
                logger.info(f"Successfully extracted article: {article_data['title']}")
                logger.info(f"Found {len(article_data['paragraphs'])} paragraphs")
        except Exception as e:
            failed_count += 1
            logger.error(f"Error processing link {link}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            articles_by_link[link] = None

    # Log processing summary
    logger.info(f"\nProcessing Summary:")
    logger.info(f"- Total links processed: {len(links)}")
    logger.info(f"- Successfully processed: {processed_count}")
    logger.info(f"- Failed to process: {failed_count}")
    logger.info(f"- Success rate: {(processed_count/len(links))*100:.1f}%")

    return articles_by_link

def add_feed(db: Database, url: str) -> None:
    """Add a new RSS feed to the database."""
    if db.add_feed(url, url):
        print(f"Successfully added feed: {url}")
    else:
        print(f"Failed to add feed: {url}")

def import_feeds_from_csv(csv_path: str) -> None:
    """Import feeds from a CSV file."""
    stats = rss_monitor.db.import_feeds_from_csv(csv_path)
    print(f"\nImport completed:")
    print(f"Total feeds processed: {stats['total']}")
    print(f"Successfully added: {stats['successful']}")
    print(f"Failed to add: {stats['failed']}")

def list_feeds(db: Database, include_inactive: bool = False) -> None:
    """List all configured feeds."""
    feeds = db.list_feeds(include_inactive)
    
    if not feeds:
        print("No feeds configured.")
        return
    
    print("\nConfigured Feeds:")
    print("-" * 80)
    print(f"{'ID':<4} {'Name':<30} {'URL':<40} {'Status':<8} {'Paywall Hits':<12}")
    print("-" * 80)
    
    for feed in feeds:
        status = "Active" if feed['is_active'] else "Inactive"
        if feed['is_paywalled']:
            status = "Paywalled"
        
        print(f"{feed['id']:<4} {feed['name'][:30]:<30} {feed['url'][:40]:<40} {status:<8} {feed['paywall_hits']:<12}")
    
    print("-" * 80)

def process_articles(monitor: RSSMonitor, tag_manager: TagManager, lm_studio: LMStudio, wordpress: WordPressPoster, limit: int = None, skip_rewrite: bool = False, skip_wordpress: bool = False):
    """
    Process articles from RSS feeds and optionally post to WordPress.
    
    Args:
        monitor (RSSMonitor): RSS monitor instance
        tag_manager (TagManager): Tag manager instance
        lm_studio (LMStudio): LMStudio instance for rewriting
        wordpress (WordPressPoster): WordPress poster instance
        limit (int, optional): Maximum number of articles to process
        skip_rewrite (bool): Whether to skip rewriting
        skip_wordpress (bool): Whether to skip WordPress posting
    """
    try:
        # Get articles from RSS feeds
        articles = monitor.get_articles(limit=limit)
        if not articles:
            logger.info("No new articles found in RSS feeds")
            return

        logger.info(f"Processing {len(articles)} articles from RSS feeds")
        processed_count = 0
        success_count = 0
        skipped_count = 0

        for url, article in articles.items():
            try:
                processed_count += 1
                logger.info(f"Processing article {processed_count}/{len(articles)}: {url}")

                # Skip if already processed
                if article.get('processed'):
                    logger.info(f"Skipping already processed article: {url}")
                    continue

                # Ensure URL is set in article data
                article['url'] = url

                # Assess article relevance
                if not tag_manager.assess_article_relevance(article):
                    logger.info(f"Skipping irrelevant article: {url}")
                    skipped_count += 1
                    continue

                # Rewrite content if enabled
                if not skip_rewrite and CONFIG["general"]["auto_rewrite"]:
                    logger.info(f"Rewriting content for article: {url}")
                    rewritten_article = lm_studio.rewrite_article(article)
                    if rewritten_article:
                        # Update article with rewritten content
                        article.update({
                            'title': rewritten_article.get('title', article['title']),
                            'content': '\n\n'.join(rewritten_article.get('paragraphs', [])),
                            'ai_metadata': {
                                'generated_by': 'LMStudio',
                                'generation_date': datetime.now().isoformat(),
                                'original_source': url
                            }
                        })
                    else:
                        logger.error(f"Failed to rewrite content for article: {url}")
                        continue

                # Generate tags
                if not article.get('tags'):
                    logger.info(f"Generating tags for article: {url}")
                    article['tags'] = tag_manager.generate_tags(article)

                # Post to WordPress if enabled
                if not skip_wordpress and CONFIG["general"]["auto_post"]:
                    logger.info(f"Posting article to WordPress: {url}")
                    try:
                        post_result = wordpress.create_post(
                            article_data=article,
                            status=CONFIG["wordpress"]["default_status"]
                        )
                        if post_result:
                            logger.info(f"Successfully posted article to WordPress: {url}")
                            article['wordpress_post_id'] = post_result
                        else:
                            logger.error(f"Failed to post article to WordPress: {url}")
                    except Exception as e:
                        logger.error(f"Error posting to WordPress: {str(e)}")
                        continue

                # Mark as processed
                article['processed'] = True
                success_count += 1
                logger.info(f"Successfully processed article: {url}")

            except Exception as e:
                logger.error(f"Error processing article {url}: {str(e)}")
                continue

        # Save processed articles
        monitor.save_articles(articles)
        logger.info(f"Processed {processed_count} articles, {success_count} successful, {skipped_count} skipped")

    except Exception as e:
        logger.error(f"Error in process_articles: {str(e)}")
        raise

def remove_feed(db: Database, feed_id: int) -> bool:
    """
    Remove a feed from the database.
    
    Args:
        db (Database): Database instance
        feed_id (int): ID of the feed to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First check if the feed exists
        feed = db.get_feed(feed_id)
        if not feed:
            logger.error(f"Feed with ID {feed_id} not found")
            return False
            
        # Remove the feed
        success = db.remove_feed(feed_id)
        if success:
            logger.info(f"Successfully removed feed with ID {feed_id}")
        else:
            logger.error(f"Failed to remove feed with ID {feed_id}")
        return success
    except Exception as e:
        logger.error(f"Error removing feed: {e}")
        return False

def main():
    try:
        args = parse_args()
        
        # Initialize database
        db = Database()
        logger.info("Database initialized")
        
        # Initialize tag manager
        tag_manager = TagManager(db=db)
        logger.info("Tag manager initialized")
        
        # Initialize LMStudio if enabled
        lm_studio = None
        if CONFIG["lm_studio"].get("use_lm_studio", False):
            lm_studio = LMStudio(
                url=CONFIG["lm_studio"].get("url", "http://localhost:1234/v1"),
                model=CONFIG["lm_studio"].get("model", "mistral-7b-instruct-v0.3")
            )
            logger.info("LMStudio initialized")
        
        # Initialize WordPress if enabled
        wordpress = None
        if not args.skip_wordpress and CONFIG["wordpress"]:
            wordpress = WordPressPoster(
                wp_url=CONFIG["wordpress"]["url"],
                username=CONFIG["wordpress"]["username"],
                password=CONFIG["wordpress"]["password"]
            )
            logger.info("WordPress initialized")
        
        # Initialize monitor with database
        monitor = RSSMonitor(
            db=db,
            max_entries=CONFIG["monitor"].get("rss_max_entries", 10),
            max_retries=CONFIG["monitor"].get("rss_max_retries", 3),
            retry_delay=CONFIG["monitor"].get("rss_retry_delay", 5)
        )
        logger.info("RSS Monitor initialized")
        
        # Handle command line arguments
        if args.add_feed:
            add_feed(db, args.add_feed)
        elif args.remove_feed:
            remove_feed(db, args.remove_feed)
        elif args.list_feeds:
            list_feeds(db)
        else:
            # Get check interval from config (default to 1 hour)
            check_interval = CONFIG["monitor"].get("check_interval", 3600)
            logger.info(f"Starting RSS feed monitoring with {check_interval} second interval")
            
            try:
                while True:
                    try:
                        # Process articles
                        process_articles(
                            monitor=monitor,
                            tag_manager=tag_manager,
                            lm_studio=lm_studio,
                            wordpress=wordpress,
                            limit=args.limit,
                            skip_rewrite=args.skip_rewrite,
                            skip_wordpress=args.skip_wordpress
                        )
                        
                        # Log next check time
                        next_check = datetime.now() + timedelta(seconds=check_interval)
                        logger.info(f"Next feed check scheduled for: {next_check}")
                        
                        # Wait for next check interval
                        time.sleep(check_interval)
                        
                    except KeyboardInterrupt:
                        logger.info("Received shutdown signal. Stopping gracefully...")
                        break
                    except Exception as e:
                        logger.error(f"Error during feed check cycle: {str(e)}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        # Wait a bit before retrying on error
                        time.sleep(60)  # Wait 1 minute before retrying
                        continue
                        
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            except Exception as e:
                logger.error(f"Fatal error in main loop: {str(e)}")
                raise
    
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()