from bs4 import BeautifulSoup  # Import BeautifulSoup for parsing HTML
from selenium import webdriver  # Import Selenium WebDriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin  # Import urljoin to handle relative URLs
from article_scraper import HeadlineGrabber, ArticleScraper  # Import from article_scraper.py
from article_rewriter import ArticleRewriter  # Import the ArticleRewriter class
from wordpress_poster import WordPressPoster  # Import the WordPressPoster class
from rss_monitor import RSSMonitor  # Import the RSSMonitor class
from webdriver_manager.chrome import ChromeDriverManager  # Import ChromeDriverManager
import logging
import time
import json
import os
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import traceback
from pathlib import Path
from database import Database
from lm_studio import LMStudio
from tag_manager import TagManager

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

# Config variables
CONFIG = load_config()

# Configure logging
log_level = getattr(logging, CONFIG["general"]["log_level"], logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("webscraper.log"),
        logging.StreamHandler()
    ]
)

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
        logging.error(f"Error loading state: {e}")
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
            logging.error(f"Failed to save error screenshot: {e}")
    
    logging.error(f"Error occurred during {state.current_stage}: {error}")
    logging.error(f"Traceback: {state.error_traceback}")

def recover_from_error(state: ProcessingState, driver: webdriver.Chrome) -> Dict[str, Any]:
    """Attempt to recover from a processing error."""
    logging.info(f"Attempting to recover from error in stage: {state.current_stage}")
    
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
            logging.error("No articles data found for recovery")
            return {}
    elif state.current_stage == 'posting':
        # Load rewritten articles and retry failed ones
        try:
            with open('rewritten_articles.json', 'r', encoding='utf-8') as f:
                articles = json.load(f)
            return articles
        except FileNotFoundError:
            logging.error("No rewritten articles found for recovery")
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
    logging.info(f"Monitoring website: {website_url}")
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
    
    logging.info(f"Found {len(filtered_links)} unique article links")
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
        logging.info(f"RSS Feed Statistics:")
        logging.info(f"- Total feeds: {stats['total_feeds']}")
        logging.info(f"- Active feeds: {stats['active_feeds']}")
        logging.info(f"- Total processed entries: {stats['total_entries']}")
        if stats['top_feeds']:
            logging.info("Top feeds by entry count:")
            for feed in stats['top_feeds']:
                logging.info(f"  - {feed['url']}: {feed['entry_count']} entries")
        
        # Get article links with detailed logging
        links = rss_monitor.get_article_links()
        logging.info(f"Found {len(links)} unique article links from RSS feeds")
        
        # Log feed health status
        active_feeds = rss_monitor.db.get_active_feeds()
        for feed in active_feeds:
            try:
                feed_data = rss_monitor._fetch_feed(feed['url'])
                if feed_data:
                    logging.info(f"Feed {feed['url']} is healthy with {len(feed_data.entries)} entries")
                else:
                    logging.warning(f"Feed {feed['url']} is not responding or has errors")
            except Exception as e:
                logging.error(f"Error checking feed health for {feed['url']}: {e}")
        
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
                logging.info(f"Processing RSS article: {link}")
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
                    logging.info(f"Successfully extracted article: {article_data['title']}")
                    logging.info(f"Found {len(article_data['paragraphs'])} paragraphs")
                else:
                    failed_count += 1
                    logging.warning(f"Failed to extract article data for link: {link}")
            else:
                # For website scraping, use the existing process
                driver.set_page_load_timeout(10)
                logging.info(f"Processing website link: {link}")
                driver.get(link)
                article_data = ArticleScraper(driver.page_source, link)
                articles_by_link[link] = article_data
                processed_count += 1
                logging.info(f"Successfully extracted article: {article_data['title']}")
                logging.info(f"Found {len(article_data['paragraphs'])} paragraphs")
        except Exception as e:
            failed_count += 1
            logging.error(f"Error processing link {link}: {e}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            articles_by_link[link] = None

    # Log processing summary
    logging.info(f"\nProcessing Summary:")
    logging.info(f"- Total links processed: {len(links)}")
    logging.info(f"- Successfully processed: {processed_count}")
    logging.info(f"- Failed to process: {failed_count}")
    logging.info(f"- Success rate: {(processed_count/len(links))*100:.1f}%")

    return articles_by_link

def add_feed(url: str, name: str = None) -> None:
    """Add a new RSS feed to the database."""
    if rss_monitor.add_feed(url, name):
        print(f"Successfully added feed: {name or url}")
    else:
        print(f"Failed to add feed: {url}")

def import_feeds_from_csv(csv_path: str) -> None:
    """Import feeds from a CSV file."""
    stats = rss_monitor.db.import_feeds_from_csv(csv_path)
    print(f"\nImport completed:")
    print(f"Total feeds processed: {stats['total']}")
    print(f"Successfully added: {stats['successful']}")
    print(f"Failed to add: {stats['failed']}")

def list_feeds(include_inactive: bool = False) -> None:
    """List all configured feeds."""
    feeds = rss_monitor.db.list_feeds(include_inactive)
    
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

def process_articles(monitor: RSSMonitor, tag_manager: TagManager, 
                    lm_studio: Optional[LMStudio] = None,
                    wordpress: Optional[WordPressPoster] = None,
                    limit: Optional[int] = None,
                    skip_rewrite: bool = False,
                    skip_wordpress: bool = False) -> Dict[str, Dict[str, Any]]:
    """Process articles from RSS feeds."""
    articles = {}
    
    # Get entries from RSS feeds
    entries = monitor.get_entries()
    if limit:
        entries = entries[:limit]
    
    total_entries = len(entries)
    processed = 0
    failed = 0
    
    for entry in entries:
        try:
            url = entry.get('link')
            if not url:
                continue
                
            logging.info(f"Processing article: {url}")
            
            # Extract content
            content = monitor._extract_article_content(url)
            if not content:
                failed += 1
                continue
            
            # Generate tags
            tags = tag_manager.generate_tags(
                content=content.get('content', ''),
                title=content.get('title', ''),
                existing_tags=entry.get('tags', [])
            )
            
            # Add tags to article data
            content['tags'] = tags
            
            # Add to articles dictionary
            articles[url] = content
            
            processed += 1
            logging.info(f"Successfully processed {processed}/{total_entries} articles")
            
        except Exception as e:
            logging.error(f"Error processing article {url}: {e}")
            failed += 1
            continue
    
    # Save articles to file
    save_articles(articles)
    
    # Print summary
    logging.info(f"""
Processing Summary:
------------------
Total entries: {total_entries}
Successfully processed: {processed}
Failed to process: {failed}
Success rate: {(processed/total_entries)*100:.1f}%
    """)
    
    return articles

def add_thematic_prompt(tag_manager: TagManager, tag_name: str, prompt: str) -> bool:
    """Add a thematic prompt for tag generation."""
    try:
        success = tag_manager.add_thematic_prompt(tag_name, prompt)
        if success:
            logging.info(f"Successfully added thematic prompt for tag: {tag_name}")
        else:
            logging.error(f"Failed to add thematic prompt for tag: {tag_name}")
        return success
    except Exception as e:
        logging.error(f"Error adding thematic prompt: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Article Monitor & Rewriter')
    parser.add_argument('--limit', type=int, help='Process only N articles')
    parser.add_argument('--skip-rewrite', action='store_true', help='Skip the article rewriting step')
    parser.add_argument('--skip-wordpress', action='store_true', help='Skip WordPress posting')
    parser.add_argument('--force-refresh', action='store_true', help='Force refresh of cached content')
    parser.add_argument('--add-feed', help='Add a new RSS feed URL')
    parser.add_argument('--feed-name', help='Name for the new feed')
    parser.add_argument('--import-csv', help='Import feeds from a CSV file')
    parser.add_argument('--list-feeds', action='store_true', help='List all configured feeds')
    parser.add_argument('--include-inactive', action='store_true', help='Include inactive feeds in listing')
    parser.add_argument('--remove-feed', type=int, help='Remove a feed by its ID')
    parser.add_argument('--toggle-feed', type=int, help='Enable/disable a feed')
    parser.add_argument('--show-stats', action='store_true', help='Display feed statistics')
    parser.add_argument('--add-thematic-prompt', nargs=2, metavar=('TAG', 'PROMPT'), 
                       help="Add a thematic prompt for tag generation")
    
    args = parser.parse_args()
    
    if args.add_feed:
        add_feed(args.add_feed, args.feed_name)
        return
    
    if args.import_csv:
        import_feeds_from_csv(args.import_csv)
        return
    
    if args.list_feeds:
        list_feeds(args.include_inactive)
        return
    
    if args.remove_feed:
        if rss_monitor.db.remove_feed(args.remove_feed):
            print(f"Successfully removed feed {args.remove_feed}")
        else:
            print(f"Failed to remove feed {args.remove_feed}")
        return
    
    if args.toggle_feed:
        if rss_monitor.db.toggle_feed(args.toggle_feed):
            print(f"Successfully toggled feed {args.toggle_feed}")
        else:
            print(f"Failed to toggle feed {args.toggle_feed}")
        return
    
    if args.show_stats:
        stats = rss_monitor.get_feed_stats()
        print("\nFeed Statistics:")
        print("-" * 80)
        print(f"Total feeds: {stats['total_feeds']}")
        print(f"Active feeds: {stats['active_feeds']}")
        print(f"Paywalled feeds: {stats['paywalled_feeds']}")
        print(f"Total paywall hits: {stats['total_paywall_hits']}")
        print(f"Total articles processed: {stats['total_articles']}")
        print("-" * 80)
        return
    
    if args.add_thematic_prompt:
        tag_name, prompt = args.add_thematic_prompt
        add_thematic_prompt(tag_manager, tag_name, prompt)
        return
    
    # Process articles
    process_articles(args.limit, args.skip_rewrite, args.skip_wordpress, args.force_refresh)

if __name__ == "__main__":
    main()