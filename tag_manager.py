import logging
from typing import List, Dict, Any, Optional
from database import Database
from lm_studio import LMStudio
from logger import tag_logger as logger
import json

class TagManager:
    """Manages tag generation and handling for articles."""
    
    def __init__(self, db: Database, lm_studio: Optional[LMStudio] = None):
        """
        Initialize the tag manager.
        
        Args:
            db (Database): Database instance
            lm_studio (LMStudio, optional): LMStudio instance for AI tag generation
        """
        self.db = db
        self.lm_studio = lm_studio
        self.thematic_prompts = self._load_thematic_prompts()
        logger.info("Tag manager initialized")
    
    def _load_thematic_prompts(self) -> Dict[str, str]:
        """Load thematic prompts from config.json."""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('thematic_prompts', {})
        except Exception as e:
            logger.error(f"Error loading thematic prompts from config: {e}")
            return {}
    
    def generate_tags(self, article: Dict[str, Any], max_tags: int = 5) -> List[str]:
        """
        Generate tags for an article using AI and existing tag suggestions.
        
        Args:
            article (Dict[str, Any]): Article data containing title, content, etc.
            max_tags (int): Maximum number of tags to generate
            
        Returns:
            List[str]: Generated tags
        """
        if not self.lm_studio:
            logger.warning("LMStudio not configured, falling back to basic tag suggestions")
            return self._get_basic_suggestions(article.get('content', ''), article.get('title', ''), max_tags)
        
        # Get existing tags
        tag_suggestions = self.db.get_tag_suggestions(article.get('content', ''))
        
        # Combine content and title for better context
        content = f"{article.get('title', '')}\n\n{article.get('content', '')}"
        
        # Generate tags using LMStudio
        prompt = self._construct_tag_prompt(content, tag_suggestions)
        response = self._generate_tags_with_lm_studio(prompt)
        
        # Parse and normalize tags
        normalized_tags = self._parse_generated_tags(response, max_tags)
        
        # Return up to max_tags tags
        return normalized_tags[:max_tags]
    
    def _construct_tag_prompt(self, content: str, tag_suggestions: List[Dict[str, Any]] = None) -> str:
        """Create a prompt for tag generation."""
        prompt = f"""Generate relevant tags for the following article:

Content:
{content[:1000]}...  # Truncated for brevity

Consider these thematic guidelines for tag generation:
"""
        
        # Add thematic prompts
        for tag_name, prompt_text in self.thematic_prompts.items():
            prompt += f"- {tag_name}: {prompt_text}\n"
        
        # Add tag suggestions
        if tag_suggestions:
            prompt += "\nConsider these frequently used tags:\n"
            for tag in tag_suggestions[:5]:
                prompt += f"- {tag['name']} (used {tag['usage_count']} times)\n"
        
        prompt += """
Generate 3-5 relevant tags that:
1. Are specific and descriptive
2. Follow the thematic guidelines
3. Are consistent with existing tags
4. Are relevant to the article content

Format: Return the tags as a JSON array of strings. For example:
["tag1", "tag2", "tag3"]
"""
        
        return prompt
    
    def _parse_generated_tags(self, response: str, max_tags: int) -> List[str]:
        """Parse and normalize the generated tags from the AI response."""
        try:
            # Handle case where response is already a list
            tags = response if isinstance(response, list) else json.loads(response.strip())
            if not isinstance(tags, list):
                logger.warning("LMStudio response was not a list of tags")
                return []
            
            # Normalize tags
            normalized_tags = []
            for tag in tags:
                if isinstance(tag, str):
                    normalized = self.db._normalize_tag(tag)
                    if normalized and normalized not in normalized_tags:
                        normalized_tags.append(normalized)
            
            return normalized_tags[:max_tags]
        except json.JSONDecodeError:
            logger.warning("Could not parse LMStudio response as JSON")
            return []
        except Exception as e:
            logger.error(f"Error parsing generated tags: {e}")
            return []
    
    def _get_basic_suggestions(self, content: str, title: str, max_tags: int) -> List[str]:
        """Get basic tag suggestions based on content and existing tags."""
        # Get existing tags ordered by usage
        suggestions = self.db.get_tag_suggestions(content, limit=max_tags)
        
        # Ensure content is a string
        if isinstance(content, list):
            content = ' '.join(str(item) for item in content)
        if isinstance(title, list):
            title = ' '.join(str(item) for item in title)
        
        # Extract tags from title and content
        text = f"{title} {content}".lower()
        words = text.split()
        
        # Count word frequencies
        word_freq = {}
        for word in words:
            if len(word) > 3:  # Skip short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort words by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        # Combine with existing suggestions
        basic_tags = []
        
        # Add existing suggestions first
        for suggestion in suggestions:
            basic_tags.append(suggestion['name'])
        
        # Add frequent words as tags
        for word, _ in sorted_words:
            if word not in basic_tags and len(basic_tags) < max_tags:
                basic_tags.append(word)
        
        return basic_tags[:max_tags]
    
    def add_thematic_prompt(self, tag_name: str, prompt: str) -> bool:
        """
        Add a thematic prompt for tag generation.
        
        Args:
            tag_name (str): The tag name
            prompt (str): The thematic prompt
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.thematic_prompts[tag_name] = prompt
            logger.info(f"Added thematic prompt for tag: {tag_name}")
            return True
        except Exception as e:
            logger.error(f"Error adding thematic prompt: {e}")
            return False
    
    def get_article_tags(self, article_url: str) -> List[Dict[str, Any]]:
        """
        Get all tags for a specific article.
        
        Args:
            article_url (str): The article URL
            
        Returns:
            List[Dict[str, Any]]: List of tags with their metadata
        """
        return self.db.get_article_tags(article_url)
    
    def add_article_tags(self, article_url: str, tag_names: List[str], 
                        source: str = 'manual') -> bool:
        """
        Add tags to an article.
        
        Args:
            article_url (str): The article URL
            tag_names (List[str]): List of tag names to add
            source (str): Source of the tags ('manual', 'rss', 'scrape', 'ai')
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.db.add_article_tags(article_url, tag_names, source)
    
    def assess_article_relevance(self, article: Dict[str, Any]) -> bool:
        """
        Assess whether an article is relevant based on thematic prompts.
        
        Args:
            article (Dict[str, Any]): Article data containing title, content, etc.
            
        Returns:
            bool: True if the article is relevant, False otherwise
        """
        if not self.lm_studio:
            logger.warning("LMStudio not configured, cannot assess article relevance")
            return True
            
        if not self.thematic_prompts:
            logger.info("No thematic prompts configured, considering all articles relevant")
            return True
            
        # Combine content and title for better context
        content = f"{article.get('title', '')}\n\n{article.get('content', '')}"
        
        # Create prompt for relevance assessment
        prompt = self._create_relevance_prompt(content)
        
        try:
            # Get AI assessment
            response = self.lm_studio.generate(prompt, max_tokens=100)
            if not response:
                logger.warning("Failed to get AI assessment, considering article relevant")
                return True
                
            # Parse response
            response = response.strip().lower()
            if response in ['yes', 'true', '1', 'relevant']:
                logger.info(f"Article '{article.get('title', '')}' assessed as relevant")
                return True
            else:
                logger.info(f"Article '{article.get('title', '')}' assessed as not relevant")
                return False
                
        except Exception as e:
            logger.error(f"Error assessing article relevance: {e}")
            return True
            
    def _create_relevance_prompt(self, content: str) -> str:
        """Create a prompt for assessing article relevance."""
        prompt = f"""Assess whether this article is relevant based on the following thematic guidelines:

Article:
{content[:1000]}...  # Truncated for brevity

Thematic Guidelines:
"""
        
        # Add thematic prompts
        for tag_name, prompt_text in self.thematic_prompts.items():
            prompt += f"- {tag_name}: {prompt_text}\n"
        
        prompt += """
Based on these guidelines, is this article relevant and worth processing?
Consider:
1. Does it align with any of the thematic guidelines?
2. Is it significant enough to warrant processing?
3. Would it provide value to the target audience?

Respond with only 'yes' or 'no'."""
        
        return prompt
    
    def _generate_tags_with_lm_studio(self, prompt: str) -> List[str]:
        """
        Generate tags using LMStudio.
        
        Args:
            prompt (str): The prompt for tag generation
            
        Returns:
            List[str]: Generated tags
        """
        try:
            if not self.lm_studio:
                logger.warning("LMStudio not configured for tag generation")
                return []
            
            # Get response from LMStudio
            response = self.lm_studio.generate(prompt)
            
            # Parse the response into individual tags
            tags = [tag.strip() for tag in response.split('\n') if tag.strip()]
            
            return tags
            
        except Exception as e:
            logger.error(f"Error generating tags with LMStudio: {e}")
            return [] 