import pytest
import os
from datetime import datetime
from rss_monitor import RSSMonitor
from database import Database

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
def test_monitor(test_db):
    """Create a test RSS monitor instance."""
    monitor = RSSMonitor(
        db=test_db,
        max_entries=5,
        max_retries=2,
        retry_delay=1
    )
    return monitor

def test_init_monitor(test_monitor):
    """Test RSS monitor initialization."""
    assert test_monitor.db is not None
    assert test_monitor.max_entries == 5
    assert test_monitor.max_retries == 2
    assert test_monitor.retry_delay == 1

def test_fetch_feed(test_monitor, test_db):
    """Test fetching a feed."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Fetch feed
    success = test_monitor.fetch_feed(feed_id)
    assert success is True
    
    # Verify feed was updated
    feed = test_db.get_feed(feed_id)
    assert feed['last_fetch'] is not None

def test_process_entries(test_monitor, test_db):
    """Test processing feed entries."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Create test entries
    entries = [
        {
            'url': f'https://test.com/article{i}',
            'title': f'Test Article {i}',
            'content': f'Test content {i}',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'feed_id': feed_id
        }
        for i in range(3)
    ]
    
    # Process entries
    processed = test_monitor.process_entries(feed_id, entries)
    assert len(processed) == len(entries)
    
    # Verify entries were saved
    articles = test_db.get_feed_articles(feed_id)
    assert len(articles) == len(entries)

def test_save_articles(test_monitor, test_db):
    """Test saving articles."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Create test articles
    articles = {
        f'https://test.com/article{i}': {
            'url': f'https://test.com/article{i}',
            'title': f'Test Article {i}',
            'content': f'Test content {i}',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'feed_id': feed_id,
            'processed': True
        }
        for i in range(3)
    }
    
    # Save articles
    test_monitor.save_articles(articles)
    
    # Verify articles were saved
    saved_articles = test_db.get_feed_articles(feed_id)
    assert len(saved_articles) == len(articles)

def test_update_feed_status(test_monitor, test_db):
    """Test updating feed status."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Update status
    success = test_monitor.update_feed_status(feed_id, is_active=False)
    assert success is True
    
    # Verify status was updated
    feed = test_db.get_feed(feed_id)
    assert feed['is_active'] is False

def test_remove_feed(test_monitor, test_db):
    """Test removing a feed."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Remove feed
    success = test_monitor.remove_feed(feed_id)
    assert success is True
    
    # Verify feed was removed
    feed = test_db.get_feed(feed_id)
    assert feed is None

def test_get_feed_articles(test_monitor, test_db):
    """Test getting articles for a feed."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Create test articles
    articles = [
        {
            'url': f'https://test.com/article{i}',
            'title': f'Test Article {i}',
            'content': f'Test content {i}',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'feed_id': feed_id
        }
        for i in range(3)
    ]
    
    # Save articles
    for article in articles:
        test_db.save_article(article)
    
    # Get articles
    feed_articles = test_monitor.get_feed_articles(feed_id)
    assert len(feed_articles) == len(articles)
    
    # Verify each article
    for article in articles:
        assert any(a['url'] == article['url'] for a in feed_articles)

def test_get_unprocessed_articles(test_monitor, test_db):
    """Test getting unprocessed articles."""
    # Add a test feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Create test articles
    articles = [
        {
            'url': f'https://test.com/article{i}',
            'title': f'Test Article {i}',
            'content': f'Test content {i}',
            'author': 'Test Author',
            'published_date': datetime.now().isoformat(),
            'feed_id': feed_id,
            'processed': 0  # Unprocessed
        }
        for i in range(3)
    ]
    
    # Save articles
    for article in articles:
        test_db.save_article(article)
    
    # Get unprocessed articles
    unprocessed = test_monitor.get_unprocessed_articles()
    assert len(unprocessed) == len(articles)
    
    # Mark one article as processed
    test_db.update_article_status(articles[0]['url'], processed=True)
    
    # Get unprocessed articles again
    unprocessed = test_monitor.get_unprocessed_articles()
    assert len(unprocessed) == len(articles) - 1 