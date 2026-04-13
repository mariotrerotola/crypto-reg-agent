"""Crawler Agent: extracts text content from project websites.

Implements the Crawler Agent from Section 3.3 of the paper, which extracts
textual content from web resources and generates a standardized Markdown
representation for downstream analysis.

Uses **crawl4ai** as the default extraction engine — it handles both static
HTML and JavaScript-rendered SPA pages, producing clean Markdown output
suitable for LLM consumption.  PDF and GitHub README URLs are handled via
dedicated lightweight methods (no browser needed).

The browser is reused across calls via ``nest_asyncio`` to avoid
"cannot be called from a running event loop" errors in batch mode.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import nest_asyncio

from mas.schemas.project import ProjectMetadata
from mas.schemas.state import ComplianceState

# Allow nested event loops (safe for sync-wrapping async crawl4ai)
nest_asyncio.apply()

logger = logging.getLogger(__name__)

MAX_CHARS_PER_URL = 15000
MAX_TOTAL_CHARS = 50000

# Common branch names to try for GitHub raw README
_GITHUB_BRANCHES = ("main", "master")
_README_NAMES = ("README.md", "README.rst", "README.txt", "README")


class CrawlerError(Exception):
    """Raised when web content extraction fails."""


class WebCrawler:
    """Crawler Agent: extracts text from project websites.

    Uses crawl4ai for web page extraction (handles static + SPA sites),
    with dedicated handlers for PDFs (pymupdf) and GitHub READMEs
    (raw.githubusercontent.com).

    The crawl4ai browser instance is lazily created and reused across
    multiple ``crawl()`` calls to avoid per-URL browser startup overhead.

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
        self._timeout_ms = int(timeout * 1000)

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
        # Handle PDF URLs separately (direct download, no browser)
        if url.lower().endswith(".pdf"):
            return self._extract_pdf(url)

        # Handle GitHub repo URLs -> fetch README directly (no browser)
        if "github.com/" in url and "/raw/" not in url:
            return self._extract_github_readme(url)

        # Default: crawl4ai for all web pages (static + SPA)
        return self._extract_with_crawl4ai(url)

    def _extract_with_crawl4ai(self, url: str) -> str | None:
        """Extract content using crawl4ai (handles static + JS-rendered pages).

        Uses ``nest_asyncio`` to safely call async code from sync context,
        avoiding "cannot be called from running event loop" errors.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        except ImportError:
            logger.warning(
                "Crawler: crawl4ai not installed, falling back to httpx for %s",
                url,
            )
            return self._extract_static(url)

        async def _crawl() -> str | None:
            browser_cfg = BrowserConfig(headless=True)
            run_cfg = CrawlerRunConfig(page_timeout=self._timeout_ms)
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(url, config=run_cfg)
                md = result.markdown
                if md and md.raw_markdown and len(md.raw_markdown) > 100:  # noqa: PLR2004
                    return md.raw_markdown
            return None

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            text = loop.run_until_complete(_crawl())
            if text:
                logger.info("Crawler: crawl4ai extracted %d chars from %s", len(text), url)
                return text
        except Exception as e:
            logger.warning("Crawler: crawl4ai failed for %s: %s", url, e)

        return None

    def _extract_static(self, url: str) -> str | None:
        """Lightweight fallback: fetch HTML with httpx, extract with trafilatura."""
        import trafilatura

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            html = resp.text
        except httpx.HTTPError as e:
            logger.warning("Crawler: HTTP error for %s: %s", url, e)
            return None

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_recall=True,
        )
        if text and len(text) > 100:  # noqa: PLR2004
            return text
        return None

    def _extract_github_readme(self, repo_url: str) -> str | None:
        """Fetch the README from a GitHub repository via raw URL.

        Tries ``main`` and ``master`` branches with common README names.
        """
        repo_url = repo_url.rstrip("/")
        if "github.com/" not in repo_url:
            return None
        path = repo_url.split("github.com/", 1)[1]
        if "/tree/" in path:
            path = path.split("/tree/")[0]

        for branch in _GITHUB_BRANCHES:
            for readme in _README_NAMES:
                raw_url = f"https://raw.githubusercontent.com/{path}/{branch}/{readme}"
                try:
                    resp = self._client.get(raw_url)
                    if resp.status_code == 200 and len(resp.text) > 50:  # noqa: PLR2004
                        logger.info("Crawler: fetched GitHub README from %s", raw_url)
                        return resp.text
                except httpx.HTTPError:
                    continue
        logger.warning("Crawler: no README found for %s", repo_url)
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

        # Prioritize whitepaper URL, then website URLs, then GitHub repos
        urls: list[str] = []
        if metadata.whitepaper_url:
            urls.append(metadata.whitepaper_url)
        urls.extend(metadata.website_urls)
        urls.extend(metadata.github_urls)

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
                f"# {metadata.name} ({metadata.symbol})\n\n"
                f"{metadata.description[:2000]}\n\n---\n\n"
            )
            text = header + text

        return {
            "whitepaper_text": text,
            "crawled_urls": urls,
        }

    return crawl_project
