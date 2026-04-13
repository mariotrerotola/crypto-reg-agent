"""Searcher Agent: discovers crypto-asset projects via CoinGecko API.

Implements the Searcher Agent from Section 3.3 of the paper, which retrieves
project metadata from external crypto-asset registries.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mas.schemas.project import ProjectMetadata
from mas.schemas.state import ComplianceState

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


class SearcherError(Exception):
    """Raised when project search fails."""


class CoinGeckoSearcher:
    """Searcher Agent: discovers crypto-asset projects via CoinGecko API.

    Uses the free CoinGecko API (no key required for basic endpoints,
    rate-limited to ~10-30 req/min).

    Args:
        api_key: Optional CoinGecko API key for higher rate limits.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["x-cg-demo-api-key"] = api_key
        self._client = httpx.Client(
            base_url=COINGECKO_BASE,
            headers=headers,
            timeout=timeout,
        )

    def search(self, query: str) -> ProjectMetadata:
        """Search for a crypto project by name or symbol.

        Two-step process:
        1. ``/search`` to find the CoinGecko coin ID
        2. ``/coins/{id}`` to fetch full metadata with URLs

        Args:
            query: Project name, symbol, or CoinGecko ID.

        Returns:
            ProjectMetadata with website URLs, whitepaper link, etc.

        Raises:
            SearcherError: If no matching project is found or API fails.
        """
        coin_id = self._resolve_coin_id(query)
        return self._fetch_coin_metadata(coin_id)

    def _resolve_coin_id(self, query: str) -> str:
        """Resolve a query string to a CoinGecko coin ID."""
        try:
            resp = self._client.get("/search", params={"query": query})
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            msg = f"CoinGecko search failed for '{query}': {e}"
            raise SearcherError(msg) from e

        coins: list[dict[str, Any]] = data.get("coins", [])
        if not coins:
            msg = f"No projects found for query: '{query}'"
            raise SearcherError(msg)

        # Return the top match
        return str(coins[0]["id"])

    def _fetch_coin_metadata(self, coin_id: str) -> ProjectMetadata:
        """Fetch full metadata for a coin by its CoinGecko ID."""
        try:
            resp = self._client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            msg = f"CoinGecko coin fetch failed for '{coin_id}': {e}"
            raise SearcherError(msg) from e

        # Extract metadata
        links: dict[str, Any] = data.get("links", {})
        homepage: list[str] = [url for url in links.get("homepage", []) if url]

        # Whitepaper: CoinGecko stores it in links.whitepaper or
        # sometimes in links.repos_url or description
        whitepaper_url: str | None = links.get("whitepaper") or None

        # Description (English)
        description_data: dict[str, str] = data.get("description", {})
        description = description_data.get("en", "")

        # Categories
        categories: list[str] = [c for c in data.get("categories", []) if c]

        # Market cap rank
        market_cap_rank = data.get("market_cap_rank")

        return ProjectMetadata(
            coingecko_id=coin_id,
            name=data.get("name", coin_id),
            symbol=data.get("symbol", "").upper(),
            website_urls=homepage,
            whitepaper_url=whitepaper_url,
            description=description[:2000] if description else "",
            categories=categories,
            market_cap_rank=market_cap_rank,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


def make_searcher_node(searcher: CoinGeckoSearcher) -> Any:
    """Create the Searcher LangGraph node.

    Reads ``project_query`` from state, queries CoinGecko,
    writes ``project_metadata`` back to state.
    """

    def search_project(state: ComplianceState) -> dict[str, Any]:
        query = state["project_query"]
        logger.info("Searcher: searching for '%s'", query)
        metadata = searcher.search(query)
        logger.info(
            "Searcher: found %s (%s), %d website URLs",
            metadata.name,
            metadata.symbol,
            len(metadata.website_urls),
        )
        return {"project_metadata": metadata}

    return search_project
