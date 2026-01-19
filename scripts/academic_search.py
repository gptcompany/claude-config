#!/usr/bin/env python3
"""
Academic Search - Direct API Integration

Direct API calls to academic sources without MCP dependency:
- arXiv (with 3s gap between requests)
- Semantic Scholar (429 handling)
- CrossRef (polite pool)

Reuses patterns from spec_pipeline.py for retry logic and circuit breakers.

USAGE:
    python academic_search.py "machine learning" --source arxiv
    python academic_search.py "neural networks" --source semantic
    python academic_search.py "deep learning" --all --limit 5
"""

import argparse
import json
import os
import random
import socket
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Callable, Optional, List, Dict, Any


# =============================================================================
# Configuration
# =============================================================================

QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_ILP_PORT = int(os.getenv("QUESTDB_ILP_PORT", 9009))

# API endpoints
ARXIV_API = "http://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_API = "https://api.crossref.org/works"

# Rate limiting
ARXIV_DELAY = 3.0  # 3 seconds between arXiv requests
SEMANTIC_DELAY = 1.0  # 1 second between Semantic Scholar requests
CROSSREF_DELAY = 0.5  # 0.5 seconds between CrossRef requests

# Track last request times
_last_request_times: Dict[str, float] = {}


# =============================================================================
# Retry Decorator (from spec_pipeline.py)
# =============================================================================


class RetriableError(Exception):
    """Error that can be retried."""

    pass


class FatalError(Exception):
    """Error that should not be retried."""

    pass


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retriable: tuple = (
        ConnectionError,
        TimeoutError,
        RetriableError,
        socket.error,
        urllib.error.URLError,
    ),
):
    """Retry decorator with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retriable as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.1)
                    time.sleep(delay + jitter)
                    print(
                        f"  Retry {attempt}/{max_attempts} after {delay:.1f}s: {e}",
                        file=sys.stderr,
                    )
                except FatalError:
                    raise
            raise last_exception

        return wrapper

    return decorator


# =============================================================================
# Circuit Breaker (from spec_pipeline.py)
# =============================================================================


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""

    state: str = "closed"
    failure_count: int = 0
    last_failure_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None


class CircuitBreaker:
    """Circuit breaker for external services."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 3,
        reset_timeout: int = 60,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = CircuitBreakerState()

    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self._state.state == "open":
            if self._state.opened_at:
                elapsed = (datetime.now() - self._state.opened_at).total_seconds()
                if elapsed >= self.reset_timeout:
                    self._state.state = "half_open"
                    return False
            return True
        return False

    def record_success(self):
        """Record successful call."""
        self._state.failure_count = 0
        self._state.state = "closed"

    def record_failure(self, error: str = None):
        """Record failed call."""
        self._state.failure_count += 1
        self._state.last_failure_at = datetime.now()
        if self._state.failure_count >= self.failure_threshold:
            self._state.state = "open"
            self._state.opened_at = datetime.now()
            print(f"  Circuit OPEN for {self.service_name}: {error}", file=sys.stderr)

    def __enter__(self):
        if self.is_open():
            raise RetriableError(f"Circuit open for {self.service_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(str(exc_val) if exc_val else None)
        return False


# Global circuit breakers
CIRCUITS = {
    "arxiv": CircuitBreaker("arxiv", failure_threshold=3, reset_timeout=120),
    "semantic": CircuitBreaker("semantic", failure_threshold=3, reset_timeout=60),
    "crossref": CircuitBreaker("crossref", failure_threshold=3, reset_timeout=60),
}


# =============================================================================
# Rate Limiting
# =============================================================================


def rate_limit(source: str, delay: float):
    """Enforce rate limiting for a source."""
    last_time = _last_request_times.get(source, 0)
    elapsed = time.time() - last_time
    if elapsed < delay:
        sleep_time = delay - elapsed
        time.sleep(sleep_time)
    _last_request_times[source] = time.time()


# =============================================================================
# QuestDB Metrics
# =============================================================================


_questdb_socket: Optional[socket.socket] = None


def _get_questdb_socket() -> Optional[socket.socket]:
    """Get or create reusable QuestDB socket."""
    global _questdb_socket
    if _questdb_socket is None:
        try:
            _questdb_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _questdb_socket.connect((QUESTDB_HOST, QUESTDB_ILP_PORT))
            _questdb_socket.settimeout(2.0)
        except (socket.error, OSError):
            _questdb_socket = None
    return _questdb_socket


def _reset_questdb_socket():
    """Reset socket on error."""
    global _questdb_socket
    if _questdb_socket:
        try:
            _questdb_socket.close()
        except Exception:
            pass
        _questdb_socket = None


def _escape_tag(value: str) -> str:
    """Escape tag value for ILP."""
    return str(value).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def log_search_metric(
    source: str, query: str, result_count: int, duration_ms: int, status: str
) -> bool:
    """Log search metric to QuestDB."""
    sock = _get_questdb_socket()
    if not sock:
        return False

    try:
        tags = f"source={_escape_tag(source)}"
        fields = (
            f'result_count={result_count}i,duration_ms={duration_ms}i,status="{status}"'
        )
        timestamp_ns = int(datetime.now().timestamp() * 1e9)
        line = f"academic_search,{tags} {fields} {timestamp_ns}\n"
        sock.sendall(line.encode())
        return True
    except (socket.error, OSError):
        _reset_questdb_socket()
        return False


# =============================================================================
# Paper Data Class
# =============================================================================


@dataclass
class Paper:
    """Normalized paper data structure."""

    id: str
    title: str
    authors: List[str]
    abstract: str
    year: Optional[int]
    url: str
    source: str
    doi: Optional[str] = None
    citations: Optional[int] = None
    pdf_url: Optional[str] = None
    categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "url": self.url,
            "source": self.source,
            "doi": self.doi,
            "citations": self.citations,
            "pdf_url": self.pdf_url,
            "categories": self.categories,
        }


