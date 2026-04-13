"""GeckoTerminal API client for discovering newly launched tokens.

GeckoTerminal tracks DEX pools across 100+ networks in real-time.
The ``/networks/new_pools`` endpoint returns pools created in the last
few hours — ideal for early warning scanning of freshly launched tokens.

Free API, no key required.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mas.agents.ratelimit import RateLimiter
from mas.schemas.project import ProjectMetadata

logger = logging.getLogger(__name__)

GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"


class GeckoTerminalError(Exception):
    """Raised when GeckoTerminal API calls fail."""


class GeckoTerminalClient:
    """Client for the GeckoTerminal API (free, no key required).

    Args:
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=GECKOTERMINAL_BASE,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        self._rate_limiter = RateLimiter(min_interval=0.5)

    def list_new_tokens(self, limit: int = 20) -> list[ProjectMetadata]:
        """Fetch recently created DEX pools and extract token metadata.

        Args:
            limit: Maximum number of unique tokens to return.

        Returns:
            List of ProjectMetadata for recently launched tokens.

        Raises:
            GeckoTerminalError: If the API call fails.
        """
        try:
            resp = self._client.get("/networks/new_pools", params={"page": 1})
            resp.raise_for_status()
            pools: list[dict[str, Any]] = resp.json().get("data", [])
        except httpx.HTTPError as e:
            msg = f"GeckoTerminal new pools fetch failed: {e}"
            raise GeckoTerminalError(msg) from e

        # Extract unique tokens
        results: list[ProjectMetadata] = []
        seen: set[str] = set()

        for pool in pools:
            if len(results) >= limit:
                break

            attr = pool.get("attributes", {})
            base_token = (
                pool.get("relationships", {})
                .get("base_token", {})
                .get("data", {})
            )
            token_id = base_token.get("id", "")
            if not token_id or token_id in seen:
                continue
            seen.add(token_id)

            network = (
                pool.get("relationships", {})
                .get("network", {})
                .get("data", {})
                .get("id", "unknown")
            )

            # Parse token name from pool name (format: "TOKEN / SOL")
            pool_name = attr.get("name", "")
            token_name = (
                pool_name.split(" / ")[0].strip()
                if " / " in pool_name
                else pool_name
            )

            address = token_id.split("_", 1)[1] if "_" in token_id else ""

            # Try to fetch token details
            info = self._fetch_token_info(network, address)
            full_name = info.get("name") or token_name
            symbol = info.get("symbol") or token_name[:8]
            description = info.get("description") or ""
            websites: list[str] = info.get("websites") or []

            results.append(
                ProjectMetadata(
                    coingecko_id=f"gt:{network}:{address[:16]}",
                    name=full_name,
                    symbol=symbol.upper(),
                    website_urls=websites,
                    description=description[:2000],
                    contract_addresses={network: address} if address else {},
                )
            )
            logger.info("GeckoTerminal: found %s (%s) on %s", full_name, symbol, network)

        return results

    def _fetch_token_info(self, network: str, address: str) -> dict[str, Any]:
        """Fetch detailed token info from GeckoTerminal."""
        if not address:
            return {}
        self._rate_limiter.wait()
        try:
            resp = self._client.get(f"/networks/{network}/tokens/{address}")
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("attributes", {})
        except httpx.HTTPError:
            pass
        return {}

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
