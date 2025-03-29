import pytest
import sqlite3
import os
from datetime import datetime
from database import Database

@pytest.fixture
def test_db():
    """Create a temporary test database."""
    db_path = "test_feeds.db"
    db = Database(db_path)
    yield db
    # Cleanup after tests
    try:
        # Close the database connection
        db.close()
        # Wait a bit to ensure all connections are closed
        import time
        time.sleep(0.1)
        # Remove the file
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception as e:
        print(f"Warning: Could not clean up test database: {e}")

def test_init_db(test_db):
    """Test database initialization."""
    # Check if tables were created
    conn = sqlite3.connect(test_db.db_path)
    c = conn.cursor()
    
    # Check feeds table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feeds'")
    assert c.fetchone() is not None
    
    # Check articles table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'")
    assert c.fetchone() is not None
    
    # Check processed_entries table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_entries'")
    assert c.fetchone() is not None
    
    # Check tags table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags'")
    assert c.fetchone() is not None
    
    # Check article_tags table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='article_tags'")
    assert c.fetchone() is not None
    
    # Check thematic_prompts table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='thematic_prompts'")
    assert c.fetchone() is not None
    
    conn.close()

def test_add_feed(test_db):
    """Test adding a feed."""
    # Clean up existing feeds
    conn = sqlite3.connect(test_db.db_path)
    c = conn.cursor()
    c.execute('DELETE FROM feeds')
    conn.commit()
    conn.close()
    
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    
    # Add feed
    feed_id = test_db.add_feed(feed_url, feed_name)
    assert feed_id is not None
    
    # Verify feed was added
    feed = test_db.get_feed(feed_id)
    assert feed is not None
    assert feed['url'] == feed_url
    assert feed['name'] == feed_name
    assert feed['is_active'] is True
    assert feed['is_paywalled'] is False

def test_remove_feed(test_db):
    """Test removing a feed."""
    # Add a feed first
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Remove the feed
    success = test_db.remove_feed(feed_id)
    assert success is True
    
    # Verify feed was removed
    feed = test_db.get_feed(feed_id)
    assert feed is None

def test_update_feed_status(test_db):
    """Test updating feed status."""
    # Add a feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Update status
    success = test_db.update_feed_status(feed_id, is_active=False)
    assert success is True
    
    # Verify status was updated
    feed = test_db.get_feed(feed_id)
    assert feed['is_active'] is False

def test_save_article(test_db):
    """Test saving an article."""
    # Add a feed first
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Create test article
    article_data = {
        'url': 'https://test.com/article1',
        'title': 'Test Article',
        'content': 'Test content',
        'author': 'Test Author',
        'published_date': datetime.now().isoformat(),
        'feed_id': feed_id
    }
    
    # Save article
    success = test_db.save_article(article_data)
    assert success is True
    
    # Verify article was saved
    conn = sqlite3.connect(test_db.db_path)
    c = conn.cursor()
    c.execute('SELECT * FROM articles WHERE url = ?', (article_data['url'],))
    article = c.fetchone()
    conn.close()
    
    assert article is not None
    assert article[2] == article_data['url']  # url column
    assert article[3] == article_data['title']  # title column
    assert article[4] == article_data['content']  # content column

def test_add_thematic_prompt(test_db):
    """Test adding a thematic prompt."""
    tag_name = "test_tag"
    prompt = "Test prompt"
    
    # Add thematic prompt
    success = test_db.add_thematic_prompt(tag_name, prompt)
    assert success is True
    
    # Verify prompt was added
    conn = sqlite3.connect(test_db.db_path)
    c = conn.cursor()
    c.execute('SELECT name, thematic_prompt FROM tags WHERE name = ?', (tag_name,))
    result = c.fetchone()
    conn.close()
    
    assert result is not None
    assert result[0] == tag_name  # name column
    assert result[1] == prompt  # thematic_prompt column

def test_get_thematic_prompts(test_db):
    """Test getting thematic prompts."""
    # Clean up existing prompts
    conn = sqlite3.connect(test_db.db_path)
    c = conn.cursor()
    c.execute('DELETE FROM thematic_prompts')
    c.execute('UPDATE tags SET thematic_prompt = NULL')
    conn.commit()
    conn.close()
    
    # Add some test prompts
    prompts = [
        ("tag1", "prompt1"),
        ("tag2", "prompt2"),
        ("tag3", "prompt3")
    ]
    
    for tag_name, prompt in prompts:
        test_db.add_thematic_prompt(tag_name, prompt)
    
    # Get all prompts
    all_prompts = test_db.get_thematic_prompts()
    assert len(all_prompts) == len(prompts)
    
    # Verify each prompt
    for tag_name, prompt in prompts:
        assert any(p['tag_name'] == tag_name and p['prompt'] == prompt for p in all_prompts)

def test_get_feed_articles(test_db):
    """Test getting articles for a feed."""
    # Add a feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Add some test articles
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
    
    for article in articles:
        test_db.save_article(article)
    
    # Get articles for the feed
    feed_articles = test_db.get_feed_articles(feed_id)
    assert len(feed_articles) == len(articles)
    
    # Verify each article
    for article in articles:
        assert any(a['url'] == article['url'] for a in feed_articles)

def test_get_unprocessed_articles(test_db):
    """Test getting unprocessed articles."""
    # Add a feed
    feed_url = "https://test.com/feed"
    feed_name = "Test Feed"
    feed_id = test_db.add_feed(feed_url, feed_name)
    
    # Add some test articles
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
    
    for article in articles:
        test_db.save_article(article)
    
    # Get unprocessed articles
    unprocessed = test_db.get_unprocessed_articles()
    assert len(unprocessed) == len(articles)
    
    # Mark one article as processed
    conn = sqlite3.connect(test_db.db_path)
    c = conn.cursor()
    c.execute('UPDATE articles SET processed = 1 WHERE url = ?', (articles[0]['url'],))
    conn.commit()
    conn.close()
    
    # Get unprocessed articles again
    unprocessed = test_db.get_unprocessed_articles()
    assert len(unprocessed) == len(articles) - 1 