import structlog
from typing import Optional

from core.config import settings
from core.constants import SEARCH_TRIGGER_KEYWORDS

logger = structlog.get_logger(__name__)

_tavily_client = None


def _get_tavily():
    global _tavily_client
    if _tavily_client is not None:
        return _tavily_client

    if not settings.search_enabled:
        return None

    try:
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=settings.tavily_api_key)
        logger.info("tavily_initialized")
        return _tavily_client
    except ImportError:
        logger.warning("tavily_not_installed")
        return None
    except Exception as e:
        logger.error("tavily_init_failed", error=str(e))
        return None


def needs_web_search(message: str) -> bool:
    
    if not settings.search_enabled:
        return False

    msg_lower = message.lower()
    return any(keyword in msg_lower for keyword in SEARCH_TRIGGER_KEYWORDS)


async def search_alzheimer_research(query: str) -> str:
    
    client = _get_tavily()
    if client is None:
        return ""

    try:
        logger.info("tavily_search_start", query=query)

        results = client.search(
            f"{query} Alzheimer disease",
            max_results=3,
            search_depth="basic",
            include_domains=[
                "alzheimer.org",
                "nia.nih.gov",
                "pubmed.ncbi.nlm.nih.gov",
                "alzheimers.net",
                "alz.org",
                "who.int",
            ],
        )

        if not results.get("results"):
            logger.warning("tavily_no_results", query=query)
            return ""

        context_lines = []
        for r in results["results"]:
            title   = r.get("title", "")
            content = r.get("content", "")[:400]  
            url     = r.get("url", "")
            if title and content:
                context_lines.append(f"• [{title}]({url})\n  {content}")

        context = "\n\n".join(context_lines)
        logger.info("tavily_search_success", result_count=len(context_lines))
        return context

    except Exception as e:
        logger.error("tavily_search_failed", query=query, error=str(e))
        return ""   