# =============================================================================
# arXiv API
# =============================================================================


@retry(max_attempts=3, base_delay=2.0, max_delay=30.0)
def search_arxiv(query: str, max_results: int = 10) -> List[Paper]:
    """
    Search arXiv using their API.

    API docs: https://info.arxiv.org/help/api/basics.html
    Rate limit: 3 seconds between requests
    """
    if CIRCUITS["arxiv"].is_open():
        print("  arXiv circuit is open, skipping", file=sys.stderr)
        return []

    rate_limit("arxiv", ARXIV_DELAY)
    start_time = time.time()

    try:
        with CIRCUITS["arxiv"]:
            # Build query URL
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ClaudeCode-Academic-Search/1.0"},
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read().decode("utf-8")

            # Parse XML
            root = ET.fromstring(xml_data)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }

            papers = []
            for entry in root.findall("atom:entry", ns):
                # Extract paper ID from id URL
                id_url = entry.find("atom:id", ns).text
                paper_id = id_url.split("/abs/")[-1] if "/abs/" in id_url else id_url

                # Extract authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns)
                    if name is not None:
                        authors.append(name.text)

                # Extract categories
                categories = []
                for category in entry.findall("arxiv:primary_category", ns):
                    if category.get("term"):
                        categories.append(category.get("term"))

                # Extract year from published date
                published = entry.find("atom:published", ns)
                year = None
                if published is not None and published.text:
                    try:
                        year = int(published.text[:4])
                    except ValueError:
                        pass

                # Find PDF link
                pdf_url = None
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href")
                        break

                title_elem = entry.find("atom:title", ns)
                abstract_elem = entry.find("atom:summary", ns)

                paper = Paper(
                    id=paper_id,
                    title=title_elem.text.strip().replace("\n", " ")
                    if title_elem is not None
                    else "",
                    authors=authors,
                    abstract=abstract_elem.text.strip().replace("\n", " ")
                    if abstract_elem is not None
                    else "",
                    year=year,
                    url=id_url,
                    source="arxiv",
                    pdf_url=pdf_url,
                    categories=categories,
                )
                papers.append(paper)

            duration_ms = int((time.time() - start_time) * 1000)
            log_search_metric("arxiv", query, len(papers), duration_ms, "success")
            return papers

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_search_metric("arxiv", query, 0, duration_ms, "error")
        raise RetriableError(f"arXiv search failed: {e}")


# =============================================================================
# Semantic Scholar API
# =============================================================================


