import requests
import logging
import os
import json
import time
from urllib.parse import urljoin
from datetime import datetime
import base64
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wordpress.log"),
        logging.StreamHandler()
    ]
)

class WordPressPoster:
    """
    A class for posting articles to WordPress using the WordPress REST API.
    """
    
    def __init__(self, wp_url, username, password, api_version="wp/v2"):
        """
        Initialize the WordPressPoster with WordPress credentials.
        
        Args:
            wp_url (str): The base URL of the WordPress site (e.g., https://example.com).
            username (str): WordPress username.
            password (str): WordPress password or application password.
            api_version (str): The WordPress REST API version to use.
        """
        self.wp_url = wp_url.rstrip('/')
        self.api_base = f"{self.wp_url}/wp-json/{api_version}"
        self.username = username
        self.password = password
        self.auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            'Authorization': f'Basic {self.auth}',
            'Content-Type': 'application/json'
        }
        
        # Cache to avoid reposting the same articles
        self.cache_file = "wordpress_cache.json"
        self.cache = self._load_cache()
        
    def _load_cache(self):
        """Load the cache from file if it exists."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Error loading cache: {e}")
            return {}
            
    def _save_cache(self):
        """Save the cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Error saving cache: {e}")
    
    def test_connection(self):
        """
        Test the connection to the WordPress API.
        
        Returns:
            bool: True if the connection is successful, False otherwise.
        """
        try:
            response = requests.get(f"{self.api_base}/posts", headers=self.headers)
            if response.status_code == 200:
                logging.info("Successfully connected to WordPress API")
                return True
            else:
                logging.error(f"Failed to connect to WordPress API: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logging.error(f"Error testing connection to WordPress API: {e}")
            return False
    
    def upload_media(self, image_url):
        """
        Upload an image to the WordPress media library.
        
        Args:
            image_url (str): The URL of the image to upload.
            
        Returns:
            int: The media ID if successful, None otherwise.
        """
        try:
            # Download the image
            response = requests.get(image_url, stream=True)
            if response.status_code != 200:
                logging.error(f"Failed to download image from {image_url}: {response.status_code}")
                return None
                
            # Determine the filename from the URL
            filename = os.path.basename(image_url.split('?')[0])
            if not filename:
                filename = f"image_{int(time.time())}.jpg"
                
            # Upload the image to WordPress
            headers = self.headers.copy()
            headers.pop('Content-Type', None)  # Remove Content-Type for file upload
            
            files = {
                'file': (filename, response.content)
            }
            
            upload_response = requests.post(
                f"{self.api_base}/media",
                headers={
                    'Authorization': f'Basic {self.auth}'
                },
                files=files
            )
            
            if upload_response.status_code in (201, 200):
                media_data = upload_response.json()
                logging.info(f"Successfully uploaded image: {filename}")
                return media_data.get('id')
            else:
                logging.error(f"Failed to upload image: {upload_response.status_code} - {upload_response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error uploading media {image_url}: {e}")
            return None
    
    def create_post_content(self, article_data: Dict[str, Any]) -> str:
        """Create WordPress post content with AI disclosure."""
        content = []
        
        # Add AI disclosure at the top
        if 'ai_metadata' in article_data:
            ai_meta = article_data['ai_metadata']
            disclosure = (
                f"<div class='ai-disclosure'>\n"
                f"<p><strong>AI-Generated Content Disclosure:</strong></p>\n"
                f"<p>This article was generated using artificial intelligence ({ai_meta['generated_by']}) "
                f"on {ai_meta['generation_date']}. The original article can be found at "
                f"<a href='{ai_meta['original_source']}'>{ai_meta['original_source']}</a>.</p>\n"
                f"</div>\n\n"
            )
            content.append(disclosure)
        
        # Add the main content
        content.append(article_data['content'])
        
        # Add attribution if available
        if article_data.get('author'):
            content.append(f"\n<p><em>Original author: {article_data['author']}</em></p>")
        
        return "\n".join(content)
    
    def create_post(self, article_data, status="draft", featured_media_id=None, categories=None, tags=None):
        """
        Create a new WordPress post from the article data.
        
        Args:
            article_data (dict): The article data including title, content, etc.
            status (str): The post status ('draft', 'publish', 'pending', etc.).
            featured_media_id (int): The ID of the featured image.
            categories (list): List of category IDs to assign to the post.
            tags (list): List of tag IDs to assign to the post.
            
        Returns:
            dict: The created post data if successful, None otherwise.
        """
        # Skip if article title or paragraphs are missing
        if not article_data or not article_data.get('title') or not article_data.get('paragraphs'):
            logging.warning("Cannot create post: Missing title or content")
            return None
            
        # Check if this article is already in the cache
        cache_key = article_data.get('title', '')
        if cache_key in self.cache:
            logging.info(f"Article already posted: {cache_key}")
            return self.cache[cache_key]
            
        # Prepare post content
        content = self.create_post_content(article_data)
        
        # Prepare post data
        post_data = {
            'title': article_data.get('title', ''),
            'content': content,
            'status': status,
            'date': datetime.now().isoformat(),
        }
        
        # Add featured media if provided
        if featured_media_id:
            post_data['featured_media'] = featured_media_id
            
        # Add categories if provided
        if categories:
            post_data['categories'] = categories
            
        # Add tags if provided
        if tags:
            post_data['tags'] = tags
            
        try:
            # Create the post
            response = requests.post(
                f"{self.api_base}/posts",
                headers=self.headers,
                json=post_data
            )
            
            if response.status_code in (201, 200):
                post_data = response.json()
                logging.info(f"Successfully created post: {post_data.get('id')} - {article_data.get('title')}")
                
                # Save to cache
                self.cache[cache_key] = post_data
                self._save_cache()
                
                return post_data
            else:
                logging.error(f"Failed to create post: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error creating post {article_data.get('title')}: {e}")
            return None
    
    def post_article(self, article_data, status="draft", upload_images=True, categories=None, tags=None):
        """
        Post an article to WordPress, including uploading any images.
        
        Args:
            article_data (dict): The article data including title, content, images, etc.
            status (str): The post status ('draft', 'publish', 'pending', etc.).
            upload_images (bool): Whether to upload and include images in the post.
            categories (list): List of category IDs to assign to the post.
            tags (list): List of tag IDs to assign to the post.
            
        Returns:
            dict: The created post data if successful, None otherwise.
        """
        logging.info(f"Posting article: {article_data.get('title', 'Untitled')}")
        
        featured_media_id = None
        
        # Upload images if enabled and available
        if upload_images and article_data.get('images'):
            try:
                # Upload the first image as featured image
                first_image = article_data['images'][0]
                featured_media_id = self.upload_media(first_image)
                
                if featured_media_id:
                    logging.info(f"Set featured image with ID: {featured_media_id}")
                else:
                    logging.warning("Failed to set featured image")
                    
            except Exception as e:
                logging.error(f"Error handling images: {e}")
        
        # Create the post
        return self.create_post(
            article_data,
            status=status,
            featured_media_id=featured_media_id,
            categories=categories,
            tags=tags
        )
    
    def get_or_create_tag(self, tag_name: str) -> Optional[int]:
        """
        Get an existing tag ID or create a new tag if it doesn't exist.
        
        Args:
            tag_name (str): The name of the tag to get or create.
            
        Returns:
            Optional[int]: The tag ID if successful, None otherwise.
        """
        try:
            # First, try to find the existing tag
            response = requests.get(
                f"{self.api_base}/tags",
                headers=self.headers,
                params={'search': tag_name}
            )
            
            if response.status_code == 200:
                tags = response.json()
                for tag in tags:
                    if tag['name'].lower() == tag_name.lower():
                        return tag['id']
            
            # If tag not found, create it
            tag_data = {
                'name': tag_name,
                'slug': tag_name.lower().replace(' ', '-')
            }
            
            response = requests.post(
                f"{self.api_base}/tags",
                headers=self.headers,
                json=tag_data
            )
            
            if response.status_code in (201, 200):
                return response.json()['id']
            else:
                logging.error(f"Failed to create tag '{tag_name}': {response.text}")
                return None
            
        except Exception as e:
            logging.error(f"Error handling tag '{tag_name}': {e}")
            return None

    def post_batch(self, articles: Dict[str, Dict[str, Any]], status: str = "draft", 
                   upload_images: bool = True, default_category: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
        """Post multiple articles to WordPress with AI disclosure and tags."""
        posted_articles = {}
        
        for url, article_data in articles.items():
            try:
                # Create post content with AI disclosure
                content = self.create_post_content(article_data)
                
                # Prepare post data
                post_data = {
                    'title': article_data['title'],
                    'content': content,
                    'status': status,
                    'categories': [default_category] if default_category else []
                }
                
                # Add featured image if available
                if upload_images and article_data.get('featured_image'):
                    image_id = self.upload_media(article_data['featured_image'])
                    if image_id:
                        post_data['featured_media'] = image_id
                
                # Handle tags
                tag_ids = []
                if article_data.get('tags'):
                    for tag_name in article_data['tags']:
                        tag_id = self.get_or_create_tag(tag_name)
                        if tag_id:
                            tag_ids.append(tag_id)
                
                if tag_ids:
                    post_data['tags'] = tag_ids
                
                # Create the post
                response = requests.post(
                    f"{self.api_base}/posts",
                    headers=self.headers,
                    json=post_data
                )
                
                if response.status_code == 201:
                    post_data = response.json()
                    posted_articles[url] = {
                        'id': post_data['id'],
                        'link': post_data['link'],
                        'status': post_data['status'],
                        'ai_metadata': article_data.get('ai_metadata', {}),
                        'tags': article_data.get('tags', [])
                    }
                    logging.info(f"Successfully posted article from {url}")
                else:
                    logging.error(f"Failed to post article from {url}: {response.text}")
                    
            except Exception as e:
                logging.error(f"Error posting article from {url}: {e}")
                continue
        
        return posted_articles

# Example usage
if __name__ == "__main__":
    # Example article data for testing
    example_article = {
        "title": "Sample WordPress Post",
        "paragraphs": [
            "This is the first paragraph of the sample article being posted to WordPress.",
            "The second paragraph provides more details and demonstrates the WordPress posting functionality.",
            "In conclusion, this final paragraph wraps up the example post."
        ],
        "author": "John Doe",
        "date": "2025-03-28",
        "images": [],  # Add image URLs here to test image uploading
        "original_url": "https://example.com/sample-article"
    }
    
    try:
        # These would typically come from environment variables or a config file
        wp_url = os.environ.get("WP_URL", "https://your-wordpress-site.com")
        wp_username = os.environ.get("WP_USERNAME", "your_username")
        wp_password = os.environ.get("WP_PASSWORD", "your_password")
        
        # Initialize the WordPress poster
        poster = WordPressPoster(wp_url, wp_username, wp_password)
        
        # Test the connection
        if poster.test_connection():
            # Post the example article
            post_data = poster.post_article(example_article, status="draft")
            
            if post_data:
                print(f"\nSuccessfully posted article!")
                print(f"Post ID: {post_data.get('id')}")
                print(f"Post URL: {post_data.get('link')}")
            else:
                print("Failed to post article.")
        else:
            print("Failed to connect to WordPress API. Check your credentials and WordPress URL.")
    except Exception as e:
        print(f"Error: {e}") 