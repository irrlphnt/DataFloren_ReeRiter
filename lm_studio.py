import logging
import requests
import json
import os
from typing import Optional, Dict, Any, List
from logger import lm_studio_logger as logger
from datetime import datetime

class LMStudio:
    """Handles interactions with a local LM Studio server."""
    
    def __init__(self, url: str = "http://localhost:1234/v1", model: str = "mistral-7b-instruct-v0.3", test_connection: bool = True):
        """
        Initialize the LM Studio client.
        
        Args:
            url (str): The URL of the LM Studio server
            model (str): The model to use
            test_connection (bool): Whether to test the connection on initialization
        """
        self.url = url.rstrip('/')
        self.model = model
        self.headers = {
            "Content-Type": "application/json"
        }
        
        # Initialize cache
        self.cache_dir = "cache"
        self.cache_file = os.path.join(self.cache_dir, "rewriter_cache.json")
        self.cache = self._load_cache()
        
        # Test connection if requested
        if test_connection:
            self.test_connection()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load the cache from file if it exists."""
        try:
            # Ensure cache directory exists
            os.makedirs(self.cache_dir, exist_ok=True)
            
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return {}
    
    def _save_cache(self) -> None:
        """Save the cache to file."""
        try:
            # Ensure cache directory exists
            os.makedirs(self.cache_dir, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def test_connection(self) -> bool:
        """Test connection to LMStudio API."""
        try:
            response = requests.get(f"{self.url}/models")
            if response.status_code == 200:
                logger.info("Successfully connected to LMStudio API")
                return True
            else:
                logger.error(f"Failed to connect to LMStudio API: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to LMStudio API: {str(e)}")
            return False
    
    def generate(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.7) -> Optional[str]:
        """
        Generate text using the LM Studio server.
        
        Args:
            prompt (str): The input prompt
            max_tokens (int): Maximum number of tokens to generate
            temperature (float): Sampling temperature
            
        Returns:
            Optional[str]: Generated text or None if failed
        """
        try:
            # Split prompt into chunks if it's too long
            chunks = self._split_prompt(prompt)
            if not chunks:
                return None
            
            # Process each chunk and combine results
            results = []
            for chunk in chunks:
                data = {
                    "messages": [
                        {"role": "user", "content": chunk}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False
                }
                
                if self.model:
                    data["model"] = self.model
                
                response = requests.post(
                    f"{self.url}/chat/completions",
                    headers=self.headers,
                    json=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("choices") and result["choices"][0].get("message"):
                        results.append(result["choices"][0]["message"]["content"])
                    else:
                        logger.error("Invalid response format from LMStudio API")
                        return None
                else:
                    logger.error(f"Error from LMStudio API: {response.status_code}")
                    return None
            
            return "\n".join(results) if results else None
            
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            return None
    
    def rewrite_article(self, article_data: Dict[str, Any], style: str = "informative", 
                       tone: str = "neutral", max_tokens: int = 4000) -> Optional[Dict[str, Any]]:
        """
        Rewrite an article using LM Studio.
        
        Args:
            article_data (dict): Dictionary containing the article data
            style (str): The writing style to use (informative, persuasive, casual, etc.)
            tone (str): The tone of the rewritten article (neutral, positive, critical, etc.)
            max_tokens (int): Maximum number of tokens for the rewritten content
            
        Returns:
            Optional[Dict[str, Any]]: Rewritten article data or None if failed
        """
        # Skip if article data is missing or invalid
        if not article_data:
            logger.warning("Cannot rewrite article: Missing article data")
            return None
            
        # Check required fields
        if not article_data.get('title'):
            logger.warning("Cannot rewrite article: Missing title")
            return None
            
        if not article_data.get('content'):
            logger.warning("Cannot rewrite article: Missing content")
            return None
            
        if not article_data.get('url'):
            logger.warning("Cannot rewrite article: Missing URL")
            return None
        
        # Check if this article is already in the cache
        cache_key = article_data.get('title', '')
        if cache_key in self.cache:
            logger.info(f"Using cached rewrite for: {cache_key}")
            return self.cache[cache_key]
        
        logger.info(f"Rewriting article: {article_data['title']}")
        
        # Construct the prompt for article rewriting
        prompt = self._construct_rewrite_prompt(article_data, style, tone)
        if not prompt:
            logger.warning("Cannot rewrite article: Failed to construct prompt")
            return None
        
        try:
            # Generate rewritten content
            rewritten_content = self.generate(prompt, max_tokens=max_tokens)
            if not rewritten_content:
                return None
            
            # Parse the rewritten content
            rewritten_article = self._parse_rewritten_content(rewritten_content, article_data)
            if not rewritten_article:
                logger.warning("Cannot rewrite article: Failed to parse rewritten content")
                return None
            
            # Add AI metadata with model name
            rewritten_article['ai_metadata'] = {
                'generated_by': f"LMStudio ({self.model})",
                'generation_date': datetime.now().isoformat(),
                'original_source': article_data.get('url', ''),
                'original_title': article_data.get('title', '')
            }
            
            # Save to cache
            self.cache[cache_key] = rewritten_article
            self._save_cache()
            
            return rewritten_article
            
        except Exception as e:
            logger.error(f"Error rewriting article {article_data.get('title')}: {e}")
            return None
    
    def _construct_rewrite_prompt(self, article_data: Dict[str, Any], style: str, tone: str) -> str:
        """
        Construct the prompt for article rewriting.
        
        Args:
            article_data (dict): The article data
            style (str): The writing style
            tone (str): The tone of the rewritten article
            
        Returns:
            str: The prompt for the LM Studio API
        """
        # Gather the original content
        title = article_data.get('title', '')
        content = article_data.get('content', '')
        
        # If content is empty, return None
        if not content:
            return None
        
        # Construct the prompt
        prompt = f"""
