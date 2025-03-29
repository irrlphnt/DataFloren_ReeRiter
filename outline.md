# Project Title: Article Monitor & Rewriter

## Table of Contents
- [Project Overview](#project-overview)
- [Features](#features)
- [Technologies & Tools](#technologies--tools)
- [Timeline & Milestones](#timeline--milestones)
- [Tasks](#tasks)
- [Current Status](#current-status)

## Project Overview
- **Purpose:** Develop a program that monitors a specific website for new links to articles on other sites. When it detects a new link, the program will scrape the source article, use AI to rewrite it, and then post the rewritten version as a WordPress post.
- **Audience:** Blog owners or content creators who want to automate the process of finding, rewriting, and publishing articles from external sources without manually visiting each site or writing the content themselves.
- **Requirements:**
  - Web scraping functionality to fetch articles from external sites.
  - AI-powered article rewriter to generate unique and coherent content.
  - WordPress integration for posting rewritten articles automatically.
  - Scheduling and automation capabilities to run the process at regular intervals.
  - Basic user interface for configuring settings, monitoring progress, and viewing reports.

## Features
- List the main features you want to implement in your project. For each feature, include a brief description and any relevant notes or dependencies.

1. **Website Monitor** ✅
   - Description: Periodically check a specified website for new links to external articles.
   - Notes/Dependencies:
     - Requires web scraping libraries (e.g., BeautifulSoup, Scrapy) and a way to parse HTML content.
     - Needs a scheduling mechanism to run the monitor at regular intervals.

2. **Article Scraper** ✅
   - Description: Fetch the source article from the detected link and extract relevant content (text, images, etc.).
   - Notes/Dependencies:
     - Depends on Website Monitor feature.
     - Requires web scraping libraries and proper handling of API requests and rate limits.

3. **AI Article Rewriter** ✅
   - Description: Use AI to rewrite the scraped article, maintaining its original meaning but with unique phrasing and structure.
   - Notes/Dependencies:
     - Depends on Article Scraper feature.
     - Requires an AI service or model for text generation and rewriting (e.g., transformers, Hugging Face models, or custom APIs).
     - May need additional functionality to preserve proper formatting, citations, and image placement.

4. **WordPress Integration** 🔲
   - Description: Automatically post the rewritten article as a new WordPress post with appropriate tags, categories, and other metadata.
   - Notes/Dependencies:
     - Requires the WordPress REST API or other methods for interacting with WordPress sites.
     - May need additional functionality to handle image uploads, featured images, and other media content.

5. **User Interface** 🔲
   - Description: Provide a user-friendly interface for configuring project settings, monitoring progress, and viewing reports on processed articles.
   - Notes/Dependencies:
     - Can be built using web frameworks like Flask or Django.
     - May require integration with task scheduling libraries (e.g., cron jobs, Celery) to manage automated processes.

6. **Reporting & Notifications** 🔲
   - Description: Generate reports on the number of articles processed, successful posts, and any errors encountered during the process.
   - Notes/Dependencies:
     - Depends on other features for data collection.
     - May require integration with email services or messaging platforms for sending notifications.

## Technologies & Tools
- Programming Language: Python (3.8+)
- Web Scraping Libraries: BeautifulSoup, Selenium (✅ Implemented)
- AI Article Rewriter: OpenAI API or LM Studio local server (✅ Implemented)
- WordPress Integration: WordPress REST API (✅ Implemented)
- User Interface: Flask or Django web frameworks
- Scheduling & Automation: Celery task queue, cron jobs
- Reporting & Notifications: Email services (e.g., SendGrid, Mailgun) or messaging platforms

## Timeline & Milestones
| Task/Feature | Estimated Duration (days) | Start Date | End Date | Dependencies | Status |
|---|---|---|---|---|---|
| Milestone 1: Project Setup & Planning | 3 | 2022-04-15 | 2022-04-17 | - | ✅ Completed |
| Milestone 2: Website Monitor & Article Scraper | 7 | 2022-04-18 | 2022-04-24 | Depends on Milestone 1 | ✅ Completed |
| Milestone 3: AI Article Rewriter | 5 | 2022-04-25 | 2022-04-29 | Depends on Milestone 2 | ✅ Completed |
| Milestone 4: WordPress Integration & Posting | 7 | 2022-04-30 | 2022-05-06 | Depends on Milestones 2 and 3 | ✅ Completed |
| Milestone 5: User Interface & Reporting | 8 | 2022-05-07 | 2022-05-14 | Depends on all previous milestones | 🔲 Not Started |
| Milestone 6: Testing, Documentation & Deployment | 3 | 2022-05-15 | 2022-05-17 | Depends on all previous milestones | 🔲 Not Started |

## Tasks
### Completed Tasks
- ✅ Set up project environment with necessary dependencies
- ✅ Implement website monitoring with Selenium and BeautifulSoup
- ✅ Implement article scraping functionality to extract title, content, author, date, and images
- ✅ Add logging and error handling for robust operation
- ✅ Implement JSON export for scraped article data
- ✅ Research and select appropriate AI services for article rewriting
- ✅ Implement article rewriter module to generate new content using OpenAI
- ✅ Add option to use local LM Studio server instead of OpenAI API
- ✅ Add functionality to maintain article formatting and structure
- ✅ Implement caching to avoid reprocessing the same articles
- ✅ Implement WordPress integration for posting articles
- ✅ Add functionality for image uploading to WordPress

### Current Tasks (User Interface & Reporting)
- 🔲 Create a basic web interface for monitoring and configuration
- 🔲 Add scheduling capabilities for automated monitoring
- 🔲 Implement reporting and notification features

### Upcoming Tasks
- 🔲 Comprehensive testing with various website sources
- 🔲 Create user documentation
- 🔲 Package for deployment

## Current Status
As of March 28, 2025, the project has successfully implemented the core functionalities:

1. Website Monitor: Monitors a specified website (datafloren.net) for external links
2. Article Scraper: Extracts detailed article data including title, content, author, date, and images
3. Article Rewriter: Rewrites articles using either:
   - OpenAI API with API key
   - Local LM Studio server without requiring an API key
4. WordPress Integration: Posts rewritten articles to WordPress with options for:
   - Featured images
   - Categories
   - Post status (draft/publish)

The system also provides:
- Comprehensive logging
- Caching to avoid duplicate processing
- Command-line options for customization
- Configuration via config.json file

The next step is to implement a basic web interface for easier management and monitoring, along with scheduling capabilities for automating the entire process.