"""Tests for the WebCrawler agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mas.agents.crawler import CrawlerError, WebCrawler


class TestCrawlMultipleURLs:
    def test_combines_multiple_sources(self) -> None:
        crawler = WebCrawler(timeout=5.0, max_urls=3)
        with patch.object(crawler, "_extract_url") as mock_extract:
            mock_extract.side_effect = ["Content A" * 20, "Content B" * 20, None]
            result = crawler.crawl(["https://a.com", "https://b.com", "https://c.com"])
            assert "Content A" in result
            assert "Content B" in result
            assert mock_extract.call_count == 3

    def test_raises_if_all_fail(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        with patch.object(crawler, "_extract_url", return_value=None), pytest.raises(CrawlerError):
            crawler.crawl(["https://fail.com"])

    def test_respects_max_urls(self) -> None:
        crawler = WebCrawler(timeout=5.0, max_urls=2)
        with patch.object(crawler, "_extract_url", return_value="x" * 200) as mock:
            crawler.crawl(["https://a.com", "https://b.com", "https://c.com"])
            assert mock.call_count == 2

    def test_truncates_per_url(self) -> None:
        crawler = WebCrawler(timeout=5.0, max_urls=1)
        long_text = "x" * 20000
        with patch.object(crawler, "_extract_url", return_value=long_text):
            result = crawler.crawl(["https://a.com"])
            # MAX_CHARS_PER_URL = 15000 + "## Source:" header
            assert len(result) < 16000


class TestURLRouting:
    def test_pdf_routed_to_extract_pdf(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        with patch.object(crawler, "_extract_pdf", return_value="pdf content") as mock:
            result = crawler._extract_url("https://example.com/whitepaper.pdf")
            mock.assert_called_once()
            assert result == "pdf content"

    def test_github_routed_to_readme(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        with patch.object(crawler, "_extract_github_readme", return_value="readme") as mock:
            result = crawler._extract_url("https://github.com/org/repo")
            mock.assert_called_once()
            assert result == "readme"

    def test_regular_url_uses_crawl4ai(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        with patch.object(crawler, "_extract_with_crawl4ai", return_value="web") as mock:
            result = crawler._extract_url("https://example.com")
            mock.assert_called_once()
            assert result == "web"


class TestGitHubReadme:
    def test_extracts_readme(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# Project\n" + "Some content here. " * 10  # >50 chars
        crawler._client.get = MagicMock(return_value=mock_resp)

        result = crawler._extract_github_readme("https://github.com/org/repo")
        assert result is not None
        assert "Project" in result

    def test_tries_main_and_master(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        call_count = 0

        def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if "master/README.md" in url:
                resp.status_code = 200
                resp.text = "x" * 100
            else:
                resp.status_code = 404
                resp.text = ""
            return resp

        crawler._client.get = mock_get  # type: ignore[assignment]
        result = crawler._extract_github_readme("https://github.com/org/repo")
        assert result is not None
        assert call_count > 1  # Tried main first, then master

    def test_returns_none_for_no_readme(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = ""
        crawler._client.get = MagicMock(return_value=mock_resp)

        result = crawler._extract_github_readme("https://github.com/org/repo")
        assert result is None


class TestMultipleRuns:
    """Verify the crawler works across multiple sequential invocations."""

    def test_multiple_crawl_calls(self) -> None:
        crawler = WebCrawler(timeout=5.0, max_urls=1)
        with patch.object(crawler, "_extract_url", return_value="content" * 20):
            r1 = crawler.crawl(["https://a.com"])
            r2 = crawler.crawl(["https://b.com"])
            assert "content" in r1
            assert "content" in r2

    def test_static_fallback_when_crawl4ai_missing(self) -> None:
        crawler = WebCrawler(timeout=5.0)
        with (
            patch.dict("sys.modules", {"crawl4ai": None}),
            patch.object(crawler, "_extract_static", return_value="static") as mock,
        ):
            # Force ImportError for crawl4ai
            result = crawler._extract_with_crawl4ai("https://example.com")
            # Will fall through to _extract_static or return None
            # depending on import error handling
            assert result is not None or mock.called
