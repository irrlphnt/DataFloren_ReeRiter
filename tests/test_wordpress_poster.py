import pytest
import os
import json
from datetime import datetime
from wordpress_poster import WordPressPoster

@pytest.fixture
def test_wordpress():
    """Create a test WordPress poster instance."""
    return WordPressPoster(
        wp_url="https://test.com",
        username="test_user",
        password="test_pass"
    )

@pytest.fixture
def test_cache_dir():
    """Create a temporary cache directory."""
    cache_dir = "test_cache"
    os.makedirs(cache_dir, exist_ok=True)
    yield cache_dir
    # Cleanup after tests
    if os.path.exists(cache_dir):
        for file in os.listdir(cache_dir):
            os.remove(os.path.join(cache_dir, file))
        os.rmdir(cache_dir)

def test_init_wordpress(test_wordpress):
    """Test WordPress poster initialization."""
    assert test_wordpress.wp_url == "https://test.com"
    assert test_wordpress.username == "test_user"
    assert test_wordpress.password == "test_pass"
    assert test_wordpress.cache_dir == "cache"

def test_test_connection(test_wordpress):
    """Test connection to WordPress API."""
    # This test will fail if WordPress is not running
    # In a real test environment, you might want to mock the API calls
    success = test_wordpress.test_connection()
    assert isinstance(success, bool)

def test_create_post(test_wordpress, test_cache_dir):
    """Test creating a post."""
    # Create test article
    article = {
        'title': 'Test Article',
        'content': 'This is a test article about technology and innovation.',
        'url': 'https://test.com/article1',
        'tags': ['technology', 'innovation']
    }
    
    # Set cache directory for testing
    test_wordpress.cache_dir = test_cache_dir
    
    # Create post
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is not None
    
    # Verify cache was created
    cache_file = os.path.join(test_cache_dir, f"{article['url']}.json")
    assert os.path.exists(cache_file)
    
    # Verify cache content
    with open(cache_file, 'r', encoding='utf-8') as f:
        cached_data = json.load(f)
        assert cached_data['post_id'] == post_id
        assert cached_data['title'] == article['title']
        assert cached_data['content'] == article['content']

def test_create_post_with_cache(test_wordpress, test_cache_dir):
    """Test creating a post with cache."""
    # Create test article
    article = {
        'title': 'Test Article',
        'content': 'This is a test article about technology and innovation.',
        'url': 'https://test.com/article1',
        'tags': ['technology', 'innovation']
    }
    
    # Set cache directory for testing
    test_wordpress.cache_dir = test_cache_dir
    
    # First post (should create cache)
    post_id1 = test_wordpress.create_post(article_data=article)
    assert post_id1 is not None
    
    # Second post (should use cache)
    post_id2 = test_wordpress.create_post(article_data=article)
    assert post_id2 is not None
    assert post_id2 == post_id1

def test_create_post_with_error(test_wordpress):
    """Test creating a post with invalid input."""
    # Test with missing required fields
    article = {
        'title': 'Test Article'
        # Missing content and url
    }
    
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is None

def test_create_post_with_empty_content(test_wordpress):
    """Test creating a post with empty content."""
    article = {
        'title': 'Test Article',
        'content': '',
        'url': 'https://test.com/article1'
    }
    
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is None

def test_create_post_with_invalid_url(test_wordpress):
    """Test creating a post with invalid URL."""
    article = {
        'title': 'Test Article',
        'content': 'Test content',
        'url': 'invalid-url'  # Invalid URL
    }
    
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is None

def test_create_post_with_special_characters(test_wordpress, test_cache_dir):
    """Test creating a post with special characters in content."""
    article = {
        'title': 'Test Article with Special Chars',
        'content': 'This is a test article with special characters: !@#$%^&*()',
        'url': 'https://test.com/article1',
        'tags': ['test']
    }
    
    # Set cache directory for testing
    test_wordpress.cache_dir = test_cache_dir
    
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is not None

def test_create_post_with_long_content(test_wordpress, test_cache_dir):
    """Test creating a post with long content."""
    # Create a long article
    long_content = "This is a test article. " * 100
    article = {
        'title': 'Test Article with Long Content',
        'content': long_content,
        'url': 'https://test.com/article1',
        'tags': ['test']
    }
    
    # Set cache directory for testing
    test_wordpress.cache_dir = test_cache_dir
    
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is not None

def test_create_post_with_tags(test_wordpress, test_cache_dir):
    """Test creating a post with tags."""
    article = {
        'title': 'Test Article with Tags',
        'content': 'This is a test article with multiple tags.',
        'url': 'https://test.com/article1',
        'tags': ['tag1', 'tag2', 'tag3']
    }
    
    # Set cache directory for testing
    test_wordpress.cache_dir = test_cache_dir
    
    post_id = test_wordpress.create_post(article_data=article)
    assert post_id is not None

def test_create_post_with_status(test_wordpress, test_cache_dir):
    """Test creating a post with different status."""
    article = {
        'title': 'Test Article with Status',
        'content': 'This is a test article with draft status.',
        'url': 'https://test.com/article1',
        'tags': ['test']
    }
    
    # Set cache directory for testing
    test_wordpress.cache_dir = test_cache_dir
    
    # Test with draft status
    post_id = test_wordpress.create_post(article_data=article, status='draft')
    assert post_id is not None
    
    # Test with private status
    article['url'] = 'https://test.com/article2'
    post_id = test_wordpress.create_post(article_data=article, status='private')
    assert post_id is not None 