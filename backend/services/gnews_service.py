import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class GNewsService:
    """Client for the GNews API (https://gnews.io/).

    Provides a news-article search tool for the agent. The API key is supplied
    from the environment and is never logged, returned from an endpoint, or
    included in error messages.
    """

    BASE_URL = "https://gnews.io/api/v4"
    MAX_QUERY_LENGTH = 500

    def __init__(self, config: dict[str, Any] | None = None, api_key: str = ""):
        config = config or {}
        self.enabled = bool(config.get("enabled", False))
        self.api_key = api_key or ""
        self.max_results = int(config.get("max_results", 5))
        self.language = str(config.get("language", "en"))
        self.country = str(config.get("country", "us"))
        self.timeout_seconds = int(config.get("timeout_seconds", 10))
        logger.info(
            "GNews service initialized (enabled=%s, max_results=%s, language=%s, country=%s)",
            self.enabled,
            self.max_results,
            self.language,
            self.country,
        )

    def is_available(self) -> bool:
        """Return True when the tool is enabled and an API key is configured."""
        return bool(self.enabled and self.api_key)

    def search(self, query: str) -> dict[str, Any]:
        """Search recent news articles for the given query.

        Calls GET /search?q=<query>&max=<n>&lang=<l>&country=<c>&token=<key>.

        Returns:
            {
                'articles': [
                    {
                        'title': str,
                        'description': str,
                        'url': str,
                        'source': str,
                        'published_at': str,   # ISO 8601
                    }
                ],
                'total_articles': int,
            }

        Raises:
            ValueError: if query is empty, whitespace-only, or too long.
            RuntimeError: if the tool is unavailable or the API/network fails.
        """
        if not self.is_available():
            raise RuntimeError("GNews is not available (disabled or missing API key)")

        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        query = query.strip()
        if len(query) > self.MAX_QUERY_LENGTH:
            raise ValueError(f"query must be at most {self.MAX_QUERY_LENGTH} characters")

        params = {
            "q": query,
            "max": self.max_results,
            "lang": self.language,
            "country": self.country,
            "token": self.api_key,
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"GNews request timed out after {self.timeout_seconds}s") from e
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError("Failed to connect to GNews") from e
        except requests.exceptions.RequestException as e:
            # Avoid leaking the API key that may appear in the request URL.
            raise RuntimeError("GNews request failed") from e

        if response.status_code != 200:
            # Do not surface the response body or API key.
            raise RuntimeError(f"GNews API returned HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as e:
            raise RuntimeError("GNews returned an invalid JSON response") from e

        articles = []
        for item in data.get("articles", []) or []:
            source = item.get("source") or {}
            articles.append(
                {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "url": item.get("url", ""),
                    "source": source.get("name", "") if isinstance(source, dict) else "",
                    "published_at": item.get("publishedAt", ""),
                }
            )

        return {
            "articles": articles,
            "total_articles": int(data.get("totalArticles", len(articles))),
        }
