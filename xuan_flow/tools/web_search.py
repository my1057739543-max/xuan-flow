"""Web search tool using Tavily API."""

import os

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for information using Tavily.

    Args:
        query: The search query string.

    Returns:
        Search results as formatted text.
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        return "Error: tavily-python is not installed. Run: pip install tavily-python"

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY environment variable is not set."

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=5)

        results = []
        for i, result in enumerate(response.get("results", []), 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "No content")
            results.append(f"[{i}] {title}\n    URL: {url}\n    {content}")

        return "\n\n".join(results) if results else "No results found."

    except Exception as e:
        return f"Search error: {e}"
