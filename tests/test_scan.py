"""Tests for the scan-new functionality (new coin listing + batch analysis)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from mas.agents.searcher import CoinGeckoSearcher, SearcherError
from mas.schemas.project import ProjectMetadata


def _fake_coin_response(coin_id: str, name: str, symbol: str) -> dict[str, Any]:
    """Build a fake CoinGecko /coins/{id} response."""
    return {
        "id": coin_id,
        "name": name,
        "symbol": symbol,
        "links": {
            "homepage": [f"https://{coin_id}.io"],
            "whitepaper": None,
        },
        "description": {"en": f"{name} is a test project."},
        "categories": ["Test"],
        "market_cap_rank": None,
    }


MARKETS_PATH = "/coins/markets"


class TestListNewCoins:
    def test_returns_metadata_list(self) -> None:
        mock_client = MagicMock()

        markets_response = MagicMock()
        markets_response.json.return_value = [
            {"id": "coin-a", "symbol": "CA", "name": "Coin A"},
            {"id": "coin-b", "symbol": "CB", "name": "Coin B"},
            {"id": "coin-c", "symbol": "CC", "name": "Coin C"},
        ]
        markets_response.raise_for_status = MagicMock()

        coin_responses = {
            "/coins/coin-a": _fake_coin_response("coin-a", "Coin A", "CA"),
            "/coins/coin-b": _fake_coin_response("coin-b", "Coin B", "CB"),
            "/coins/coin-c": _fake_coin_response("coin-c", "Coin C", "CC"),
        }

        def mock_get(path: str, **kwargs: Any) -> MagicMock:
            if path == MARKETS_PATH:
                return markets_response
            resp = MagicMock()
            resp.json.return_value = coin_responses.get(path, {})
            resp.raise_for_status = MagicMock()
            return resp

        mock_client.get = mock_get

        searcher = CoinGeckoSearcher()
        searcher._client = mock_client  # type: ignore[assignment]

        results = searcher.list_new_coins(limit=3)
        assert len(results) == 3
        assert all(isinstance(r, ProjectMetadata) for r in results)
        assert results[0].name == "Coin A"
        assert results[1].coingecko_id == "coin-b"

    def test_respects_limit(self) -> None:
        mock_client = MagicMock()
        markets_response = MagicMock()
        markets_response.json.return_value = [
            {"id": f"coin-{i}"} for i in range(20)
        ]
        markets_response.raise_for_status = MagicMock()

        def mock_get(path: str, **kwargs: Any) -> MagicMock:
            if path == MARKETS_PATH:
                return markets_response
            coin_id = path.split("/")[-1]
            resp = MagicMock()
            resp.json.return_value = _fake_coin_response(coin_id, f"Coin {coin_id}", "X")
            resp.raise_for_status = MagicMock()
            return resp

        mock_client.get = mock_get

        searcher = CoinGeckoSearcher()
        searcher._client = mock_client  # type: ignore[assignment]

        results = searcher.list_new_coins(limit=5)
        assert len(results) == 5

    def test_skips_failed_coins(self) -> None:
        mock_client = MagicMock()
        markets_response = MagicMock()
        markets_response.json.return_value = [
            {"id": "good-coin"},
            {"id": "bad-coin"},
            {"id": "another-good"},
        ]
        markets_response.raise_for_status = MagicMock()

        import httpx

        def mock_get(path: str, **kwargs: Any) -> MagicMock:
            if path == MARKETS_PATH:
                return markets_response
            if "bad-coin" in path:
                raise httpx.HTTPError("API error")
            coin_id = path.split("/")[-1]
            resp = MagicMock()
            resp.json.return_value = _fake_coin_response(coin_id, f"Coin {coin_id}", "X")
            resp.raise_for_status = MagicMock()
            return resp

        mock_client.get = mock_get

        searcher = CoinGeckoSearcher()
        searcher._client = mock_client  # type: ignore[assignment]

        results = searcher.list_new_coins(limit=10)
        assert len(results) == 2  # bad-coin skipped

    def test_empty_list(self) -> None:
        mock_client = MagicMock()
        markets_response = MagicMock()
        markets_response.json.return_value = []
        markets_response.raise_for_status = MagicMock()
        mock_client.get = MagicMock(return_value=markets_response)

        searcher = CoinGeckoSearcher()
        searcher._client = mock_client  # type: ignore[assignment]

        results = searcher.list_new_coins()
        assert results == []

    def test_api_error_raises(self) -> None:
        import httpx

        mock_client = MagicMock()
        mock_client.get = MagicMock(side_effect=httpx.HTTPError("Network error"))

        searcher = CoinGeckoSearcher()
        searcher._client = mock_client  # type: ignore[assignment]

        with pytest.raises(SearcherError, match="new coins listing failed"):
            searcher.list_new_coins()
