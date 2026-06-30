import logging
import re
from typing import Optional

from models.web_search import WebSearchResult

logger = logging.getLogger(__name__)

# Strip control characters but keep normal whitespace.
_CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_MAX_QUERY_LEN = 200
_MAX_SNIPPET_LEN = 300
_MAX_TOTAL_CONTEXT_LEN = 3000


def _sanitize_query(query: str) -> str:
    """Strip control characters and enforce length limit."""
    cleaned = _CONTROL_CHAR_RE.sub('', query).strip()
    return cleaned[:_MAX_QUERY_LEN]


def format_search_context(results: list[WebSearchResult]) -> str:
    """Format search results into a prompt-injectable context block."""
    if not results:
        return ''

    lines = [
        '[Web Search Results]',
        'The following are recent web search results relevant to the user\'s question.',
        'Use these to inform your response. Cite sources using [Source Title](URL) format.',
        '',
    ]

    for i, r in enumerate(results, 1):
        snippet = (r.snippet or '')[:_MAX_SNIPPET_LEN]
        lines.append(f'{i}. **{r.title}**')
        lines.append(f'   {snippet}')
        lines.append(f'   Source: {r.url}')
        lines.append('')

    context = '\n'.join(lines).rstrip()
    if len(context) > _MAX_TOTAL_CONTEXT_LEN:
        context = context[:_MAX_TOTAL_CONTEXT_LEN]
    return context + '\n\n---'


class WebSearchService:
    """Performs web searches via DuckDuckGo."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check whether the duckduckgo-search package is importable."""
        if self._available is None:
            try:
                import duckduckgo_search  # noqa: F401
                self._available = True
            except ImportError:
                logger.warning('duckduckgo-search package not installed — web search disabled')
                self._available = False
        return self._available

    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """Search the web and return structured results.

        Returns an empty list on any failure — search is best-effort.
        """
        if not self.is_available():
            return []

        sanitized = _sanitize_query(query)
        if not sanitized:
            return []

        try:
            from duckduckgo_search import DDGS

            with DDGS(timeout=self.timeout) as ddgs:
                raw = ddgs.text(sanitized, max_results=max_results)

            results: list[WebSearchResult] = []
            for item in raw or []:
                title = str(item.get('title', '')).strip()
                url = str(item.get('href', '')).strip()
                snippet = str(item.get('body', '')).strip()
                if title and url:
                    results.append(WebSearchResult(
                        title=title,
                        url=url,
                        snippet=snippet[:_MAX_SNIPPET_LEN],
                    ))

            logger.info('Web search query=%r result_count=%d', sanitized[:80], len(results))
            return results

        except Exception:
            logger.warning('Web search failed for query=%r', sanitized[:80], exc_info=True)
            return []
