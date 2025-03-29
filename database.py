import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import re

class Database:
    """Database manager for storing RSS feeds and processed entries."""
    
    def __init__(self, db_path: str = "articles.db"):
        """
        Initialize the database manager.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create feeds table
        c.execute('''
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                is_active BOOLEAN DEFAULT 1,
                last_fetch TIMESTAMP,
                paywall_hits INTEGER DEFAULT 0,
                is_paywalled BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create processed_entries table
        c.execute('''
            CREATE TABLE IF NOT EXISTS processed_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                entry_id TEXT UNIQUE NOT NULL,
                title TEXT,
                link TEXT,
                published_date TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
        ''')
        
        # Create paywall_hits table
        c.execute('''
            CREATE TABLE IF NOT EXISTS paywall_hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                url TEXT NOT NULL,
                hit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
        ''')
        
        # Create tags table
        c.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                normalized_name TEXT NOT NULL,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                thematic_prompt TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create article_tags table (many-to-many relationship)
        c.execute('''
            CREATE TABLE IF NOT EXISTS article_tags (
                article_url TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                source TEXT NOT NULL,  -- 'rss', 'scrape', 'ai'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (article_url, tag_id),
                FOREIGN KEY (tag_id) REFERENCES tags (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_feed(self, url: str, name: str = None) -> bool:
        """
        Add a new feed to the database.
        
        Args:
            url (str): The feed URL
            name (str, optional): A friendly name for the feed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # If no name provided, use the URL as the name
            if not name:
                name = url
            
            c.execute('''
                INSERT INTO feeds (url, name)
                VALUES (?, ?)
            ''', (url, name))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            logging.warning(f"Feed URL {url} already exists")
            return False
        except Exception as e:
            logging.error(f"Error adding feed {url}: {e}")
            return False
    
    def import_feeds_from_csv(self, csv_path: str) -> Dict[str, int]:
        """
        Import feeds from a CSV file.
        
        Args:
            csv_path (str): Path to the CSV file
            
        Returns:
            Dict[str, int]: Statistics about the import (total, successful, failed)
        """
        stats = {
            'total': 0,
            'successful': 0,
            'failed': 0
        }
        
        try:
            import csv
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    stats['total'] += 1
                    url = row.get('url', '').strip()
                    name = row.get('name', '').strip()
                    
                    if not url:
                        logging.warning(f"Skipping row {stats['total']}: No URL provided")
                        stats['failed'] += 1
                        continue
                    
                    if not name:
                        name = url
                    
                    if self.add_feed(url, name):
                        stats['successful'] += 1
                    else:
                        stats['failed'] += 1
                
                return stats
                
        except Exception as e:
            logging.error(f"Error importing feeds from CSV: {e}")
            return stats
    
    def list_feeds(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        List all feeds in the database.
        
        Args:
            include_inactive (bool): Whether to include inactive feeds
            
        Returns:
            List[Dict[str, Any]]: List of feed information
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        query = '''
            SELECT id, url, name, title, is_active, is_paywalled, 
                   last_fetch, created_at, last_checked, paywall_hits, last_paywall_hit
            FROM feeds
        '''
        
        if not include_inactive:
            query += ' WHERE is_active = 1'
        
        query += ' ORDER BY name'
        
        c.execute(query)
        
        columns = [description[0] for description in c.description]
        feeds = []
        
        for row in c.fetchall():
            feed = dict(zip(columns, row))
            # Convert timestamps to ISO format
            for key in ['last_fetch', 'created_at', 'last_checked', 'last_paywall_hit']:
                if feed[key]:
                    feed[key] = datetime.fromisoformat(feed[key]).isoformat()
            feeds.append(feed)
        
        conn.close()
        return feeds
    
    def get_active_feeds(self) -> List[Dict[str, Any]]:
        """
        Get all active RSS feeds from the database.
        
        Returns:
            List[Dict[str, Any]]: List of feed dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT id, url, title FROM feeds WHERE is_active = 1")
            return [
                {"id": row[0], "url": row[1], "title": row[2]}
                for row in c.fetchall()
            ]
        except Exception as e:
            logging.error(f"Error getting active feeds: {e}")
            return []
    
    def mark_entry_processed(self, feed_id: int, entry_id: str, title: str, 
                           link: str, published_at: Optional[str] = None) -> bool:
        """
        Mark an entry as processed in the database.
        
        Args:
            feed_id (int): The ID of the feed
            entry_id (str): The unique ID of the entry
            title (str): The entry title
            link (str): The entry URL
            published_at (Optional[str]): The publication date
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO processed_entries 
                (feed_id, entry_id, title, link, published_at)
                VALUES (?, ?, ?, ?, ?)
            """, (feed_id, entry_id, title, link, published_at))
            
            # Update feed's last fetch time
            c.execute("""
                UPDATE feeds 
                SET last_fetch = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (feed_id,))
            
            conn.commit()
            conn.close()
            return c.rowcount > 0
        except Exception as e:
            logging.error(f"Error marking entry as processed: {e}")
            return False
    
    def is_entry_processed(self, entry_id: str) -> bool:
        """
        Check if an entry has been processed before.
        
        Args:
            entry_id (str): The unique ID of the entry
            
        Returns:
            bool: True if the entry has been processed, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "SELECT 1 FROM processed_entries WHERE entry_id = ?",
                (entry_id,)
            )
            return c.fetchone() is not None
        except Exception as e:
            logging.error(f"Error checking processed entry: {e}")
            return False
    
    def update_feed_status(self, feed_id: int, is_active: bool) -> bool:
        """
        Update the active status of a feed.
        
        Args:
            feed_id (int): The ID of the feed
            is_active (bool): Whether the feed is active
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                "UPDATE feeds SET is_active = ? WHERE id = ?",
                (is_active, feed_id)
            )
            conn.commit()
            conn.close()
            return c.rowcount > 0
        except Exception as e:
            logging.error(f"Error updating feed status: {e}")
            return False
    
    def get_feed_stats(self) -> Dict[str, Any]:
        """
        Get statistics about feeds and processed entries.
        
        Returns:
            Dict[str, Any]: Dictionary containing statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Get total feeds
            c.execute("SELECT COUNT(*) FROM feeds")
            total_feeds = c.fetchone()[0]
            
            # Get active feeds
            c.execute("SELECT COUNT(*) FROM feeds WHERE is_active = 1")
            active_feeds = c.fetchone()[0]
            
            # Get total processed entries
            c.execute("SELECT COUNT(*) FROM processed_entries")
            total_entries = c.fetchone()[0]
            
            # Get feeds with most entries
            c.execute("""
                SELECT f.url, COUNT(pe.id) as entry_count
                FROM feeds f
                LEFT JOIN processed_entries pe ON f.id = pe.feed_id
                GROUP BY f.id
                ORDER BY entry_count DESC
                LIMIT 5
            """)
            top_feeds = c.fetchall()
            
            conn.close()
            
            return {
                "total_feeds": total_feeds,
                "active_feeds": active_feeds,
                "total_entries": total_entries,
                "top_feeds": [
                    {"url": url, "entry_count": count}
                    for url, count in top_feeds
                ]
            }
        except Exception as e:
            logging.error(f"Error getting feed stats: {e}")
            return {
                "total_feeds": 0,
                "active_feeds": 0,
                "total_entries": 0,
                "top_feeds": []
            }
    
    def record_paywall_hit(self, feed_id: int, article_url: str) -> None:
        """
        Record a paywall hit for a feed.
        
        Args:
            feed_id (int): The ID of the feed
            article_url (str): The URL of the paywalled article
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Record the hit
        c.execute('''
            INSERT INTO paywall_hits (feed_id, url)
            VALUES (?, ?)
        ''', (feed_id, article_url))
        
        # Update feed stats
        c.execute('''
            UPDATE feeds 
            SET paywall_hits = paywall_hits + 1,
                last_paywall_hit = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (feed_id,))
        
        conn.commit()
        conn.close()
    
    def get_recent_paywall_hits(self, feed_id: int, days: int = 7) -> int:
        """
        Get the number of paywall hits for a feed in the last N days.
        
        Args:
            feed_id (int): The ID of the feed
            days (int): Number of days to look back
            
        Returns:
            int: Number of paywall hits
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT COUNT(*) FROM paywall_hits
            WHERE feed_id = ?
            AND hit_date >= datetime('now', ?)
        ''', (feed_id, f'-{days} days'))
        
        return c.fetchone()[0]
    
    def mark_feed_as_paywalled(self, feed_id: int) -> bool:
        """
        Mark a feed as paywalled.
        
        Args:
            feed_id (int): The ID of the feed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                UPDATE feeds 
                SET is_paywalled = 1,
                    is_active = 0
                WHERE id = ?
            ''', (feed_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error marking feed {feed_id} as paywalled: {e}")
            return False
    
    def remove_feed(self, feed_id: int) -> bool:
        """
        Remove a feed and its associated data.
        
        Args:
            feed_id (int): The ID of the feed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Remove paywall hits
            c.execute('DELETE FROM paywall_hits WHERE feed_id = ?', (feed_id,))
            
            # Remove the feed
            c.execute('DELETE FROM feeds WHERE id = ?', (feed_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error removing feed {feed_id}: {e}")
            return False
    
    def add_tag(self, name: str, source: str = 'manual', thematic_prompt: str = None) -> Optional[int]:
        """
        Add a new tag to the database.
        
        Args:
            name (str): The tag name
            source (str): Source of the tag ('manual', 'rss', 'scrape', 'ai')
            thematic_prompt (str, optional): Thematic prompt for AI tag generation
            
        Returns:
            Optional[int]: Tag ID if successful, None otherwise
        """
        try:
            normalized_name = self._normalize_tag(name)
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Check if tag already exists
            c.execute('SELECT id FROM tags WHERE normalized_name = ?', (normalized_name,))
            existing_tag = c.fetchone()
            
            if existing_tag:
                # Update usage count and last used
                c.execute('''
                    UPDATE tags 
                    SET usage_count = usage_count + 1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (existing_tag[0],))
                tag_id = existing_tag[0]
            else:
                # Insert new tag
                c.execute('''
                    INSERT INTO tags (name, normalized_name, thematic_prompt)
                    VALUES (?, ?, ?)
                ''', (name, normalized_name, thematic_prompt))
                tag_id = c.lastrowid
            
            conn.commit()
            conn.close()
            return tag_id
            
        except Exception as e:
            logging.error(f"Error adding tag '{name}': {e}")
            return None
    
    def _normalize_tag(self, tag: str) -> str:
        """
        Normalize a tag name by:
        1. Converting to lowercase
        2. Removing special characters
        3. Replacing spaces with hyphens
        4. Removing multiple consecutive hyphens
        
        Args:
            tag (str): The tag to normalize
            
        Returns:
            str: Normalized tag
        """
        # Convert to lowercase
        tag = tag.lower()
        
        # Remove special characters except spaces and hyphens
        tag = re.sub(r'[^a-z0-9\s-]', '', tag)
        
        # Replace spaces with hyphens
        tag = re.sub(r'\s+', '-', tag)
        
        # Remove multiple consecutive hyphens
        tag = re.sub(r'-+', '-', tag)
        
        # Remove leading and trailing hyphens
        tag = tag.strip('-')
        
        return tag
    
    def get_tag_suggestions(self, content: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get tag suggestions based on content and existing tags.
        
        Args:
            content (str): Article content to analyze
            limit (int): Maximum number of suggestions to return
            
        Returns:
            List[Dict[str, Any]]: List of suggested tags with their metadata
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Get active tags ordered by usage count
            c.execute('''
                SELECT id, name, normalized_name, usage_count, thematic_prompt
                FROM tags
                WHERE is_active = 1
                ORDER BY usage_count DESC
                LIMIT 100
            ''')
            
            existing_tags = [{
                'id': row[0],
                'name': row[1],
                'normalized_name': row[2],
                'usage_count': row[3],
                'thematic_prompt': row[4]
            } for row in c.fetchall()]
            
            conn.close()
            
            # Return top tags based on usage count
            return existing_tags[:limit]
            
        except Exception as e:
            logging.error(f"Error getting tag suggestions: {e}")
            return []
    
    def get_thematic_prompts(self) -> List[Dict[str, Any]]:
        """
        Get all thematic prompts for tag generation.
        
        Returns:
            List[Dict[str, Any]]: List of thematic prompts with their associated tags
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT id, name, thematic_prompt
                FROM tags
                WHERE thematic_prompt IS NOT NULL
                AND is_active = 1
            ''')
            
            prompts = [{
                'id': row[0],
                'tag_name': row[1],
                'prompt': row[2]
            } for row in c.fetchall()]
            
            conn.close()
            return prompts
            
        except Exception as e:
            logging.error(f"Error getting thematic prompts: {e}")
            return []
    
    def add_thematic_prompt(self, tag_name: str, prompt: str) -> bool:
        """
        Add or update a thematic prompt for a tag.
        
        Args:
            tag_name (str): The tag name
            prompt (str): The thematic prompt
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # First ensure the tag exists
            tag_id = self.add_tag(tag_name)
            if not tag_id:
                return False
            
            # Update the thematic prompt
            c.execute('''
                UPDATE tags
                SET thematic_prompt = ?
                WHERE id = ?
            ''', (prompt, tag_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logging.error(f"Error adding thematic prompt for '{tag_name}': {e}")
            return False
    
    def get_article_tags(self, article_url: str) -> List[Dict[str, Any]]:
        """
        Get all tags for a specific article.
        
        Args:
            article_url (str): The article URL
            
        Returns:
            List[Dict[str, Any]]: List of tags with their metadata
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT t.id, t.name, t.normalized_name, at.source, at.created_at
                FROM article_tags at
                JOIN tags t ON at.tag_id = t.id
                WHERE at.article_url = ?
                ORDER BY at.created_at DESC
            ''', (article_url,))
            
            tags = [{
                'id': row[0],
                'name': row[1],
                'normalized_name': row[2],
                'source': row[3],
                'created_at': row[4]
            } for row in c.fetchall()]
            
            conn.close()
            return tags
            
        except Exception as e:
            logging.error(f"Error getting tags for article {article_url}: {e}")
            return []
    
    def add_article_tags(self, article_url: str, tag_names: List[str], source: str = 'manual') -> bool:
        """
        Add tags to an article.
        
        Args:
            article_url (str): The article URL
            tag_names (List[str]): List of tag names to add
            source (str): Source of the tags ('manual', 'rss', 'scrape', 'ai')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            for tag_name in tag_names:
                # Add or get tag
                tag_id = self.add_tag(tag_name, source)
                if not tag_id:
                    continue
                
                # Add article-tag relationship
                c.execute('''
                    INSERT OR IGNORE INTO article_tags (article_url, tag_id, source)
                    VALUES (?, ?, ?)
                ''', (article_url, tag_id, source))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logging.error(f"Error adding tags to article {article_url}: {e}")
            return False 