You are a professional article rewriter. Rewrite the following article in a {style} style with a {tone} tone.
Maintain the key information and meaning, but use different wording and structure.
Format the response with a clear title and paragraphs.

Title: {title}

Content:
{content}

Please provide the rewritten article in the following format:
TITLE: [Your rewritten title]

[Your rewritten paragraphs, each separated by a blank line]
"""
        return prompt
    
    def _parse_rewritten_content(self, content: str, original_article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the rewritten content into a structured article format.
        
        Args:
            content (str): The raw rewritten content
            original_article (dict): The original article data
            
        Returns:
            Dict[str, Any]: The parsed article data
        """
        try:
            # Split content into lines
            lines = content.strip().split('\n')
            
            # Extract title (should start with "TITLE:")
            title = None
            paragraphs = []
            
            for line in lines:
                if line.startswith('TITLE:'):
                    title = line[6:].strip()
                elif line.strip():
                    paragraphs.append(line.strip())
            
            # If no title was found, use the original title
            if not title:
                title = original_article.get('title', '')
            
            # Create the rewritten article
            rewritten_article = {
                'title': title,
                'paragraphs': paragraphs,
                'url': original_article.get('url', ''),
                'ai_metadata': {
                    'generated_by': 'lm_studio',
                    'generation_date': datetime.now().isoformat(),
                    'original_source': original_article.get('url', '')
                }
            }
            
            return rewritten_article
            
        except Exception as e:
            logger.error(f"Error parsing rewritten content: {e}")
            return None
    
    def _split_prompt(self, prompt: str, max_chunk_size: int = 4000) -> List[str]:
        """
        Split a long prompt into smaller chunks.
        
        Args:
            prompt (str): The prompt to split
            max_chunk_size (int): Maximum size of each chunk
            
        Returns:
            List[str]: List of prompt chunks
        """
        # Simple splitting by paragraphs
        paragraphs = prompt.split('\n\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for paragraph in paragraphs:
            paragraph_size = len(paragraph)
            
            if current_size + paragraph_size > max_chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(paragraph)
            current_size += paragraph_size
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def is_available(self) -> bool:
        """
        Check if the LM Studio server is available.
        
        Returns:
            bool: True if server is available, False otherwise
        """
        try:
            response = requests.get(f"{self.url}/models", timeout=5)
            return response.status_code == 200
        except:
            return False 