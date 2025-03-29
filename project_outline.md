# Article Monitor & Rewriter - Project Outline

## Project Overview

The Article Monitor & Rewriter is a comprehensive tool that monitors websites and RSS feeds for new articles, rewrites them using AI, and posts them to WordPress. The tool includes a web interface for easy management and monitoring.

## Core Components

### 1. Website Monitor
- Monitors specified websites for new articles
- Extracts external links from main content areas
- Excludes tag cloud and category pages
- Configurable link limits and monitoring intervals
- Error handling and retry mechanisms

### 2. RSS Feed Monitor
- Supports multiple RSS feed sources
- Configurable entry limits per feed
- Feed management through web interface
- Feed status tracking and statistics
- Duplicate entry prevention

### 3. Article Scraper
- Extracts article content, title, and metadata
- Handles images and media content
- Preserves original author and date information
- Supports both website and RSS content
- Error handling for malformed content

### 4. AI Article Rewriter
- Integration with LM Studio (default)
- OpenAI API support as alternative
- Configurable model selection
- Content preservation and formatting
- AI disclosure metadata
- Error handling and retry logic

### 5. WordPress Integration
- REST API integration
- Article posting with metadata
- Image upload support
- Category and tag management
- Post status control
- Error handling and recovery

### 6. Web Interface
- Dashboard with processing status
- RSS feed management
- Article monitoring and filtering
- System logs with real-time updates
- Processing control
- Error notifications

### 7. Error Handling & Recovery
- State tracking for each processing stage
- Automatic recovery from failures
- Detailed error logging
- Error notifications in web interface
- Screenshot capture on errors
- Processing state persistence

### 8. Configuration & Logging
- JSON-based configuration
- Environment variable support
- Command-line arguments
- Comprehensive logging system
- Log filtering and export
- Real-time log updates

## Data Flow

1. Monitoring Stage
   - Website scraping or RSS feed monitoring
   - Link extraction and validation
   - Duplicate checking

2. Scraping Stage
   - Article content extraction
   - Metadata collection
   - Image processing

3. Rewriting Stage
   - AI model integration
   - Content rewriting
   - AI disclosure addition

4. Posting Stage
   - WordPress API integration
   - Article posting
   - Image upload
   - Status tracking

## File Structure

```
article-monitor-rewriter/
├── main.py                 # Main script
├── article_scraper.py      # Article scraping functionality
├── article_rewriter.py     # AI rewriting functionality
├── wordpress_poster.py     # WordPress integration
├── rss_monitor.py          # RSS feed monitoring
├── config.json            # Configuration file
├── requirements.txt       # Python dependencies
├── manage.py             # Django management script
├── article_monitor_web/   # Django project settings
└── monitor/              # Django app
    ├── models.py         # Database models
    ├── views.py          # View controllers
    ├── urls.py           # URL routing
    ├── forms.py          # Form definitions
    └── templates/        # HTML templates
```

## Configuration Options

### Command Line Arguments
- `--limit`: Number of links to process
- `--use-openai`: Use OpenAI API instead of LM Studio
- `--api-key`: OpenAI API key
- `--use-rss`: Enable RSS feed monitoring
- `--rss-feeds`: List of RSS feed URLs
- `--rss-max-entries`: Maximum entries per feed
- `--skip-rewrite`: Skip article rewriting
- `--skip-wordpress`: Skip WordPress posting
- `--wp-status`: WordPress post status
- `--wp-category`: Default WordPress category

### Environment Variables
- `WP_URL`: WordPress site URL
- `WP_USERNAME`: WordPress username
- `WP_PASSWORD`: WordPress password
- `OPENAI_API_KEY`: OpenAI API key

## AI Disclosure Features

- Model information tracking
- Generation date and time
- Original source attribution
- Clear disclosure statement
- Metadata preservation
- WordPress integration

## Error Recovery Features

- Processing state tracking
- Automatic stage recovery
- Failed link handling
- Error logging and reporting
- Screenshot capture
- Web interface notifications

## Next Steps

1. Web Interface Enhancements
   - User authentication
   - Role-based access control
   - Customizable dashboard
   - Advanced filtering options

2. Processing Improvements
   - Scheduled processing
   - Batch processing optimization
   - Parallel processing support
   - Advanced error recovery

3. Integration Features
   - Additional AI model support
   - Multiple WordPress site support
   - API rate limiting
   - Webhook notifications

4. Monitoring & Analytics
   - Processing statistics
   - Performance metrics
   - Success rate tracking
   - Usage analytics

5. Documentation & Deployment
   - API documentation
   - Deployment guides
   - Docker support
   - CI/CD integration 