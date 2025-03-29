# Article Monitor & Rewriter

A Python-based tool for monitoring RSS feeds, extracting article content, and optionally rewriting articles using AI. The tool can handle both RSS feed content and direct article scraping, with smart paywall detection and handling.

## Features

### RSS Feed Monitoring
- Monitor multiple RSS feeds simultaneously
- Extract article content, titles, authors, and metadata
- Smart content extraction with fallback to direct article scraping
- Automatic paywall detection and handling
- Feed management (add, remove, enable/disable feeds)
- Database storage for feed and article tracking

### Content Extraction
- Intelligent content parsing from RSS feeds
- Fallback to direct article scraping when needed
- Smart paragraph extraction and cleaning
- Metadata extraction (title, author, date, tags)
- Support for various content formats and structures

### Paywall Detection & Handling
- Automatic detection of paywalled content
- Tracking of paywall hits per feed
- Smart feed management for paywalled sources
- User interaction for handling paywalled feeds
- Configurable paywall detection thresholds

### Article Processing
- Content cleaning and formatting
- Paragraph extraction and validation
- Metadata preservation
- Support for various article formats
- Configurable content processing rules

### Database Management
- SQLite database for persistent storage
- Feed and article tracking
- Paywall hit tracking
- Feed statistics and monitoring
- Automatic database initialization

### Tag Management

The system includes a sophisticated tag management system that supports:
- Automatic tag generation using AI
- Tag normalization and deduplication
- Thematic prompts for consistent tagging
- Tag suggestions based on content and usage history

#### Adding Thematic Prompts

You can add thematic prompts to guide tag generation:

```bash
python main.py --add-thematic-prompt "Technology" "Focus on emerging technologies, digital trends, and innovation"
python main.py --add-thematic-prompt "Science" "Include scientific discoveries, research findings, and scientific methodology"
```

#### Tag Generation

Tags are automatically generated for each article using:
1. AI-based analysis of article content
2. Existing tags from the RSS feed
3. Thematic prompts
4. Frequently used tags in the system

The system will:
- Normalize tags (lowercase, remove special characters)
- Remove duplicates
- Consider thematic guidelines
- Track tag usage statistics

#### Tag Sources

Tags can come from multiple sources:
- RSS feeds (original article tags)
- Direct scraping (tags from article pages)
- AI generation (based on content analysis)
- Manual addition

#### Tag Database

The system maintains a database of tags with:
- Normalized names
- Usage statistics
- Thematic prompts
- Source tracking
- Last used timestamps

#### Example Usage

1. Add a thematic prompt:
```bash
python main.py --add-thematic-prompt "Cybersecurity" "Focus on security threats, data protection, and privacy"
```

2. Process articles with tag generation:
```bash
python main.py --limit 5
```

3. View article tags:
```bash
python main.py --show-article-tags "https://example.com/article"
```

The generated tags will be:
- Normalized (e.g., "Machine Learning" → "machine-learning")
- Consistent with thematic guidelines
- Based on article content
- Tracked in the database for future suggestions

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/article-monitor-rewriter.git
   cd article-monitor-rewriter
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the application:
   - Copy `config.json.example` to `config.json`
   - Update the configuration with your settings

## Configuration

The `config.json` file supports the following settings:

```json
{
    "monitor": {
        "use_rss": true,
        "website_url": "https://your-website.com",
        "link_limit": 5,
        "rss_feeds": [
            "https://your-website.com/feed/",
            "https://your-website.com/feed/rss/"
        ],
        "rss_max_entries": 10,
        "rss_timeout": 10,
        "rss_min_paragraph_length": 20,
        "rss_content_classes": [
            "entry-content",
            "post-content",
            "article-content"
        ]
    }
}
```

## Usage

### Quick Start

1. First, add your RSS feed to the configuration:
   ```bash
   # Edit config.json and add your feed URL to the rss_feeds list
   ```

2. Run the script to process articles:
   ```bash
   python main.py --limit 5
   ```

### Command Line Options

```bash
python main.py [options]
```

Available options:
- `--limit N`: Process only N articles (default: all)
- `--skip-rewrite`: Skip the article rewriting step
- `--skip-wordpress`: Skip WordPress posting
- `--force-refresh`: Force refresh of cached content
- `--add-feed URL`: Add a new RSS feed URL
- `--list-feeds`: List all configured feeds
- `--remove-feed ID`: Remove a feed by its ID
- `--toggle-feed ID`: Enable/disable a feed
- `--show-stats`: Display feed statistics

