import pytest
import os
import json
from datetime import datetime
from main import (
    load_config,
    parse_args,
    add_feed,
    remove_feed,
    list_feeds,
    add_thematic_prompt,
    save_articles,
    process_articles
)
from database import Database
from tag_manager import TagManager
from lm_studio import LMStudio
from wordpress_poster import WordPressPoster
from rss_monitor import RSSMonitor

@pytest.fixture
def test_db():
    """Create a temporary test database."""
    db_path = "test_feeds.db"
    db = Database(db_path)
    yield db
    # Cleanup after tests
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def test_config():
    """Create a test configuration."""
    return {
        "monitor": {
            "website_url": "https://test.com",
            "link_limit": 5,
            "use_rss": True,
            "rss_feeds": [],
            "rss_max_entries": 10
        },
        "openai": {},
        "wordpress": {
            "url": "https://test.com",
            "username": "test_user",
            "password": "test_pass"
        },
        "general": {
            "auto_rewrite": True,
            "auto_post": True,
            "log_level": "INFO"
        },
        "lm_studio": {
            "use_lm_studio": True,
            "url": "http://localhost:1234/v1",
            "model": "test-model"
        }
    }

@pytest.fixture
def test_tag_manager(test_db):
    """Create a test tag manager instance."""
    return TagManager(db=test_db)

@pytest.fixture
def test_lm_studio(test_config):
    """Create a test LMStudio instance."""
    return LMStudio(
        url=test_config["lm_studio"]["url"],
        model=test_config["lm_studio"]["model"]
    )

@pytest.fixture
def test_wordpress(test_config):
    """Create a test WordPress poster instance."""
    return WordPressPoster(
        wp_url=test_config["wordpress"]["url"],
        username=test_config["wordpress"]["username"],
        password=test_config["wordpress"]["password"]
    )

@pytest.fixture
def test_monitor(test_db, test_config):
    """Create a test RSS monitor instance."""
    return RSSMonitor(
        db=test_db,
        max_entries=test_config["monitor"]["rss_max_entries"],
        max_retries=3,
        retry_delay=1
    )

def test_load_config():
    """Test loading configuration."""
    config = load_config()
    assert isinstance(config, dict)
    assert "monitor" in config
    assert "wordpress" in config
    assert "general" in config
    assert "lm_studio" in config

def test_parse_args():
    """Test parsing command line arguments."""
    # Test add feed
    args = parse_args(['--add-feed', 'https://test.com/feed'])
    assert args.add_feed == 'https://test.com/feed'
    
    # Test remove feed
    args = parse_args(['--remove-feed', '1'])
    assert args.remove_feed == 1
    
    # Test list feeds
    args = parse_args(['--list-feeds'])
    assert args.list_feeds is True
    
    # Test add thematic prompt
    args = parse_args(['--add-thematic-prompt', '--tag-name', 'test', '--prompt', 'test prompt'])
    assert args.add_thematic_prompt is True
    assert args.tag_name == 'test'
    assert args.prompt == 'test prompt'

def test_add_feed(test_db):
    """Test adding a feed."""
    feed_url = "https://test.com/feed"
    success = add_feed(test_db, feed_url)
    assert success is True
    
    # Verify feed was added
    conn = test_db._get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM feeds WHERE url = ?', (feed_url,))
    feed = c.fetchone()
    conn.close()
    
    assert feed is not None
    assert feed[1] == feed_url  # url column

def test_remove_feed(test_db):
    """Test removing a feed."""
    # Add a feed first
    feed_url = "https://test.com/feed"
    feed_id = test_db.add_feed(feed_url, "Test Feed")
    
    # Remove the feed
    success = remove_feed(test_db, feed_id)
    assert success is True
    
    # Verify feed was removed
    feed = test_db.get_feed(feed_id)
    assert feed is None

def test_list_feeds(test_db):
    """Test listing feeds."""
    # Add some test feeds
    feeds = [
        ("https://test1.com/feed", "Test Feed 1"),
        ("https://test2.com/feed", "Test Feed 2")
    ]
    
    for url, name in feeds:
        test_db.add_feed(url, name)
    
    # List feeds
    list_feeds(test_db)  # This will print to stdout, but we can't easily test the output

def test_add_thematic_prompt(test_tag_manager):
    """Test adding a thematic prompt."""
    tag_name = "test_tag"
    prompt = "Test prompt for tag generation"
    
    success = add_thematic_prompt(test_tag_manager, tag_name, prompt)
    assert success is True
    
    # Verify prompt was added
    prompts = test_tag_manager.get_thematic_prompts()
    assert any(p['tag_name'] == tag_name and p['prompt'] == prompt for p in prompts)

def test_save_articles(test_db):
    """Test saving articles."""
    # Create test articles
    articles = {
        'https://test.com/article1': {
            'url': 'https://test.com/article1',
            'title': 'Test Article 1',
            'content': 'Test content 1',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'processed': True
        },
        'https://test.com/article2': {
            'url': 'https://test.com/article2',
            'title': 'Test Article 2',
            'content': 'Test content 2',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'processed': True
        }
    }
    
    # Save articles
    save_articles(articles)
    
    # Verify articles were saved
    conn = test_db._get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM articles')
    count = c.fetchone()[0]
    conn.close()
    
    assert count == len(articles)

def test_process_articles(test_db, test_tag_manager, test_lm_studio, test_wordpress, test_monitor, test_config):
    """Test processing articles."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_id = test_db.add_feed(feed_url, "Test Feed")
    
    # Create test articles
    articles = {
        'https://test.com/article1': {
            'url': 'https://test.com/article1',
            'title': 'Test Article 1',
            'content': 'Test content 1',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'feed_id': feed_id,
            'processed': False
        },
        'https://test.com/article2': {
            'url': 'https://test.com/article2',
            'title': 'Test Article 2',
            'content': 'Test content 2',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'feed_id': feed_id,
            'processed': False
        }
    }
    
    # Process articles
    process_articles(
        articles=articles,
        tag_manager=test_tag_manager,
        lm_studio=test_lm_studio,
        wordpress=test_wordpress,
        monitor=test_monitor,
        skip_rewrite=False,
        skip_wordpress=False
    )
    
    # Verify articles were processed
    conn = test_db._get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM articles WHERE processed = 1')
    count = c.fetchone()[0]
    conn.close()
    
    assert count == len(articles) 