import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import re
from logger import database_logger as logger
import time
import csv

class Database:
    """Database manager for storing RSS feeds and processed entries."""
    
    def __init__(self, db_path: str = "feeds.db"):
        """
        Initialize the database manager.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
        logger.info(f"Database initialized at {db_path}")
    
    def _get_connection(self):
        """Get a database connection with a timeout."""
        max_retries = 5  # Increased from 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=120)  # Increased timeout to 120 seconds
                conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging
                conn.execute("PRAGMA busy_timeout=60000")  # Set busy timeout to 60 seconds
                conn.execute("PRAGMA synchronous=NORMAL")  # Reduce synchronous mode for better performance
                conn.execute("PRAGMA cache_size=10000")  # Increase cache size
                conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
                return conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                raise
            except Exception as e:
                logger.error(f"Unexpected error getting database connection: {e}")
                raise
    
    def _init_db(self) -> None:
        """Initialize the database tables."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if processed_entries table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_entries'")
                if cursor.fetchone():
                    # Get existing columns from the old table
                    cursor.execute("PRAGMA table_info(processed_entries)")
                    existing_columns = [col[1] for col in cursor.fetchall()]
                    
                    # Create new table with correct schema
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS processed_entries_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            feed_id INTEGER,
                            entry_id TEXT UNIQUE NOT NULL,
                            title TEXT,
                            link TEXT,
                            published_at TEXT,
                            processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (feed_id) REFERENCES feeds(id)
                        )
                    """)
                    
                    # Map old column names to new ones
                    column_mapping = {
                        'id': 'id',
                        'feed_id': 'feed_id',
                        'entry_url': 'link',  # Map entry_url to link
                        'title': 'title',
                        'published_at': 'published_at',
                        'processed_at': 'processed_at'
                    }
                    
                    # Build the INSERT statement using mapped columns
                    old_cols = []
                    new_cols = []
                    for old_col in existing_columns:
                        if old_col in column_mapping:
                            old_cols.append(old_col)
                            new_cols.append(column_mapping[old_col])
                    
                    if old_cols:
                        old_cols_str = ', '.join(old_cols)
                        new_cols_str = ', '.join(new_cols)
                        cursor.execute(f"""
                            INSERT OR IGNORE INTO processed_entries_new ({new_cols_str})
                            SELECT {old_cols_str}
                            FROM processed_entries
                        """)
                    
                    # Drop old table and rename new table
                    cursor.execute("DROP TABLE processed_entries")
                    cursor.execute("ALTER TABLE processed_entries_new RENAME TO processed_entries")
                    logger.info("Recreated processed_entries table with entry_id column")
                else:
                    # Table doesn't exist - create it
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS processed_entries (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            feed_id INTEGER,
                            entry_id TEXT UNIQUE NOT NULL,
                            title TEXT,
                            link TEXT,
                            published_at TEXT,
                            processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (feed_id) REFERENCES feeds(id)
                        )
                    """)
                
                # Create other tables if they don't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS feeds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        name TEXT,
                        is_active INTEGER DEFAULT 1,
                        is_paywalled INTEGER DEFAULT 0,
                        last_fetch TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        paywall_hits INTEGER DEFAULT 0,
                        last_paywall_hit TEXT
                    )
                """)
                
                # Create articles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        feed_id INTEGER,
                        url TEXT UNIQUE NOT NULL,
                        title TEXT,
                        content TEXT,
                        author TEXT,
                        published_date TEXT,
                        processed INTEGER DEFAULT 0,
                        wordpress_post_id TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (feed_id) REFERENCES feeds(id)
                    )
                """)
                
                # Create paywall_hits table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS paywall_hits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        feed_id INTEGER NOT NULL,
                        url TEXT NOT NULL,
                        hit_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (feed_id) REFERENCES feeds (id)
                    )
                """)
                
                # Create tags table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        normalized_name TEXT UNIQUE NOT NULL,
                        source TEXT,
                        usage_count INTEGER DEFAULT 0,
                        last_used TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 1
                    )
                """)
                
                # Create article_tags table for many-to-many relationship
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS article_tags (
                        article_id INTEGER,
                        tag_id INTEGER,
                        source TEXT DEFAULT 'manual',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (article_id, tag_id),
                        FOREIGN KEY (article_id) REFERENCES articles (id),
                        FOREIGN KEY (tag_id) REFERENCES tags (id)
                    )
                """)
                
                conn.commit()
                logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def add_feed(self, url: str, name: str) -> Optional[int]:
        """
        Add a new feed to the database.
        
        Args:
            url (str): The feed URL
            name (str): The feed name
            
        Returns:
            Optional[int]: The feed ID if successful, None otherwise
        """
        if not url or not url.strip():
            logger.error("Feed URL cannot be empty")
            return None
            
        url = url.strip()
        
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Check if feed already exists (case-insensitive)
                c.execute('SELECT id, name FROM feeds WHERE LOWER(url) = LOWER(?)', (url,))
                existing = c.fetchone()
                if existing:
                    logger.warning(f"Feed URL '{url}' already exists with ID {existing[0]} and name '{existing[1]}'")
                    return existing[0]
                
                # Validate URL format
                if not url.startswith(('http://', 'https://')):
                    logger.error(f"Invalid feed URL format: {url}")
                    return None
                
                # Add new feed
                c.execute('''
                    INSERT INTO feeds (url, name, is_active)
                    VALUES (?, ?, 1)
                ''', (url, name or url))
                
                feed_id = c.lastrowid
                conn.commit()
                logger.info(f"Successfully added feed: {url}")
                return feed_id
                
        except sqlite3.IntegrityError as e:
            logger.error(f"Database integrity error adding feed {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error adding feed {url}: {e}")
            return None
    
    def import_feeds_from_csv(self, csv_path: str) -> dict:
        """Import feeds from a CSV file.
        Returns a dictionary with import statistics."""
        stats = {
            'total': 0,
            'added': 0,
            'duplicates': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # Read CSV file
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Convert headers to lowercase for case-insensitive matching
                if reader.fieldnames:
                    reader.fieldnames = [h.lower().replace(' ', '_') for h in reader.fieldnames]
                
                # Check headers
                headers = set(reader.fieldnames) if reader.fieldnames else set()
                if 'url' not in headers:
                    stats['errors'].append("CSV file must have a 'URL' column")
                    return stats
                    
                # Process feeds
                for row in reader:
                    stats['total'] += 1
                    try:
                        url = row.get('url', '').strip()
                        name = row.get('feed_name', row.get('name', url)).strip()  # Try both feed_name and name
                        
                        if not url:
                            stats['failed'] += 1
                            stats['errors'].append(f"Row {stats['total']}: Empty URL")
                            continue
                            
                        # Try to add the feed
                        if self.add_feed(url, name):
                            stats['added'] += 1
                        else:
                            stats['duplicates'] += 1
                            
                    except Exception as e:
                        stats['failed'] += 1
                        stats['errors'].append(f"Row {stats['total']}: {str(e)}")
                        
        except FileNotFoundError:
            stats['errors'].append(f"CSV file not found: {csv_path}")
        except Exception as e:
            stats['errors'].append(f"Error reading CSV: {str(e)}")
            
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
            SELECT id, url, name, is_active, is_paywalled, 
                   last_fetch, created_at, paywall_hits
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
            for key in ['last_fetch', 'created_at']:
                if feed[key]:
                    feed[key] = datetime.fromisoformat(feed[key]).isoformat()
            feeds.append(feed)
        
        conn.close()
        return feeds
    
    def get_active_feeds(self) -> List[Dict[str, Any]]:
        """
        Get all active feeds.
        
        Returns:
            List[Dict[str, Any]]: List of active feed information
        """
        conn = self._get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''
                SELECT id, url, name, is_active, is_paywalled, 
                       last_fetch, created_at, paywall_hits
                FROM feeds
                WHERE is_active = 1
                ORDER BY name
            ''')
            
            columns = [description[0] for description in c.description]
            feeds = []
            
            for row in c.fetchall():
                feed = dict(zip(columns, row))
                # Format timestamps for JSON serialization
                for key in ['last_fetch', 'created_at']:
                    if feed[key]:
                        feed[key] = datetime.fromisoformat(feed[key]).isoformat()
                feeds.append(feed)
            
            return feeds
        finally:
            conn.close()
    
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
    
    def update_feed_status(self, feed_id: int, is_active: bool = None, is_paywalled: bool = None) -> bool:
        """
        Update a feed's status.
        
        Args:
            feed_id (int): The feed ID
            is_active (bool, optional): Whether the feed is active
            is_paywalled (bool, optional): Whether the feed is paywalled
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Check if feed exists
                c.execute('SELECT 1 FROM feeds WHERE id = ?', (feed_id,))
                if not c.fetchone():
                    logging.warning(f"Feed {feed_id} does not exist")
                    return False
                
                updates = []
                params = []
                
                if is_active is not None:
                    updates.append('is_active = ?')
                    params.append(1 if is_active else 0)
                
                if is_paywalled is not None:
                    updates.append('is_paywalled = ?')
                    params.append(1 if is_paywalled else 0)
                
                if not updates:
                    return True
                
                params.append(feed_id)
                query = f'''
                    UPDATE feeds
                    SET {', '.join(updates)}
                    WHERE id = ?
                '''
                
                c.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating feed status {feed_id}: {e}")
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
        Remove a feed from the database.
        
        Args:
            feed_id (int): The feed ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Check if feed exists
                c.execute('SELECT 1 FROM feeds WHERE id = ?', (feed_id,))
                if not c.fetchone():
                    logging.warning(f"Feed {feed_id} does not exist")
                    return False
                
                # First delete related records
                c.execute('DELETE FROM articles WHERE feed_id = ?', (feed_id,))
                c.execute('DELETE FROM processed_entries WHERE feed_id = ?', (feed_id,))
                c.execute('DELETE FROM paywall_hits WHERE feed_id = ?', (feed_id,))
                
                # Then delete the feed
                c.execute('DELETE FROM feeds WHERE id = ?', (feed_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error removing feed {feed_id}: {e}")
            return False
    
    def add_tag(self, name: str, source: str = 'manual') -> Optional[int]:
        """
        Add a new tag to the database.
        
        Args:
            name (str): The tag name
            source (str): Source of the tag ('manual', 'rss', 'scrape', 'ai')
            
        Returns:
            Optional[int]: The tag ID if successful, None otherwise
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Normalize tag name
                normalized_name = self._normalize_tag(name)
                
                # Check if tag already exists
                c.execute('SELECT id FROM tags WHERE normalized_name = ?', (normalized_name,))
                existing = c.fetchone()
                if existing:
                    # Update usage count and last used date
                    c.execute('''
                        UPDATE tags 
                        SET usage_count = usage_count + 1,
                            last_used = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (existing[0],))
                    return existing[0]
                
                # Add new tag
                c.execute('''
                    INSERT INTO tags (name, normalized_name, source)
                    VALUES (?, ?, ?)
                ''', (name, normalized_name, source))
                
                tag_id = c.lastrowid
                conn.commit()
                return tag_id
        except Exception as e:
            logging.error(f"Error adding tag {name}: {e}")
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
                SELECT id, name, normalized_name, usage_count
                FROM tags
                WHERE is_active = 1
                ORDER BY usage_count DESC
                LIMIT 100
            ''')
            
            existing_tags = [{
                'id': row[0],
                'name': row[1],
                'normalized_name': row[2],
                'usage_count': row[3]
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
            with self._get_connection() as conn:
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
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # First ensure the tag exists
                tag_id = self.add_tag(tag_name)
                if not tag_id:
                    return False
                
                # Update the tag's thematic prompt
                c.execute('''
                    UPDATE tags
                    SET thematic_prompt = ?
                    WHERE id = ?
                ''', (prompt, tag_id))
                
                conn.commit()
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
        """Add tags to an article."""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    # ... existing tag addition code ...
                    return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    if attempt < max_retries - 1:
                        logger.warning(f"Database locked, retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                logger.error(f"Error adding tags: {e}")
                return False
            except Exception as e:
                logger.error(f"Error adding tags: {e}")
                return False
        
        return False
    
    def save_article(self, article_data: Dict[str, Any]) -> bool:
        """
        Save an article to the database.
        
        Args:
            article_data (Dict[str, Any]): Article data including url, title, content, etc.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Extract article data
                url = article_data.get('url')
                title = article_data.get('title')
                content = article_data.get('content')
                author = article_data.get('author')
                published_date = article_data.get('published_date')
                processed = article_data.get('processed', 0)
                wordpress_post_id = article_data.get('wordpress_post_id')
                feed_id = article_data.get('feed_id')
                
                # Save article
                c.execute('''
                    INSERT OR REPLACE INTO articles 
                    (url, title, content, author, published_date, processed, wordpress_post_id, feed_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (url, title, content, author, published_date, processed, wordpress_post_id, feed_id))
                
                # Save tags if present
                if 'tags' in article_data and article_data['tags']:
                    self.add_article_tags(url, article_data['tags'], source='rss')
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving article {article_data.get('url')}: {e}")
            return False
    
    def get_feed(self, feed_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a feed by its ID.
        
        Args:
            feed_id (int): The feed ID
            
        Returns:
            Optional[Dict[str, Any]]: The feed data if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                c.execute('''
                    SELECT id, url, name, is_active, is_paywalled, last_fetch, created_at
                    FROM feeds
                    WHERE id = ?
                ''', (feed_id,))
                
                row = c.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'url': row[1],
                        'name': row[2],
                        'is_active': bool(row[3]),
                        'is_paywalled': bool(row[4]),
                        'last_fetch': row[5],
                        'created_at': row[6]
                    }
                return None
        except Exception as e:
            logging.error(f"Error getting feed {feed_id}: {e}")
            return None
    
    def get_feed_articles(self, feed_id: int) -> List[Dict[str, Any]]:
        """
        Get all articles for a specific feed.
        
        Args:
            feed_id (int): The feed ID
            
        Returns:
            List[Dict[str, Any]]: List of articles for the feed
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Check if feed exists
                c.execute('SELECT 1 FROM feeds WHERE id = ?', (feed_id,))
                if not c.fetchone():
                    logging.warning(f"Feed {feed_id} does not exist")
                    return []
                
                c.execute('''
                    SELECT id, url, title, content, author, published_date, 
                           processed, wordpress_post_id, created_at
                    FROM articles
                    WHERE feed_id = ?
                    ORDER BY published_date DESC
                ''', (feed_id,))
                
                columns = [description[0] for description in c.description]
                articles = []
                
                for row in c.fetchall():
                    article = dict(zip(columns, row))
                    # Convert timestamps to ISO format
                    for key in ['published_date', 'created_at']:
                        if article[key]:
                            article[key] = datetime.fromisoformat(article[key]).isoformat()
                    articles.append(article)
                
                return articles
        except Exception as e:
            logging.error(f"Error getting articles for feed {feed_id}: {e}")
            return []
    
    def get_unprocessed_articles(self) -> List[Dict[str, Any]]:
        """
        Get all unprocessed articles.
        
        Returns:
            List[Dict[str, Any]]: List of unprocessed articles
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                c.execute('''
                    SELECT id, url, title, content, author, published_date, 
                           processed, wordpress_post_id, created_at, feed_id
                    FROM articles
                    WHERE processed = 0
                    ORDER BY published_date DESC
                ''')
                
                columns = [description[0] for description in c.description]
                articles = []
                
                for row in c.fetchall():
                    article = dict(zip(columns, row))
                    # Convert timestamps to ISO format
                    for key in ['published_date', 'created_at']:
                        if article[key]:
                            article[key] = datetime.fromisoformat(article[key]).isoformat()
                    articles.append(article)
                
                return articles
        except Exception as e:
            logging.error(f"Error getting unprocessed articles: {e}")
            return []
    
    def export_feeds_to_csv(self, csv_path: str) -> bool:
        """
        Export all feeds to a CSV file.
        
        Args:
            csv_path (str): Path to save the CSV file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                
                # Get all feeds
                c.execute('''
                    SELECT url, name, is_active, is_paywalled, 
                           last_fetch, created_at, paywall_hits
                    FROM feeds
                    ORDER BY name
                ''')
                
                feeds = c.fetchall()
                
                # Write to CSV
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # Write header
                    writer.writerow(['url', 'name', 'is_active', 'is_paywalled', 
                                   'last_fetch', 'created_at', 'paywall_hits'])
                    # Write data
                    writer.writerows(feeds)
                
                logger.info(f"Successfully exported {len(feeds)} feeds to {csv_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error exporting feeds to CSV: {e}")
            return False 