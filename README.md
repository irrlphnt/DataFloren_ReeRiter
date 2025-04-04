# DataFloren ReeRiter

A Python-based article monitoring and rewriting system that processes RSS feeds, rewrites content using LMStudio, and publishes to WordPress.

## Core Features

- **RSS Feed Monitoring**: Continuously monitors multiple RSS feeds for new articles
- **Content Processing**: Extracts and processes article content from various sources
- **AI-Powered Rewriting**: Uses LMStudio to rewrite articles while maintaining original meaning
- **WordPress Integration**: Automatically publishes rewritten content to WordPress
- **Database Management**: Tracks processed articles and feed status in SQLite database
- **Tag Management**: Automatically generates and manages article tags
- **Error Handling**: Robust error handling and logging system

## Recent Improvements

- Enhanced article processing with improved content extraction
- Better error handling and logging
- Optimized database operations
- Improved WordPress post creation with AI metadata
- Streamlined configuration management

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/DataFloren_ReeRiter.git
cd DataFloren_ReeRiter
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the application:
- Copy `config.example.json` to `config.json`
- Update the configuration with your WordPress and LMStudio settings

5. Initialize the database:
```bash
python main.py
```

## Usage

Run the main script:
```bash
python main.py
```

The script will:
1. Monitor configured RSS feeds
2. Process new articles
3. Rewrite content using LMStudio
4. Publish to WordPress
5. Update the database with processed entries

## Configuration

Edit `config.json` to customize:
- WordPress API settings
- LMStudio endpoint
- RSS feed URLs
- Processing parameters
- Logging levels

## Project Structure

- `main.py`: Main application entry point
- `database.py`: Database management and operations
- `wordpress_poster.py`: WordPress API integration
- `lm_studio.py`: LMStudio API integration
- `rss_monitor.py`: RSS feed monitoring
- `tag_manager.py`: Tag generation and management
- `logger.py`: Logging configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 