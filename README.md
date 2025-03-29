# DataFloren ReeRiter

A Python-based RSS feed monitoring and article rewriting system that uses AI to process and republish content.

## Features

- RSS feed monitoring with configurable check intervals
- AI-powered article rewriting using LMStudio
- WordPress integration for content publishing
- Tag management system with AI-generated tags
- Paywall detection and handling
- Feed management system with import/export capabilities
- Database-backed storage for feeds and articles
- Configurable settings via JSON

## Prerequisites

- Python 3.8+
- LMStudio running locally (for AI processing)
- WordPress site with REST API access
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/DataFloren_ReeRiter.git
cd DataFloren_ReeRiter
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Configure the application:
   - Copy `config.json.example` to `config.json`
   - Update the configuration with your settings:
     - LMStudio API URL and model
     - WordPress site URL and credentials
     - RSS feed check interval
     - Other preferences

## Usage

### Basic Usage

Run the script to start monitoring RSS feeds:
```bash
python main.py
```

### Feed Management

Add a new RSS feed:
```bash
python main.py --add-feed "https://example.com/feed"
```

Remove a feed by ID:
```bash
python main.py --remove-feed 1
```

List all configured feeds:
```bash
python main.py --list-feeds
```

Import feeds from CSV:
```bash
python main.py --import-feeds feeds.csv
```

Export feeds to CSV:
```bash
python main.py --export-feeds feeds_backup.csv
```

### CSV Format for Feed Import/Export

The CSV file should have the following columns:
- `url`: The RSS feed URL
- `name`: A display name for the feed (optional)

Example:
```csv
url,name
https://example.com/feed,Example Feed
https://another.com/feed,Another Feed
```

### Additional Options

- `--limit N`: Process only N articles
- `--skip-rewrite`: Skip article rewriting
- `--skip-wordpress`: Skip WordPress posting

## Configuration

Edit `config.json` to configure:

- LMStudio settings (URL, model)
- WordPress credentials
- RSS feed check interval
- Tag generation settings
- Other preferences

## Database

The application uses SQLite for storage (`feeds.db`). The database includes tables for:
- RSS feeds
- Articles
- Processed entries
- Tags
- Article-tag relationships
- Paywall tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 