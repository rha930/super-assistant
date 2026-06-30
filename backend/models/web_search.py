from dataclasses import dataclass


@dataclass
class WebSearchResult:
    """A single web search result."""

    title: str
    url: str
    snippet: str
