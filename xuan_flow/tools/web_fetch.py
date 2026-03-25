"""Web content fetching tool for deep research."""

import logging
from typing import Optional
from langchain_core.tools import tool
from langchain_community.document_loaders import WebBaseLoader

logger = logging.getLogger(__name__)

@tool
def web_fetch_content(url: str) -> str:
    """Fetch and extract the full text content from a web URL.
    
    Use this when you need the detailed content of a specific page 
    beyond the short snippet provided by web_search.
    
    Args:
        url: The URL of the web page to fetch.
        
    Returns:
        The text content of the page, cleaned and formatted.
    """
    try:
        logger.info(f"Fetching content from: {url}")
        loader = WebBaseLoader(url)
        docs = loader.load()
        
        if not docs:
            return f"Error: No content found at {url}"
            
        # Combine all parts and clean up
        content = "\n\n".join([doc.page_content for doc in docs])
        
        # Simple cleanup of excessive whitespace
        import re
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        # Limit length to prevent context window overflow
        char_limit = 15000
        if len(content) > char_limit:
            content = content[:char_limit] + "\n\n... [Content Truncated for Length] ..."
            
        return content
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return f"Error fetching content: {e}"
