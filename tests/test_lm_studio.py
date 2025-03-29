import pytest
import os
import json
from datetime import datetime
from lm_studio import LMStudio
import requests_mock

@pytest.fixture
def test_lm_studio():
    """Create a test LMStudio instance."""
    lm_studio = LMStudio(
        url="http://localhost:1234/v1",
        model="test-model",
        test_connection=False
    )
    # Clear cache before each test
    lm_studio.cache = {}
    lm_studio._save_cache()
    return lm_studio

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

@pytest.fixture
def mock_api(requests_mock):
    """Mock LMStudio API responses."""
    # Mock models endpoint
    requests_mock.get(
        "http://localhost:1234/v1/models",
        json={"data": [{"id": "test-model"}]},
        status_code=200
    )
    
    # Mock chat completions endpoint
    requests_mock.post(
        "http://localhost:1234/v1/chat/completions",
        json={
            "choices": [{
                "message": {
                    "content": "TITLE: Rewritten Test Article\n\nThis is a rewritten test article about technology and innovation."
                }
            }]
        },
        status_code=200
    )
    
    return requests_mock

def test_init_lm_studio(test_lm_studio):
    """Test LMStudio initialization."""
    assert test_lm_studio.url == "http://localhost:1234/v1"
    assert test_lm_studio.model == "test-model"
    assert test_lm_studio.cache_dir == "cache"

def test_test_connection(test_lm_studio, mock_api):
    """Test connection to LMStudio API."""
    success = test_lm_studio.test_connection()
    assert success is True

def test_rewrite_article(test_lm_studio, test_cache_dir, mock_api):
    """Test article rewriting."""
    # Create test article
    article = {
        'title': 'Test Article',
        'content': 'This is a test article about technology and innovation.',
        'url': 'https://test.com/article1'
    }
    
    # Set cache directory for testing
    test_lm_studio.cache_dir = test_cache_dir
    
    # Rewrite article
    rewritten = test_lm_studio.rewrite_article(article)
    assert rewritten is not None
    assert 'title' in rewritten
    assert 'paragraphs' in rewritten
    assert len(rewritten['paragraphs']) > 0
    
    # Verify cache was created
    cache_file = os.path.join(test_cache_dir, "rewriter_cache.json")
    assert os.path.exists(cache_file)
    
    # Verify cache content
    with open(cache_file, 'r', encoding='utf-8') as f:
        cached_data = json.load(f)
        assert article['title'] in cached_data
        assert cached_data[article['title']]['title'] == rewritten['title']
        assert cached_data[article['title']]['paragraphs'] == rewritten['paragraphs']

def test_rewrite_article_with_cache(test_lm_studio, test_cache_dir, mock_api):
    """Test article rewriting with cache."""
    # Create test article
    article = {
        'title': 'Test Article',
        'content': 'This is a test article about technology and innovation.',
        'url': 'https://test.com/article1'
    }
    
    # Set cache directory for testing
    test_lm_studio.cache_dir = test_cache_dir
    
    # First rewrite (should create cache)
    rewritten1 = test_lm_studio.rewrite_article(article)
    assert rewritten1 is not None
    
    # Second rewrite (should use cache)
    rewritten2 = test_lm_studio.rewrite_article(article)
    assert rewritten2 is not None
    assert rewritten2 == rewritten1

def test_rewrite_article_with_error(test_lm_studio, mock_api):
    """Test article rewriting with invalid input."""
    # Test with missing required fields
    article = {
        'title': 'Test Article'
        # Missing content and url
    }
    
    rewritten = test_lm_studio.rewrite_article(article)
    assert rewritten is None

def test_rewrite_article_with_empty_content(test_lm_studio, mock_api):
    """Test article rewriting with empty content."""
    article = {
        'title': 'Test Article',
        'content': '',
        'url': 'https://test.com/article1'
    }
    
    rewritten = test_lm_studio.rewrite_article(article)
    assert rewritten is None

def test_rewrite_article_with_invalid_url(test_lm_studio, mock_api):
    """Test article rewriting with invalid URL."""
    article = {
        'title': 'Test Article',
        'content': 'Test content',
        'url': 'invalid-url'  # Invalid URL
    }
    
    rewritten = test_lm_studio.rewrite_article(article)
    assert rewritten is None

def test_rewrite_article_with_special_characters(test_lm_studio, test_cache_dir, mock_api):
    """Test article rewriting with special characters in content."""
    article = {
        'title': 'Test Article with Special Chars',
        'content': 'This is a test article with special characters: !@#$%^&*()',
        'url': 'https://test.com/article1'
    }
    
    # Set cache directory for testing
    test_lm_studio.cache_dir = test_cache_dir
    
    rewritten = test_lm_studio.rewrite_article(article)
    assert rewritten is not None
    assert 'title' in rewritten
    assert 'paragraphs' in rewritten
    assert len(rewritten['paragraphs']) > 0

def test_rewrite_article_with_long_content(test_lm_studio, test_cache_dir, mock_api):
    """Test article rewriting with long content."""
    # Create a long article
    long_content = "This is a test article. " * 100
    article = {
        'title': 'Test Article with Long Content',
        'content': long_content,
        'url': 'https://test.com/article1'
    }
    
    # Set cache directory for testing
    test_lm_studio.cache_dir = test_cache_dir
    
    rewritten = test_lm_studio.rewrite_article(article)
    assert rewritten is not None
    assert 'title' in rewritten
    assert 'paragraphs' in rewritten
    assert len(rewritten['paragraphs']) > 0 