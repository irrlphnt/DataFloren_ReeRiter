from bs4 import BeautifulSoup
from urllib.parse import urljoin

def HeadlineGrabber(html_content):
    """
    Extracts all headlines (h1 tags) from the given HTML content.

    Args:
        html_content (str): The HTML content of a webpage.

    Returns:
        list: A list of strings containing the text of all h1 tags found in the HTML.
    """
    # Parse HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all h1 tags in the parsed HTML and store their text
    headlines = []
    for tag in soup.find_all('h1'):
        headlines.append(tag.text.strip())  # Extract and store text from h1 tags

    return headlines

def ArticleScraper(html_content, base_url):
    """
    Extracts comprehensive article data from the given HTML content.

    Args:
        html_content (str): The HTML content of a webpage.
        base_url (str): The base URL of the webpage for resolving relative URLs.

    Returns:
        dict: A dictionary containing the article data:
            - title: The article title (string).
            - paragraphs: List of paragraphs in the article body.
            - author: The article author if available (string or None).
            - date: The publication date if available (string or None).
            - images: List of image URLs found in the article.
            - tags: List of tags associated with the article.
    """
    # Parse HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Initialize article data dictionary
    article_data = {
        'title': None,
        'paragraphs': [],
        'author': None,
        'date': None,
        'images': [],
        'tags': []
    }
    
    # Extract article title (h1)
    title_tag = soup.find('h1')
    if title_tag:
        article_data['title'] = title_tag.text.strip()
    
    # Extract paragraphs from the main content
    # This is a simple approach; for better results, you might want to
    # focus on specific content containers like 'article', 'main', etc.
    main_content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
    if main_content:
        for p in main_content.find_all('p'):
            if p.text.strip():  # Only add non-empty paragraphs
                article_data['paragraphs'].append(p.text.strip())
    else:
        # If no specific content container is found, try to get all paragraphs
        for p in soup.find_all('p'):
            if p.text.strip():  # Only add non-empty paragraphs
                article_data['paragraphs'].append(p.text.strip())
    
    # Extract author (common patterns, but may need adjustment for specific sites)
    author_elem = soup.find('meta', attrs={'name': 'author'}) or \
                 soup.find('a', attrs={'rel': 'author'}) or \
                 soup.find('span', class_='author')
    if author_elem:
        if author_elem.name == 'meta':
            article_data['author'] = author_elem.get('content', '')
        else:
            article_data['author'] = author_elem.text.strip()
    
    # Extract publication date (common patterns, but may need adjustment)
    date_elem = soup.find('meta', attrs={'property': 'article:published_time'}) or \
               soup.find('time') or \
               soup.find('span', class_='date')
    if date_elem:
        if date_elem.name == 'meta':
            article_data['date'] = date_elem.get('content', '')
        elif date_elem.get('datetime'):
            article_data['date'] = date_elem.get('datetime', '')
        else:
            article_data['date'] = date_elem.text.strip()
    
    # Extract images
    for img in soup.find_all('img'):
        if img.get('src'):
            # Handle relative URLs
            img_url = urljoin(base_url, img.get('src'))
            article_data['images'].append(img_url)
    
    # Extract tags
    # Look for tags in various common locations
    tag_elements = (
        soup.find_all('a', class_='tag') or  # Common tag class
        soup.find_all('a', rel='tag') or     # WordPress-style tags
        soup.find_all('span', class_='tag') or
        soup.find_all('div', class_='tags')
    )
    
    if tag_elements:
        for tag_elem in tag_elements:
            tag_text = tag_elem.text.strip()
            if tag_text and tag_text not in article_data['tags']:
                article_data['tags'].append(tag_text)
    
    # If no tags found in standard locations, try to extract from URL
    if not article_data['tags'] and '/tag/' in base_url:
        tag_from_url = base_url.split('/tag/')[-1].split('/')[0].replace('-', ' ').title()
        if tag_from_url and tag_from_url not in article_data['tags']:
            article_data['tags'].append(tag_from_url)
    
    return article_data

# Example usage and testing:
if __name__ == "__main__":
    # Example HTML content for testing
    html_content = """
    <html>
        <head>
            <title>Test Page</title>
            <meta name="author" content="John Doe">
            <meta property="article:published_time" content="2025-03-27T12:00:00Z">
        </head>
        <body>
            <article>
                <h1>Headline 1</h1>
                <p>First paragraph of the article.</p>
                <p>Second paragraph with some more content.</p>
                <img src="/images/test.jpg" alt="Test Image">
            </article>
        </body>
    </html>
    """

    # Call the HeadlineGrabber function with the example HTML content
    headlines = HeadlineGrabber(html_content)
    print("Extracted Headlines:", headlines)

    # Call the ArticleScraper function with the example HTML content
    article_data = ArticleScraper(html_content, "https://example.com")
    print("\nArticle Data:")
    print(f"  Title: {article_data['title']}")
    print(f"  Author: {article_data['author']}")
    print(f"  Date: {article_data['date']}")
    print(f"  Images: {article_data['images']}")
    print(f"  Paragraphs: {len(article_data['paragraphs'])} found")
    for i, p in enumerate(article_data['paragraphs'], 1):
        print(f"    {i}. {p}")