@retry(max_attempts=3, base_delay=2.0, max_delay=60.0)
def search_semantic_scholar(
    query: str, max_results: int = 10, year: str = None
) -> List[Paper]:
    """
    Search Semantic Scholar using their API.

    API docs: https://api.semanticscholar.org/api-docs/
    Rate limit: 100 requests per 5 minutes for unauthenticated
    """
    if CIRCUITS["semantic"].is_open():
        print("  Semantic Scholar circuit is open, skipping", file=sys.stderr)
        return []

    rate_limit("semantic", SEMANTIC_DELAY)
    start_time = time.time()

    try:
        with CIRCUITS["semantic"]:
            # Build query URL
            params = {
                "query": query,
                "limit": max_results,
                "fields": "paperId,title,authors,abstract,year,url,citationCount,openAccessPdf,fieldsOfStudy,externalIds",
            }
            if year:
                params["year"] = year

            url = f"{SEMANTIC_SCHOLAR_API}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "ClaudeCode-Academic-Search/1.0",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            papers = []
            for item in data.get("data", []):
                # Extract authors
                authors = [
                    a.get("name", "") for a in item.get("authors", []) if a.get("name")
                ]

                # Extract DOI
                external_ids = item.get("externalIds", {}) or {}
                doi = external_ids.get("DOI")

                # Extract PDF URL
                pdf_info = item.get("openAccessPdf", {}) or {}
                pdf_url = pdf_info.get("url")

                # Extract fields of study as categories
                categories = item.get("fieldsOfStudy", []) or []

                paper = Paper(
                    id=item.get("paperId", ""),
                    title=item.get("title", ""),
                    authors=authors,
                    abstract=item.get("abstract", "") or "",
                    year=item.get("year"),
                    url=item.get("url")
                    or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
                    source="semantic_scholar",
                    doi=doi,
                    citations=item.get("citationCount"),
                    pdf_url=pdf_url,
                    categories=categories,
                )
                papers.append(paper)

            duration_ms = int((time.time() - start_time) * 1000)
            log_search_metric("semantic", query, len(papers), duration_ms, "success")
            return papers

    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Rate limited - record failure and raise retriable
            duration_ms = int((time.time() - start_time) * 1000)
            log_search_metric("semantic", query, 0, duration_ms, "rate_limited")
            raise RetriableError(f"Semantic Scholar rate limited: {e}")
        raise

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_search_metric("semantic", query, 0, duration_ms, "error")
        raise RetriableError(f"Semantic Scholar search failed: {e}")


# =============================================================================
# CrossRef API
# =============================================================================


