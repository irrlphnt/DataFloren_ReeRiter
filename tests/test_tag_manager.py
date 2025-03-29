import pytest
import os
from datetime import datetime
from tag_manager import TagManager
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
def test_tag_manager(test_db):
    """Create a test tag manager instance."""
    return TagManager(db=test_db)

def test_init_tag_manager(test_tag_manager):
    """Test tag manager initialization."""
    assert test_tag_manager.db is not None

def test_add_tag(test_tag_manager, test_db):
    """Test adding a tag."""
    tag_name = "test_tag"
    source = "manual"
    
    # Add tag
    tag_id = test_tag_manager.add_tag(tag_name, source)
    assert tag_id is not None
    
    # Verify tag was added
    conn = test_db._get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM tags WHERE name = ?', (tag_name,))
    tag = c.fetchone()
    conn.close()
    
    assert tag is not None
    assert tag[1] == tag_name  # name column
    assert tag[2] == source  # source column

def test_get_tag(test_tag_manager, test_db):
    """Test getting a tag."""
    # Add a test tag
    tag_name = "test_tag"
    source = "manual"
    tag_id = test_tag_manager.add_tag(tag_name, source)
    
    # Get tag
    tag = test_tag_manager.get_tag(tag_name)
    assert tag is not None
    assert tag['name'] == tag_name
    assert tag['source'] == source

def test_update_tag_usage(test_tag_manager, test_db):
    """Test updating tag usage."""
    # Add a test tag
    tag_name = "test_tag"
    source = "manual"
    tag_id = test_tag_manager.add_tag(tag_name, source)
    
    # Update usage
    success = test_tag_manager.update_tag_usage(tag_name)
    assert success is True
    
    # Verify usage was updated
    tag = test_tag_manager.get_tag(tag_name)
    assert tag['usage_count'] == 1
    assert tag['last_used'] is not None

def test_generate_tags(test_tag_manager):
    """Test generating tags for an article."""
    # Create test article
    article = {
        'title': 'Test Article Title',
        'content': 'This is a test article about technology and innovation. It discusses AI and machine learning.',
        'url': 'https://test.com/article1'
    }
    
    # Generate tags
    tags = test_tag_manager.generate_tags(article)
    assert len(tags) > 0
    
    # Verify tags are relevant
    assert any('technology' in tag.lower() for tag in tags)
    assert any('ai' in tag.lower() or 'machine learning' in tag.lower() for tag in tags)

def test_add_thematic_prompt(test_tag_manager):
    """Test adding a thematic prompt."""
    tag_name = "test_tag"
    prompt = "Test prompt for tag generation"
    
    # Add thematic prompt
    success = test_tag_manager.add_thematic_prompt(tag_name, prompt)
    assert success is True
    
    # Verify prompt was added
    prompts = test_tag_manager.get_thematic_prompts()
    assert any(p['tag_name'] == tag_name and p['prompt'] == prompt for p in prompts)

def test_get_thematic_prompts(test_tag_manager):
    """Test getting thematic prompts."""
    # Add some test prompts
    prompts = [
        ("tag1", "prompt1"),
        ("tag2", "prompt2"),
        ("tag3", "prompt3")
    ]
    
    for tag_name, prompt in prompts:
        test_tag_manager.add_thematic_prompt(tag_name, prompt)
    
    # Get all prompts
    all_prompts = test_tag_manager.get_thematic_prompts()
    assert len(all_prompts) == len(prompts)
    
    # Verify each prompt
    for tag_name, prompt in prompts:
        assert any(p['tag_name'] == tag_name and p['prompt'] == prompt for p in all_prompts)

def test_get_suggested_tags(test_tag_manager):
    """Test getting suggested tags."""
    # Add some test tags with usage counts
    tags = [
        ("tag1", 5),
        ("tag2", 3),
        ("tag3", 1),
        ("tag4", 0)
    ]
    
    for tag_name, usage_count in tags:
        tag_id = test_tag_manager.add_tag(tag_name, "manual")
        if usage_count > 0:
            for _ in range(usage_count):
                test_tag_manager.update_tag_usage(tag_name)
    
    # Get suggested tags
    suggested = test_tag_manager.get_suggested_tags(limit=2)
    assert len(suggested) == 2
    
    # Verify tags are ordered by usage count
    assert suggested[0]['name'] == "tag1"  # highest usage
    assert suggested[1]['name'] == "tag2"  # second highest usage

def test_cleanup_unused_tags(test_tag_manager):
    """Test cleaning up unused tags."""
    # Add some test tags
    tags = [
        ("tag1", 5),  # used
        ("tag2", 0),  # unused
        ("tag3", 1),  # used
        ("tag4", 0)   # unused
    ]
    
    for tag_name, usage_count in tags:
        tag_id = test_tag_manager.add_tag(tag_name, "manual")
        if usage_count > 0:
            for _ in range(usage_count):
                test_tag_manager.update_tag_usage(tag_name)
    
    # Cleanup unused tags
    success = test_tag_manager.cleanup_unused_tags()
    assert success is True
    
    # Verify unused tags were removed
    conn = test_tag_manager.db._get_connection()
    c = conn.cursor()
    c.execute('SELECT name FROM tags')
    remaining_tags = [row[0] for row in c.fetchall()]
    conn.close()
    
    assert "tag1" in remaining_tags
    assert "tag2" not in remaining_tags
    assert "tag3" in remaining_tags
    assert "tag4" not in remaining_tags 