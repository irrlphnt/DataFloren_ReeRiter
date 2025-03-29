import logging
import requests
import json
import os
from typing import Optional, Dict, Any, List
from logger import lm_studio_logger as logger

class LMStudio:
    """Handles interactions with a local LM Studio server."""
    
    def __init__(self, url: str = "http://localhost:1234/v1", model: str = "mistral-7b-instruct-v0.3"):
        """
        Initialize the LM Studio client.
        
        Args:
            url (str): The URL of the LM Studio server
            model (str): The model to use
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
        
        # Test connection
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
        # Skip if article title is missing
        if not article_data or not article_data.get('title'):
            logger.warning("Cannot rewrite article: Missing title or article data")
            return None
        
        # Check if this article is already in the cache
        cache_key = article_data.get('title', '')
        if cache_key in self.cache:
            logger.info(f"Using cached rewrite for: {cache_key}")
            return self.cache[cache_key]
        
        logger.info(f"Rewriting article: {article_data['title']}")
        
        # Construct the prompt for article rewriting
        prompt = self._construct_rewrite_prompt(article_data, style, tone)
        
        try:
            # Generate rewritten content
            rewritten_content = self.generate(prompt, max_tokens=max_tokens)
            if not rewritten_content:
                return None
            
            # Parse the rewritten content
            rewritten_article = self._parse_rewritten_content(rewritten_content, article_data)
            
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
        paragraphs = article_data.get('paragraphs', [])
        content = "\n\n".join(paragraphs)
        
        # Construct the prompt
        prompt = f"""
You are a professional article rewriter. Rewrite the following article in a {style} style with a {tone} tone.
Maintain the key information and meaning, but use different wording and structure.
Format the response with a clear title and paragraphs.

Original Title: {title}

Original Content:
{content}

Please format your response as follows:
TITLE: [Rewritten Title]

[Rewritten content organized in paragraphs]
        """
        
        return prompt
    
    def _parse_rewritten_content(self, rewritten_content: str, original_article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the rewritten content from the LM Studio API response.
        
        Args:
            rewritten_content (str): The rewritten content from the API
            original_article (dict): The original article data
            
        Returns:
            Dict[str, Any]: A dictionary containing the rewritten article data
        """
        # Initialize with structure similar to original article
        rewritten_article = {
            'title': original_article.get('title', ''),  # Default to original
            'paragraphs': [],
            'author': original_article.get('author', ''),
            'date': original_article.get('date', ''),
            'images': original_article.get('images', []),  # Preserve original images
            'original_url': original_article.get('original_url', '')
        }
        
        # Extract title and content from the rewritten text
        lines = rewritten_content.split('\n')
        content_started = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Extract title
            if line.startswith('TITLE:'):
                rewritten_article['title'] = line.replace('TITLE:', '').strip()
            elif 'TITLE:' in line:  # Handle case where format might be different
                parts = line.split('TITLE:')
                if len(parts) > 1:
                    rewritten_article['title'] = parts[1].strip()
            # For paragraphs, we skip any non-content lines at the beginning
            elif not content_started:
                # If we've processed the title and encountered a substantial text that's not an instruction
                if (rewritten_article['title'] and 
                    len(line) > 30 and 
                    not line.startswith('#') and 
                    not line.startswith('TITLE:')):
                    content_started = True
                    rewritten_article['paragraphs'].append(line)
            else:
                # Add to paragraphs if it's not a short line
                if len(line) > 10:
                    rewritten_article['paragraphs'].append(line)
        
        # If no title was extracted, use the original
        if not rewritten_article['title'] or rewritten_article['title'] == 'Rewritten Title':
            rewritten_article['title'] = original_article.get('title', '')
        
        return rewritten_article
    
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