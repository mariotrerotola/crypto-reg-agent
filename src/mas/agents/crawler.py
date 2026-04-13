"""Crawler Agent: extracts text content from project websites.

Implements the Crawler Agent from Section 3.3 of the paper, which extracts
textual content from web resources and generates a standardized Markdown
representation for downstream analysis.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import trafilatura

from mas.schemas.project import ProjectMetadata
from mas.schemas.state import ComplianceState

logger = logging.getLogger(__name__)

MAX_CHARS_PER_URL = 15000
MAX_TOTAL_CHARS = 50000


class CrawlerError(Exception):
    """Raised when web content extraction fails."""


class WebCrawler:
    """Crawler Agent: extracts text from project websites.

    Uses trafilatura for main content extraction, with httpx for HTTP
    fetching. Falls back to raw HTML text extraction if trafilatura
    returns nothing. PDF URLs are downloaded and extracted via pymupdf
    if available.

    Args:
        timeout: HTTP request timeout in seconds.
        max_urls: Maximum number of URLs to crawl per project.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_urls: int = 5,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        self._max_urls = max_urls

    def crawl(self, urls: list[str]) -> str:
        """Crawl a list of URLs and extract main text content.

        Args:
            urls: List of URLs to crawl (prioritized, first is most important).

        Returns:
            Combined text content in Markdown format.

        Raises:
            CrawlerError: If no text could be extracted from any URL.
        """
        sections: list[str] = []
        total_chars = 0

        for url in urls[: self._max_urls]:
            if total_chars >= MAX_TOTAL_CHARS:
                break

            text = self._extract_url(url)
            if text:
                truncated = text[:MAX_CHARS_PER_URL]
                sections.append(f"## Source: {url}\n\n{truncated}")
                total_chars += len(truncated)
                logger.info("Crawler: extracted %d chars from %s", len(truncated), url)
            else:
                logger.warning("Crawler: no content extracted from %s", url)

        if not sections:
            msg = f"No text content could be extracted from any URL: {urls}"
            raise CrawlerError(msg)

        logger.info("Crawler: %d URLs crawled, %d total chars", len(sections), total_chars)
        return "\n\n---\n\n".join(sections)

    def _extract_url(self, url: str) -> str | None:
        """Fetch and extract main content from a single URL."""
        # Handle PDF URLs separately
        if url.lower().endswith(".pdf"):
            return self._extract_pdf(url)

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            html = resp.text
        except httpx.HTTPError as e:
            logger.warning("Crawler: HTTP error for %s: %s", url, e)
            return None

        # Primary: trafilatura
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_precision=True,
        )
        if text and len(text) > 100:
            return text

        # Fallback: basic HTML text extraction via trafilatura bare mode
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_recall=True,
        )
        if text and len(text) > 100:
            return text

        logger.warning("Crawler: trafilatura returned insufficient content for %s", url)
        return None

    def _extract_pdf(self, url: str) -> str | None:
        """Download and extract text from a PDF URL."""
        try:
            import pymupdf  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("Crawler: pymupdf not installed, skipping PDF: %s", url)
            return None

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content
        except httpx.HTTPError as e:
            logger.warning("Crawler: HTTP error downloading PDF %s: %s", url, e)
            return None

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            pages: list[str] = []
            for page in doc:
                text = page.get_text()
                if text.strip():
                    pages.append(text.strip())
            doc.close()
        except Exception as e:
            logger.warning("Crawler: PDF extraction failed for %s: %s", url, e)
            return None

        if not pages:
            return None

        return "\n\n".join(pages)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


def make_crawler_node(crawler: WebCrawler) -> Any:
    """Create the Crawler LangGraph node.

    Reads ``project_metadata`` from state, crawls website URLs,
    writes ``whitepaper_text`` and ``crawled_urls`` back to state.

    If crawling fails entirely, falls back to the project description
    from the Searcher metadata.
    """

    def crawl_project(state: ComplianceState) -> dict[str, Any]:
        metadata: ProjectMetadata = state["project_metadata"]

        # Prioritize whitepaper URL, then website URLs
        urls: list[str] = []
        if metadata.whitepaper_url:
            urls.append(metadata.whitepaper_url)
        urls.extend(metadata.website_urls)

        logger.info(
            "Crawler: crawling %d URLs for %s (%s)",
            len(urls),
            metadata.name,
            metadata.symbol,
        )

        try:
            text = crawler.crawl(urls)
        except CrawlerError:
            # Fallback: use the CoinGecko description as input
            if metadata.description:
                logger.warning("Crawler: all URLs failed, falling back to CoinGecko description")
                text = f"# {metadata.name} ({metadata.symbol})\n\n{metadata.description}"
            else:
                raise

        # Prepend project description from registry as context
        if metadata.description and not text.startswith(f"# {metadata.name}"):
            header = (
                f"# {metadata.name} ({metadata.symbol})\n\n{metadata.description[:2000]}\n\n---\n\n"
            )
            text = header + text

        return {
            "whitepaper_text": text,
            "crawled_urls": urls,
        }

    return crawl_project
