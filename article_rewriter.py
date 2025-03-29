import openai
import logging
import os
import json
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rewriter.log"),
        logging.StreamHandler()
    ]
)

class ArticleRewriter:
    """
    A class for rewriting articles using either OpenAI's API or a local LM Studio server.
    """
    
    def __init__(self, api_key=None, use_lm_studio=False, lm_studio_url="http://localhost:1234/v1", lm_studio_model=None):
        """
        Initialize the ArticleRewriter.
        
        Args:
            api_key (str, optional): OpenAI API key. If not provided, it will try to get it from environment variable.
            use_lm_studio (bool): Whether to use LM Studio instead of OpenAI.
            lm_studio_url (str): The URL of the LM Studio API server.
            lm_studio_model (str): The model name to use in LM Studio.
        """
        self.use_lm_studio = use_lm_studio
        
        # Set up the client
        if self.use_lm_studio:
            if not lm_studio_model:
                logging.warning("No LM Studio model specified. Will attempt to use a default model but this may fail.")
                
            logging.info(f"Using LM Studio server at {lm_studio_url}")
            self.client = openai.OpenAI(
                base_url=lm_studio_url,
                api_key="lm-studio"  # LM Studio doesn't require a real API key
            )
            self.model = lm_studio_model or "local-model"  # Default model name for LM Studio
            
            # Try to verify available models
            try:
                self._check_lm_studio_models()
            except Exception as e:
                logging.warning(f"Failed to check available LM Studio models: {e}")
        else:
            # Get API key from environment variable if not provided
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key is required when not using LM Studio. Provide it as a parameter or set the OPENAI_API_KEY environment variable.")
            
            # Initialize the OpenAI client
            self.client = openai.OpenAI(api_key=self.api_key)
            self.model = "gpt-3.5-turbo-16k"  # Default model for OpenAI
        
        # Cache to avoid reprocessing the same articles
        self.cache_file = "rewriter_cache.json"
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
    
    def _check_lm_studio_models(self):
        """Check available models in LM Studio and log them."""
        try:
            models_response = self.client.models.list()
            available_models = [model.id for model in models_response.data]
            
            logging.info(f"Available LM Studio models: {available_models}")
            
            if self.model not in available_models:
                logging.warning(f"Selected model '{self.model}' is not in the list of available models. "
                               f"Please choose one of: {', '.join(available_models)}")
        except Exception as e:
            logging.error(f"Error checking LM Studio models: {e}")
            
    def rewrite_article(self, article_data, style="informative", tone="neutral", max_tokens=4000):
        """
        Rewrite an article using OpenAI's API or LM Studio.
        
        Args:
            article_data (dict): Dictionary containing the article data from ArticleScraper.
            style (str): The writing style to use (informative, persuasive, casual, etc.).
            tone (str): The tone of the rewritten article (neutral, positive, critical, etc.).
            max_tokens (int): Maximum number of tokens for the rewritten content.
            
        Returns:
            dict: A dictionary containing the rewritten article data.
        """
        # Skip if article title is missing
        if not article_data or not article_data.get('title'):
            logging.warning("Cannot rewrite article: Missing title or article data")
            return None
            
        # Check if this article is already in the cache
        cache_key = article_data.get('title', '')
        if cache_key in self.cache:
            logging.info(f"Using cached rewrite for: {cache_key}")
            return self.cache[cache_key]
            
        logging.info(f"Rewriting article: {article_data['title']}")
        
        # Construct the prompt for article rewriting
        prompt = self._construct_rewrite_prompt(article_data, style, tone)
        
        try:
            # Prepare messages based on whether we're using LM Studio or OpenAI
            system_content = "You are a professional article rewriter. Rewrite the given article in a way that preserves the meaning but uses different wording and structure. Include all the key information from the original."
            
            if self.use_lm_studio:
                # LM Studio only supports 'user' and 'assistant' roles
                # Combine system and user messages
                combined_prompt = f"{system_content}\n\n{prompt}"
                messages = [
                    {"role": "user", "content": combined_prompt}
                ]
                logging.info("Using LM Studio compatible message format (user role only)")
            else:
                # OpenAI supports system, user, and assistant roles
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ]
            
            # Call the API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,  # Balancing creativity and coherence
            )
            
            # Extract the rewritten content
            rewritten_content = response.choices[0].message.content.strip()
            
            # Parse the rewritten content
            rewritten_article = self._parse_rewritten_content(rewritten_content, article_data)
            
            # Save to cache
            self.cache[cache_key] = rewritten_article
            self._save_cache()
            
            return rewritten_article
            
        except Exception as e:
            error_message = str(e)
            if self.use_lm_studio and "model_not_found" in error_message:
                # Extract available models from error message if possible
                available_models = []
                if "Your models:" in error_message:
                    models_text = error_message.split("Your models:")[1].strip()
                    available_models = [line.strip() for line in models_text.split("\n") if line.strip()]
                
                if available_models:
                    logging.error(f"Model '{self.model}' not found in LM Studio. Available models: {', '.join(available_models)}")
                    logging.error(f"Please specify one of the available models using the --lm-studio-model parameter or in config.json")
                else:
                    logging.error(f"Model '{self.model}' not found in LM Studio. Please check your LM Studio server and select an available model.")
            elif self.use_lm_studio and "Only user and assistant roles are supported" in error_message:
                logging.error("LM Studio error: Only 'user' and 'assistant' roles are supported. This should be handled automatically, but there might be an issue with the API implementation.")
            else:
                logging.error(f"Error rewriting article {article_data.get('title')}: {e}")
            return None
            
    def _construct_rewrite_prompt(self, article_data, style, tone):
        """
        Construct the prompt for the OpenAI API.
        
        Args:
            article_data (dict): The article data.
            style (str): The writing style.
            tone (str): The tone of the rewritten article.
            
        Returns:
            str: The prompt for the OpenAI API.
        """
        # Gather the original content
        title = article_data.get('title', '')
        paragraphs = article_data.get('paragraphs', [])
        content = "\n\n".join(paragraphs)
        
        # Construct the prompt
        prompt = f"""
Rewrite the following article in a {style} style with a {tone} tone. 
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
        
    def _parse_rewritten_content(self, rewritten_content, original_article):
        """
        Parse the rewritten content from the OpenAI API response.
        
        Args:
            rewritten_content (str): The rewritten content from the API.
            original_article (dict): The original article data.
            
        Returns:
            dict: A dictionary containing the rewritten article data.
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
    
    def rewrite_batch(self, articles_data):
        """
        Rewrite a batch of articles.
        
        Args:
            articles_data (dict): Dictionary where keys are URLs and values are article data.
            
        Returns:
            dict: A dictionary where keys are URLs and values are rewritten article data.
        """
        rewritten_articles = {}
        
        for url, article_data in articles_data.items():
            if article_data:
                logging.info(f"Processing article from {url}")
                # Add original URL to the article data
                article_data['original_url'] = url
                
                # Rewrite the article
                rewritten = self.rewrite_article(article_data)
                
                if rewritten:
                    rewritten_articles[url] = rewritten
                    logging.info(f"Successfully rewrote article: {rewritten['title']}")
                    
                    # Add a small delay to avoid rate limiting
                    time.sleep(1)
                else:
                    logging.warning(f"Failed to rewrite article from {url}")
            else:
                logging.warning(f"Skipping invalid article data from {url}")
                
        return rewritten_articles

# Example usage
if __name__ == "__main__":
    # Example article data for testing
    example_article = {
        "title": "Sample Article Title",
        "paragraphs": [
            "This is the first paragraph of the sample article. It contains some introductory information about the topic.",
            "The second paragraph provides more details and elaborates on the main points of the article.",
            "In conclusion, this final paragraph summarizes the key points and provides a conclusion to the article."
        ],
        "author": "John Doe",
        "date": "2025-03-28",
        "images": ["https://example.com/image1.jpg"]
    }
    
    try:
        # Initialize the rewriter
        # Set your API key here or as an environment variable
        rewriter = ArticleRewriter()  # Or ArticleRewriter("your-api-key")
        
        # Rewrite the example article
        rewritten = rewriter.rewrite_article(example_article)
        
        if rewritten:
            print("\nRewritten Article:")
            print(f"Title: {rewritten['title']}")
            print("\nContent:")
            for p in rewritten['paragraphs']:
                print(f"- {p}")
    except Exception as e:
        print(f"Error: {e}") 