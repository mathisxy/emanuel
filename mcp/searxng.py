from pyserxng import LocalSearXNGClient
from pyserxng.models import SearchResponse


def web_search(query : str, news : bool = False) -> SearchResponse:

    # Method 1: Simple usage with context manager

    with LocalSearXNGClient("http://localhost:8888") as client:
        if client.test_connection():
            results = client.search_news(query) if news else client.search(query)
            print(f"Found {len(results.results)} results")
            return results