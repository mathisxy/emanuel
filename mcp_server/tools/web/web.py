import logging
from typing import Annotated, List

from mcp_server.mcp_instance import mcp
from mcp_server.tools.web.searxng import web_search


@mcp.tool(tags={"Web"})
def search_web(query: str, news : Annotated[bool, "Explizit nach aktuellen Nachrichten suchen"] = False, result_count: int = 5) -> List:
    """Für Informationen aus dem Web, z.B. über aktuelle Themen."""

    results = web_search(query, news)

    results_list = [
        {"title": r.title, "url": r.url, "content": r.content}
        for r in results.results[:result_count]
    ]

    logging.info(results_list)

    return results_list