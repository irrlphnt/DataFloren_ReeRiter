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
- **Interactive Setup**: User-friendly setup wizard for configuration

## Recent Improvements

- Enhanced article processing with improved content extraction
- Better error handling and logging
- Optimized database operations
- Improved WordPress post creation with AI metadata
- Streamlined configuration management
- Added interactive setup wizard for easy configuration

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

4. Run the setup wizard:
```bash
python main.py --setup
```

The setup wizard will guide you through:
- WordPress configuration
- AI provider selection and setup
- RSS feed configuration
- General application settings

Alternatively, you can manually configure the application:
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

To reconfigure the application at any time, run:
```bash
python main.py --setup
```

## Configuration

The application can be configured in two ways:
1. **Interactive Setup Wizard**: Run `python main.py --setup` for a guided configuration process
2. **Manual Configuration**: Edit `config.json` to customize:
   - WordPress API settings
   - AI provider settings (LMStudio, OpenAI, Anthropic, Ollama)
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
- `setup_wizard.py`: Interactive configuration setup

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 