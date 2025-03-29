# DataFloren Article Monitor & Rewriter

A Python-based tool for monitoring, scraping, and rewriting articles from various sources, with support for WordPress integration and AI-powered content generation.

## Features

- **Multi-source Article Monitoring**
  - Website scraping with Selenium
  - RSS feed monitoring
  - Support for multiple feed sources
  - Automatic paywall detection

- **AI-Powered Content Generation**
  - Article rewriting using LM Studio
  - Tag generation
  - Thematic prompt support
  - Caching for improved performance

- **WordPress Integration**
  - Automatic article posting
  - Tag management
  - AI disclosure support
  - Draft/publish status control

- **Robust Error Handling**
  - Automatic recovery from failures
  - State tracking and persistence
  - Detailed logging
  - Cache management

## Project Structure

```
DataFloren_ReeRiter/
├── cache/                  # Cache directory for various features
│   ├── rewriter_cache.json # Cached rewritten articles
│   └── ...                # Other cache files
├── main.py                # Main application entry point
├── lm_studio.py           # LM Studio integration for AI features
├── rss_monitor.py         # RSS feed monitoring and management
├── article_scraper.py     # Article content extraction
├── wordpress_poster.py    # WordPress integration
├── tag_manager.py         # Tag generation and management
├── database.py            # Database operations
├── logger.py              # Logging configuration
├── config.json            # Application configuration
└── requirements.txt       # Python dependencies
```

## Configuration

The application is configured through `config.json`:

```json
{
    "monitor": {
        "website_url": "https://example.com",
        "link_limit": 5,
        "use_rss": true,
        "rss_feeds": ["https://example.com/feed"],
        "rss_max_entries": 10
    },
    "lm_studio": {
        "use_lm_studio": true,
        "url": "http://localhost:1234/v1",
        "model": "mistral-7b-instruct-v0.3"
    },
    "wordpress": {
        "url": "https://example.com",
        "username": "admin",
        "password": "password",
        "default_status": "draft"
    },
    "general": {
        "auto_rewrite": true,
        "auto_post": false,
        "log_level": "INFO"
    }
}
```

## Usage

### Basic Usage

```bash
python main.py
```

### Command Line Options

- `--limit N`: Process only N articles
- `--skip-rewrite`: Skip article rewriting
- `--skip-wordpress`: Skip WordPress posting
- `--add-feed URL`: Add a new RSS feed
- `--remove-feed URL`: Remove an RSS feed
- `--list-feeds`: List all configured feeds
- `--add-thematic-prompt --tag-name TAG --prompt PROMPT`: Add a thematic prompt for tag generation

### Running with LM Studio

```bash
# Windows
run_with_lm_studio.bat

# Linux/Mac
./run_with_lm_studio.sh
```

## Dependencies

- Python 3.8+
- Selenium WebDriver
- BeautifulSoup4
- Requests
- Chrome/Chromium browser (for web scraping)

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure `config.json` with your settings
4. Start LM Studio server if using AI features
5. Run the application

## Cache Management

The application uses a `cache` directory to store various feature-specific caches:

- `rewriter_cache.json`: Stores rewritten articles to avoid reprocessing
- Additional cache files may be added for other features

## Logging

Logs are stored in feature-specific log files:
- `main.log`: Main application logs
- `lm_studio.log`: AI-related operations
- `tag_manager.log`: Tag generation logs

## Error Handling

The application includes robust error handling:
- Automatic recovery from failures
- State persistence for long-running operations
- Detailed error logging
- Screenshot capture on web scraping failures

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 