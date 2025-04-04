import json
import os
from typing import Dict, Any, Optional
import requests
from getpass import getpass
from logger import setup_logger

logger = setup_logger('setup_wizard')

class SetupWizard:
    """Interactive setup wizard for configuring the application."""
    
    def __init__(self):
        self.config: Dict[str, Any] = {
            "monitor": {
                "rss_feeds": [],
                "check_interval": 3600,
                "max_entries": 100
            },
            "wordpress": {
                "site_url": "",
                "username": "",
                "password": "",
                "api_version": "wp/v2"
            },
            "ai_provider": {
                "type": "",  # lm_studio, openai, anthropic, ollama
                "settings": {}
            }
        }
    
    def _test_wordpress_connection(self, site_url: str, username: str, password: str) -> bool:
        """Test WordPress connection with provided credentials."""
        try:
            response = requests.get(
                f"{site_url}/wp-json/wp/v2/posts",
                auth=(username, password),
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"WordPress connection test failed: {e}")
            return False
    
    def _test_ai_provider(self, provider_type: str, settings: Dict[str, Any]) -> bool:
        """Test connection to the selected AI provider."""
        try:
            if provider_type == "lm_studio":
                response = requests.get(f"{settings['api_url']}/models", timeout=10)
                return response.status_code == 200
            elif provider_type == "openai":
                import openai
                openai.api_key = settings['api_key']
                response = openai.Model.list()
                return bool(response)
            elif provider_type == "anthropic":
                import anthropic
                client = anthropic.Client(api_key=settings['api_key'])
                response = client.messages.create(
                    model="claude-3-opus-20240229",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                return bool(response)
            elif provider_type == "ollama":
                url = settings.get('api_url', 'http://localhost:11434')
                response = requests.get(f"{url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"AI provider connection test failed: {e}")
            return False
    
    def setup_wordpress(self):
        """Configure WordPress settings."""
        print("\n=== WordPress Configuration ===")
        while True:
            site_url = input("Enter WordPress site URL (e.g., https://your-site.com): ").strip()
            username = input("Enter WordPress username: ").strip()
            password = getpass("Enter WordPress application password: ").strip()
            
            print("\nTesting WordPress connection...")
            if self._test_wordpress_connection(site_url, username, password):
                print("WordPress connection successful!")
                self.config["wordpress"].update({
                    "site_url": site_url,
                    "username": username,
                    "password": password
                })
                break
            else:
                print("Failed to connect to WordPress. Please check your credentials.")
                if input("Try again? (y/n): ").lower() != 'y':
                    break
    
    def setup_ai_provider(self):
        """Configure AI provider settings."""
        print("\n=== AI Provider Configuration ===")
        providers = {
            "1": "lm_studio",
            "2": "openai",
            "3": "anthropic",
            "4": "ollama"
        }
        
        while True:
            print("\nAvailable AI Providers:")
            print("1. LMStudio (local)")
            print("2. OpenAI")
            print("3. Anthropic")
            print("4. Ollama")
            
            choice = input("\nSelect AI provider (1-4): ").strip()
            if choice not in providers:
                print("Invalid choice. Please try again.")
                continue
            
            provider_type = providers[choice]
            settings = {}
            
            if provider_type == "lm_studio":
                settings["api_url"] = input("Enter LMStudio API URL (default: http://localhost:1234/v1): ").strip() or "http://localhost:1234/v1"
                settings["model"] = input("Enter model name (default: mistral-7b-instruct-v0.3): ").strip() or "mistral-7b-instruct-v0.3"
            
            elif provider_type in ["openai", "anthropic"]:
                settings["api_key"] = getpass(f"Enter {provider_type} API key: ").strip()
                if provider_type == "openai":
                    settings["model"] = input("Enter model name (default: gpt-3.5-turbo): ").strip() or "gpt-3.5-turbo"
                else:
                    settings["model"] = input("Enter model name (default: claude-3-opus-20240229): ").strip() or "claude-3-opus-20240229"
            
            elif provider_type == "ollama":
                settings["api_url"] = input("Enter Ollama API URL (default: http://localhost:11434): ").strip() or "http://localhost:11434"
                settings["model"] = input("Enter model name (default: mistral): ").strip() or "mistral"
            
            print(f"\nTesting {provider_type} connection...")
            if self._test_ai_provider(provider_type, settings):
                print(f"{provider_type} connection successful!")
                self.config["ai_provider"] = {
                    "type": provider_type,
                    "settings": settings
                }
                break
            else:
                print(f"Failed to connect to {provider_type}.")
                if input("Try again? (y/n): ").lower() != 'y':
                    break
    
    def setup_rss_feeds(self):
        """Configure RSS feed settings."""
        print("\n=== RSS Feed Configuration ===")
        while True:
            feed_url = input("\nEnter RSS feed URL (or press Enter to finish): ").strip()
            if not feed_url:
                break
            
            try:
                import feedparser
                feed = feedparser.parse(feed_url)
                if feed.bozo:
                    print(f"Warning: Feed may be invalid - {feed.bozo_exception}")
                    if input("Add anyway? (y/n): ").lower() != 'y':
                        continue
                self.config["monitor"]["rss_feeds"].append(feed_url)
                print(f"Added feed: {feed_url}")
            except Exception as e:
                print(f"Error validating feed: {e}")
                if input("Add anyway? (y/n): ").lower() != 'y':
                    continue
    
    def run(self):
        """Run the setup wizard."""
        print("Welcome to the DataFloren ReeRiter Setup Wizard!")
        print("This wizard will help you configure the application.")
        
        # Load existing config if available
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print("\nLoaded existing configuration.")
            except Exception as e:
                logger.error(f"Error loading existing config: {e}")
        
        # Run setup steps
        self.setup_wordpress()
        self.setup_ai_provider()
        self.setup_rss_feeds()
        
        # Save configuration
        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            print("\nConfiguration saved successfully!")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            print(f"\nError saving configuration: {e}")

def run_setup():
    """Run the setup wizard."""
    wizard = SetupWizard()
    wizard.run()

if __name__ == "__main__":
    run_setup() 