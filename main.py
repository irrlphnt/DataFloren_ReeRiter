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
from selenium.webdriver.common.by import By

# Load configuration from config.json
def load_config():
    """Load configuration from config.json."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Article Monitor & Rewriter')
    parser.add_argument('--limit', type=int, help='Process only N articles')
    parser.add_argument('--skip-rewrite', action='store_true', help='Skip article rewriting')
    parser.add_argument('--skip-wordpress', action='store_true', help='Skip WordPress posting')
    parser.add_argument('--add-feed', type=str, help='Add a new RSS feed')
    parser.add_argument('--remove-feed', type=int, help='Remove an RSS feed by its ID')
    parser.add_argument('--list-feeds', action='store_true', help='List all configured feeds')
    parser.add_argument('--import-feeds', type=str, help='Import feeds from a CSV file')
    parser.add_argument('--export-feeds', type=str, help='Export feeds to a CSV file')
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
        for link in main_content.find_all('a', href=True):
            # Get the absolute URL
            absolute_url = urljoin(website_url, link['href'])
            
            # Skip if it's not an external link
            if not absolute_url.startswith(website_url):
                continue
                
            # Skip if it's a tag cloud item or navigation link
            if any(x in link.get('class', []) for x in ['tag-cloud-link', 'nav-link']):
                continue
                
            # Add to set of unique links
            links.add(absolute_url)
    
    # Convert set to list and return
    return list(links)

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

def process_links(driver, links, rss_monitor=None):
    """
    Process a list of links, fetching and extracting article data from each link.

    Args:
        driver: Selenium WebDriver instance
        links: List of URLs to process
        rss_monitor: Optional RSSMonitor instance for feed processing

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary of processed article data
    """
    article_data = {}
    total_links = len(links)
    processed = 0
    failed = 0

    for link in links:
        try:
            processed += 1
            logger.info(f"Processing link {processed}/{total_links}: {link}")
            
            # Try RSS feed first if monitor is provided
            if rss_monitor:
                try:
                    entries = rss_monitor.get_entries(link)
                    if entries:
                        for entry in entries:
                            url = entry.get('link')
                            if url and url not in article_data:
                                article_data[url] = {
                                    'url': url,
                                    'title': entry.get('title', ''),
                                    'content': entry.get('summary', ''),
                                    'author': entry.get('author', ''),
                                    'published': entry.get('published_date', ''),
                                    'tags': entry.get('tags', []),
                                    'processed': False,
                                    'source_feed': link
                                }
                        continue
                except Exception as e:
                    logger.warning(f"Error processing RSS feed {link}: {e}")
            
            # If not an RSS feed or RSS processing failed, try website scraping
            driver.get(link)
            time.sleep(2)  # Wait for page to load
            
            # Get all links on the page
            page_links = driver.find_elements(By.TAG_NAME, 'a')
            for page_link in page_links:
                try:
                    href = page_link.get_attribute('href')
                    if not href or href in article_data:
                        continue
                        
                    # Check if it's an article link
                    if is_article_link(href):
                        article_data[href] = {
                            'url': href,
                            'title': page_link.text.strip(),
                            'content': '',
                            'author': '',
                            'published': '',
                            'tags': [],
                            'processed': False
                        }
                except Exception as e:
                    logger.warning(f"Error processing link {href}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error processing {link}: {e}")
            failed += 1
            continue
    
    success_rate = ((processed - failed) / total_links * 100) if total_links > 0 else 0
    logger.info(f"Link processing summary:")
    logger.info(f"Total links: {total_links}")
    logger.info(f"Successfully processed: {processed - failed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success rate: {success_rate:.1f}%")
    
    return article_data

def add_feed(db: Database, url: str) -> None:
    """Add a new RSS feed to the database."""
    if db.add_feed(url, url):
        print(f"Successfully added feed: {url}")
    else:
        print(f"Failed to add feed: {url}")

def remove_feed(db: Database, feed_id: int) -> None:
    """Remove a feed from the database."""
    if db.remove_feed(feed_id):
        print(f"Successfully removed feed with ID: {feed_id}")
    else:
        print(f"Failed to remove feed with ID: {feed_id}")

def list_feeds(db: Database) -> None:
    """List all configured feeds."""
    feeds = db.list_feeds()
    if not feeds:
        print("No feeds configured.")
        return
    
    print("\nConfigured Feeds:")
    print("-" * 80)
    print(f"{'ID':<4} {'Name':<30} {'URL':<40} {'Status':<8}")
    print("-" * 80)
    
    for feed in feeds:
        status = "Active" if feed['is_active'] else "Inactive"
        if feed['is_paywalled']:
            status = "Paywalled"
        print(f"{feed['id']:<4} {feed['name'][:30]:<30} {feed['url'][:40]:<40} {status:<8}")
    
    print("-" * 80)

def import_feeds_from_csv(csv_path: str) -> None:
    """Import feeds from a CSV file."""
    try:
        # Initialize database
        db = Database()
        logger.info("Database initialized for feed import")
        
        # Import feeds
        stats = db.import_feeds_from_csv(csv_path)
        
        if stats:
            print(f"\nFeed Import Statistics:")
            print(f"Total feeds processed: {stats['total']}")
            print(f"Successfully added: {stats['added']}")
            print(f"Already existed: {stats['duplicates']}")
            print(f"Failed to add: {stats['failed']}")
            
            if stats['errors']:
                print("\nErrors encountered:")
                for error in stats['errors']:
                    print(f"- {error}")
        else:
            print("Failed to import feeds. Check the logs for details.")
            
    except Exception as e:
        logger.error(f"Error importing feeds from CSV: {str(e)}")
        print(f"Error importing feeds: {str(e)}")

def export_feeds(db: Database, csv_path: str) -> None:
    """Export feeds to a CSV file."""
    if db.export_feeds_to_csv(csv_path):
        print(f"Successfully exported feeds to: {csv_path}")
    else:
        print(f"Failed to export feeds to: {csv_path}")

def process_article(entry: Dict[str, Any], lm_studio: Optional[LMStudio] = None) -> Dict[str, Any]:
    """Process an article entry."""
    try:
        # Create article data dictionary
        article_data = {
            'title': entry.get('title', ''),
            'content': entry.get('content', ''),
            'author': entry.get('author', ''),
            'link': entry.get('link', ''),  # Store as 'link' to match entry format
            'published_date': entry.get('published', '')
        }
        
        # Log available fields
        logger.info(f"Article fields: {', '.join(f'{k}: {bool(v)}' for k, v in article_data.items())}")
        
        # Try to rewrite with LMStudio if available
        if lm_studio and lm_studio.is_available():
            logger.info(f"Rewriting article: {article_data['title']}")
            try:
                # Create data for LMStudio with correct field names
                lm_data = {
                    'title': article_data['title'],
                    'content': article_data['content'],
                    'url': article_data['link']  # Pass as 'url' to LMStudio
                }
                
                # Log LMStudio data
                logger.info(f"LMStudio data fields: {', '.join(f'{k}: {bool(v)}' for k, v in lm_data.items())}")
                
                # Only proceed if we have the required fields
                if lm_data['title'] and lm_data['content'] and lm_data['url']:
                    rewritten = lm_studio.rewrite_article(
                        article_data=lm_data,
                        style="informative",
                        tone="neutral",
                        max_tokens=1500
                    )
                    if rewritten:
                        # Update article data with rewritten content
                        article_data['rewritten_content'] = '\n\n'.join(rewritten.get('paragraphs', []))
                        article_data['title'] = rewritten.get('title', article_data['title'])
                        logger.info(f"Successfully rewritten article: {article_data['title']}")
                    else:
                        logger.warning(f"Failed to rewrite article: {article_data['title']}")
                else:
                    logger.warning("Missing required fields for rewriting")
            except Exception as e:
                logger.error(f"Error rewriting article: {e}")
                logger.warning("Using original content due to rewriting error")
        else:
            logger.warning("LMStudio not available, using original content")
        
        return article_data
        
    except Exception as e:
        logger.error(f"Error processing article: {e}")
        return article_data

def main():
    try:
        # Load configuration
        CONFIG = load_config()
        
        # Initialize components
        db = Database()
        wordpress = WordPressPoster(
            wp_url=CONFIG["wordpress"]["url"],
            username=CONFIG["wordpress"]["username"],
            password=CONFIG["wordpress"]["password"]
        )
        
        lm_studio = None
        if CONFIG["lm_studio"].get("use_lm_studio", False):
            lm_studio = LMStudio(
                url=CONFIG["lm_studio"].get("url", "http://localhost:1234/v1"),
                model=CONFIG["lm_studio"].get("model", "mistral-7b-instruct-v0.3")
            )
        
        # Get active feeds
        feeds = db.get_active_feeds()
        if not feeds:
            logger.warning("No active feeds found")
            return
        
        # Process each feed
        for feed in feeds:
            try:
                logger.info(f"Processing feed: {feed['name']}")
                
                # Get entries from feed
                entries = db.get_unprocessed_entries(feed['id'])
                if not entries:
                    continue
                
                # Process each entry
                for entry in entries:
                    try:
                        # Check if already published
                        post_id = db.get_wordpress_post_id(entry.get('link', ''))
                        if post_id and wordpress.verify_post_exists(post_id):
                            logger.info(f"Article already published: {entry.get('title', '')}")
                            continue
                        
                        # Process article
                        article_data = process_article(entry, lm_studio)
                        
                        # Create WordPress post data
                        wp_data = {
                            'title': article_data.get('title', ''),
                            'content': article_data.get('rewritten_content', article_data.get('content', '')),
                            'author': article_data.get('author', ''),
                            'url': article_data.get('link', ''),
                            'ai_metadata': {
                                'generated_by': f"LMStudio ({CONFIG['lm_studio'].get('model', '')})",
                                'generation_date': datetime.now().isoformat(),
                                'original_source': article_data.get('link', ''),
                                'original_title': article_data.get('title', '')
                            }
                        }
                        
                        # Post to WordPress
                        post_id = wordpress.create_post(
                            article_data=wp_data,
                            status=CONFIG["wordpress"].get("default_status", "draft")
                        )
                        
                        if post_id:
                            # Update database
                            db.update_wordpress_post_id(article_data.get('link', ''), str(post_id))
                            logger.info(f"Posted to WordPress: {article_data.get('title', '')}")
                        
                        # Mark as processed
                        db.mark_entry_processed(
                            feed_id=feed['id'],
                            entry_id=entry.get('id', '')
                        )
                        
                    except Exception as e:
                        logger.error(f"Error processing entry: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error processing feed {feed['name']}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()