@retry(max_attempts=3, base_delay=1.0, max_delay=30.0)
def search_crossref(query: str, max_results: int = 10) -> List[Paper]:
    """
    Search CrossRef using their API.

    API docs: https://api.crossref.org/swagger-ui/index.html
    Rate limit: "polite" pool with mailto in User-Agent
    """
    if CIRCUITS["crossref"].is_open():
        print("  CrossRef circuit is open, skipping", file=sys.stderr)
        return []

    rate_limit("crossref", CROSSREF_DELAY)
    start_time = time.time()

    try:
        with CIRCUITS["crossref"]:
            # Build query URL
            params = {
                "query": query,
                "rows": max_results,
                "sort": "relevance",
            }
            url = f"{CROSSREF_API}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(
                url,
                headers={
                    # Using mailto for polite pool access
                    "User-Agent": "ClaudeCode-Academic-Search/1.0 (mailto:research@example.com)",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            papers = []
            for item in data.get("message", {}).get("items", []):
                # Extract authors
                authors = []
                for author in item.get("author", []):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    if given and family:
                        authors.append(f"{given} {family}")
                    elif family:
                        authors.append(family)

                # Extract year from published date
                year = None
                date_parts = item.get("published", {}).get("date-parts", [[]])
                if date_parts and date_parts[0]:
                    year = date_parts[0][0] if date_parts[0] else None

                # Extract title
                titles = item.get("title", [])
                title = titles[0] if titles else ""

                # Extract abstract
                abstract = item.get("abstract", "") or ""
                # CrossRef abstracts sometimes have JATS XML tags
                if abstract:
                    import re

                    abstract = re.sub(r"<[^>]+>", "", abstract)

                # Extract DOI
                doi = item.get("DOI", "")

                # Extract subjects as categories
                categories = item.get("subject", []) or []

                paper = Paper(
                    id=doi,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    url=item.get("URL") or f"https://doi.org/{doi}" if doi else "",
                    source="crossref",
                    doi=doi,
                    citations=item.get("is-referenced-by-count"),
                    categories=categories,
                )
                papers.append(paper)

            duration_ms = int((time.time() - start_time) * 1000)
            log_search_metric("crossref", query, len(papers), duration_ms, "success")
            return papers

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_search_metric("crossref", query, 0, duration_ms, "error")
        raise RetriableError(f"CrossRef search failed: {e}")


# =============================================================================
# Unified Search
# =============================================================================


def search_all(
    query: str, max_results: int = 10, sources: List[str] = None
) -> Dict[str, List[Paper]]:
    """
    Search all configured academic sources.

    Args:
        query: Search query
        max_results: Max results per source
        sources: List of sources to search (default: all)

    Returns:
        Dict mapping source name to list of papers
    """
    if sources is None:
        sources = ["arxiv", "semantic", "crossref"]

    results = {}

    for source in sources:
        try:
            if source == "arxiv":
                results["arxiv"] = search_arxiv(query, max_results)
            elif source == "semantic":
                results["semantic"] = search_semantic_scholar(query, max_results)
            elif source == "crossref":
                results["crossref"] = search_crossref(query, max_results)
            else:
                print(f"  Unknown source: {source}", file=sys.stderr)
        except Exception as e:
            print(f"  {source} search failed: {e}", file=sys.stderr)
            results[source] = []

    return results


def deduplicate_papers(papers: List[Paper]) -> List[Paper]:
    """
    Deduplicate papers across sources based on DOI or title similarity.
    Prefers papers with more citations.
    """
    seen_dois = {}
    seen_titles = {}
    unique = []

    for paper in sorted(papers, key=lambda p: p.citations or 0, reverse=True):
        # Check DOI first (most reliable)
        if paper.doi:
            if paper.doi in seen_dois:
                continue
            seen_dois[paper.doi] = paper

        # Fallback to title similarity
        title_key = paper.title.lower()[:50]  # First 50 chars of lowercase title
        if title_key in seen_titles:
            continue
        seen_titles[title_key] = paper

        unique.append(paper)

    return unique


# =============================================================================
# CLI
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Search academic papers from arXiv, Semantic Scholar, and CrossRef",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python academic_search.py "machine learning"
  python academic_search.py "neural networks" --source arxiv
  python academic_search.py "deep learning" --all --limit 5
  python academic_search.py "transformers" --source semantic --year 2024-
        """,
    )

    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--source",
        "-s",
        choices=["arxiv", "semantic", "crossref"],
        help="Search specific source",
    )
    parser.add_argument("--all", "-a", action="store_true", help="Search all sources")
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Max results per source (default: 10)",
    )
    parser.add_argument(
        "--year",
        "-y",
        help="Year filter for Semantic Scholar (e.g., 2020, 2020-2024, 2020-)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output JSON instead of formatted text",
    )
    parser.add_argument(
        "--dedupe", "-d", action="store_true", help="Deduplicate papers across sources"
    )

    args = parser.parse_args()

    # Determine sources to search
    if args.source:
        sources = [args.source]
    elif args.all:
        sources = ["arxiv", "semantic", "crossref"]
    else:
        # Default to Semantic Scholar (best coverage)
        sources = ["semantic"]

    # Search
    print(f"Searching: {args.query}", file=sys.stderr)
    print(f"Sources: {', '.join(sources)}", file=sys.stderr)

    results = search_all(args.query, args.limit, sources)

    # Collect all papers
    all_papers = []
    for source, papers in results.items():
        all_papers.extend(papers)

    # Deduplicate if requested
    if args.dedupe and len(sources) > 1:
        all_papers = deduplicate_papers(all_papers)
        print(f"After dedup: {len(all_papers)} papers", file=sys.stderr)

    # Output
    if args.json:
        output = {
            "query": args.query,
            "sources": sources,
            "total": len(all_papers),
            "papers": [p.to_dict() for p in all_papers],
        }
        print(json.dumps(output, indent=2))
    else:
        # Formatted text output
        print(f"\n{'=' * 60}")
        print(f"Query: {args.query}")
        print(f"Total: {len(all_papers)} papers")
        print(f"{'=' * 60}\n")

        for i, paper in enumerate(all_papers, 1):
            print(f"{i}. [{paper.source}] {paper.title}")
            if paper.authors:
                print(
                    f"   Authors: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}"
                )
            if paper.year:
                print(f"   Year: {paper.year}")
            if paper.citations is not None:
                print(f"   Citations: {paper.citations}")
            print(f"   URL: {paper.url}")
            if paper.abstract:
                abstract_preview = (
                    paper.abstract[:200] + "..."
                    if len(paper.abstract) > 200
                    else paper.abstract
                )
                print(f"   Abstract: {abstract_preview}")
            print()


if __name__ == "__main__":
    main()
