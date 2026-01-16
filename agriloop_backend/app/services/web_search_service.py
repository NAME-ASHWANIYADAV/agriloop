from ddgs import DDGS
from typing import List, Dict
import asyncio

class WebSearchService:
    def __init__(self):
        pass

    def _perform_sync_search(self, query: str, max_results: int) -> str:
        """Synchronous wrapper for the search call."""
        with DDGS() as ddgs:
            results: List[Dict[str, str]] = list(ddgs.text(keywords=query, region='in-en', max_results=max_results))
            if not results:
                return f"No relevant information found online for query: '{query}'."
            snippets = [f"Title: {r.get('title')}\nSnippet: {r.get('body')}\nURL: {r.get('href')}\n---" for r in results]
            return "\n\n".join(snippets)

    async def search_market_data(self, queries: List[str], max_results_per_query: int = 2) -> str:
        """
        Performs asynchronous web searches for a list of queries and combines the results.
        """
        tasks = [
            asyncio.to_thread(self._perform_sync_search, query, max_results_per_query)
            for query in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        combined_results = ""
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                combined_results += f"Error during search for query '{queries[i]}': {result}\n\n"
            else:
                combined_results += f"Results for query: '{queries[i]}'\n---\n{result}\n\n"
        
        return combined_results.strip()

def get_web_search_service():
    return WebSearchService()

