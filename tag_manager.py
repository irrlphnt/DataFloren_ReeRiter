import logging
from typing import List, Dict, Any, Optional
from database import Database
from lm_studio import LMStudio

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
    
    def generate_tags(self, content: str, title: str, existing_tags: List[str] = None, 
                     max_tags: int = 5) -> List[str]:
        """
        Generate tags for an article using AI and existing tag suggestions.
        
        Args:
            content (str): Article content
            title (str): Article title
            existing_tags (List[str], optional): Existing tags to consider
            max_tags (int): Maximum number of tags to generate
            
        Returns:
            List[str]: Generated tags
        """
        if not self.lm_studio:
            logging.warning("LMStudio not configured, falling back to basic tag suggestions")
            return self._get_basic_suggestions(content, title, max_tags)
        
        # Get thematic prompts and existing tags
        thematic_prompts = self.db.get_thematic_prompts()
        tag_suggestions = self.db.get_tag_suggestions(content)
        
        # Prepare the prompt
        prompt = self._create_tag_generation_prompt(
            content, title, existing_tags, thematic_prompts, tag_suggestions
        )
        
        try:
            # Generate tags using LMStudio
            response = self.lm_studio.generate(prompt)
            if not response:
                return self._get_basic_suggestions(content, title, max_tags)
            
            # Parse and normalize the generated tags
            generated_tags = self._parse_generated_tags(response, max_tags)
            
            # Add generated tags to the database
            for tag in generated_tags:
                self.db.add_tag(tag, source='ai')
            
            return generated_tags
            
        except Exception as e:
            logging.error(f"Error generating tags with AI: {e}")
            return self._get_basic_suggestions(content, title, max_tags)
    
    def _create_tag_generation_prompt(self, content: str, title: str, 
                                    existing_tags: List[str],
                                    thematic_prompts: List[Dict[str, Any]],
                                    tag_suggestions: List[Dict[str, Any]]) -> str:
        """Create a prompt for tag generation."""
        prompt = f"""Generate relevant tags for the following article:

Title: {title}

Content:
{content[:1000]}...  # Truncated for brevity

Consider these thematic prompts for tag generation:
"""
        
        # Add thematic prompts
        for prompt_data in thematic_prompts:
            prompt += f"- {prompt_data['tag_name']}: {prompt_data['prompt']}\n"
        
        # Add existing tags if any
        if existing_tags:
            prompt += f"\nExisting tags: {', '.join(existing_tags)}\n"
        
        # Add tag suggestions
        if tag_suggestions:
            prompt += "\nConsider these frequently used tags:\n"
            for tag in tag_suggestions[:5]:
                prompt += f"- {tag['name']} (used {tag['usage_count']} times)\n"
        
        prompt += f"""
Generate {max(3, min(5, len(thematic_prompts) + 2))} relevant tags that:
1. Are specific and descriptive
2. Follow the thematic guidelines
3. Are consistent with existing tags
4. Are relevant to the article content

Format: Return only the tags, one per line, without any additional text or formatting.
"""
        
        return prompt
    
    def _parse_generated_tags(self, response: str, max_tags: int) -> List[str]:
        """Parse and normalize the generated tags from the AI response."""
        # Split response into lines and clean up
        tags = [line.strip() for line in response.split('\n') if line.strip()]
        
        # Normalize tags
        normalized_tags = []
        for tag in tags:
            normalized = self.db._normalize_tag(tag)
            if normalized and normalized not in normalized_tags:
                normalized_tags.append(normalized)
        
        return normalized_tags[:max_tags]
    
    def _get_basic_suggestions(self, content: str, title: str, max_tags: int) -> List[str]:
        """Get basic tag suggestions based on content and existing tags."""
        # Get existing tags ordered by usage
        suggestions = self.db.get_tag_suggestions(content, limit=max_tags)
        
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
        return self.db.add_thematic_prompt(tag_name, prompt)
    
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