### Examples

1. Add a new RSS feed:
   ```bash
   python main.py --add-feed "https://example.com/feed/"
   ```

2. List all configured feeds:
   ```bash
   python main.py --list-feeds
   ```

3. Process 3 articles from all feeds:
   ```bash
   python main.py --limit 3
   ```

4. Process articles without rewriting:
   ```bash
   python main.py --skip-rewrite
   ```

5. Force refresh and process 5 articles:
   ```bash
   python main.py --limit 5 --force-refresh
   ```

### Feed Management

You can manage feeds in three ways:

1. Through the command line:
   ```bash
   # Add a feed with a name
   python main.py --add-feed "https://example.com/feed/" --feed-name "Example News"
   
   # List all feeds (including inactive ones)
   python main.py --list-feeds --include-inactive
   
   # Remove a feed
   python main.py --remove-feed 1
   
   # Toggle a feed
   python main.py --toggle-feed 1
   ```

2. Through a CSV file:
   ```bash
   # Import feeds from a CSV file
   python main.py --import-csv feeds.csv
   ```
   
   The CSV file should have the following format:
   ```csv
   url,name
   https://example.com/feed/,Example News
   https://another-site.com/feed/,Another Site
   ```
   
   Note: The `name` column is optional. If not provided, the URL will be used as the name.

3. Through the configuration file:
   ```json
   {
       "monitor": {
           "rss_feeds": [
               "https://example.com/feed/",
               "https://another-site.com/feed/"
           ]
       }
   }
   ```

### Feed Listing

The `--list-feeds` command provides a detailed view of all configured feeds:

```bash
python main.py --list-feeds
```

Output example:
```
Configured Feeds:
--------------------------------------------------------------------------------
ID   Name                           URL                                      Status   Paywall Hits
--------------------------------------------------------------------------------
1    Example News                   https://example.com/feed/              Active    0
2    Another Site                   https://another-site.com/feed/         Active    3
3    Paywalled Site                 https://paywalled-site.com/feed/       Paywalled 5
--------------------------------------------------------------------------------
```

Status indicators:
- `Active`: Feed is enabled and being monitored
- `Inactive`: Feed is disabled but kept in the database
- `Paywalled`: Feed has been marked as paywalled and will be skipped

### Feed Statistics

To view detailed statistics about your feeds:

```bash
python main.py --show-stats
```

Output example:
```
Feed Statistics:
--------------------------------------------------------------------------------
Total feeds: 10
Active feeds: 8
Paywalled feeds: 2
Total paywall hits: 15
Total articles processed: 150
--------------------------------------------------------------------------------
```

### Programmatic Usage

You can also use the RSSMonitor class directly in your Python code:

```python
from rss_monitor import RSSMonitor

# Initialize the monitor
monitor = RSSMonitor()

# Add a new feed
monitor.add_feed("https://example.com/feed/")

# Get feed statistics
stats = monitor.get_feed_stats()

# Process articles
entries = monitor.get_entries(force_refresh=True)
```

### Paywall Handling

The system automatically detects paywalled content and handles it appropriately:

1. When a paywall is detected:
   - The hit is recorded in the database
   - The feed's paywall hit count is updated
   - If a feed hits 5 paywalls within 7 days:
     - You'll be prompted to:
       1. Keep monitoring the feed
       2. Mark it as paywalled (will be skipped in future)
       3. Remove it completely

2. To check paywall statistics:
   ```bash
   python main.py --show-stats
   ```

## Database Schema

### Feeds Table
- `id`: Primary key
- `url`: Feed URL
- `title`: Feed title
- `is_active`: Whether the feed is active
- `is_paywalled`: Whether the feed is paywalled
- `last_fetch`: Last fetch timestamp
- `created_at`: Creation timestamp
- `last_checked`: Last check timestamp
- `paywall_hits`: Number of paywall hits
- `last_paywall_hit`: Last paywall hit timestamp

### Processed Entries Table
- `id`: Primary key
- `feed_id`: Foreign key to feeds
- `entry_id`: Unique entry identifier
- `title`: Entry title
- `link`: Entry URL
- `published_at`: Publication timestamp
- `processed_at`: Processing timestamp

### Paywall Hits Table
- `id`: Primary key
- `feed_id`: Foreign key to feeds
- `article_url`: Paywalled article URL
- `hit_date`: Hit timestamp

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- LM Studio for providing local AI capabilities
- OpenAI for API access
- WordPress for REST API
- All contributors and users of this project 