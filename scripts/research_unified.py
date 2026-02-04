#!/usr/bin/env python3
"""
Unified Research Aggregator - 4-Source Research Pipeline

Sources:
1. Academic APIs (arXiv, Semantic Scholar, CrossRef)
2. Context7 MCP (library documentation)
3. Claude-flow memory (stored patterns)
4. Local docs (.planning/, docs/, ARCHITECTURE.md, README.md)

Usage:
    python research_unified.py "query" [--sources academic,context7,memory,local]
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ResearchResult:
    source: str
    title: str
    content: str
    relevance: float = 0.0
    url: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class UnifiedResearch:
    """Aggregates research from multiple sources."""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root or os.getcwd())

    async def search(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[ResearchResult]:
        """
        Search across all configured sources.

        Args:
            query: Search query
            sources: List of sources to search (default: all)
            limit: Max results per source

        Returns:
            Merged and ranked results from all sources
        """
        sources = sources or ["academic", "context7", "memory", "local"]
        tasks = []

        for source in sources:
            if source == "academic":
                tasks.append(self.search_academic(query, limit))
            elif source == "context7":
                tasks.append(self.search_context7(query, limit))
            elif source == "memory":
                tasks.append(self.search_memory(query, limit))
            elif source == "local":
                tasks.append(self.search_local_docs(query, limit))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results, filtering exceptions
        all_results: list[ResearchResult] = []
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            elif isinstance(result, Exception):
                print(f"[WARN] Source error: {result}", file=sys.stderr)

        return self.merge_and_rank(all_results, query, limit * 2)

    async def search_academic(self, query: str, limit: int = 5) -> list[ResearchResult]:
        """Search academic APIs (delegates to existing research skill)."""
        results: list[ResearchResult] = []

        # Try Semantic Scholar
        try:
            cmd = [
                "curl",
                "-s",
                f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit={limit}&fields=title,abstract,url",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            data = json.loads(stdout.decode())

            for paper in data.get("data", [])[:limit]:
                results.append(
                    ResearchResult(
                        source="semantic_scholar",
                        title=paper.get("title", "Untitled"),
                        content=paper.get("abstract", "")[:500],
                        url=paper.get("url"),
                        metadata={"paperId": paper.get("paperId")},
                    )
                )
        except Exception as e:
            print(f"[WARN] Semantic Scholar search failed: {e}", file=sys.stderr)

        return results

    async def search_context7(self, query: str, limit: int = 5) -> list[ResearchResult]:
        """Search library docs via Context7 MCP."""
        results: list[ResearchResult] = []

        # Extract library name from query (simple heuristic)
        keywords = query.lower().split()
        library_candidates = ["fastapi", "pydantic", "sqlalchemy", "pytest", "numpy", "pandas"]
        library = next((k for k in keywords if k in library_candidates), None)

        if not library:
            return results

        try:
            # Resolve library ID
            cmd = [
                "npx",
                "@claude-flow/cli@latest",
                "mcp",
                "call",
                "context7",
                "resolve-library-id",
                "--libraryName",
                library,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)

            if proc.returncode == 0:
                lib_data = json.loads(stdout.decode())
                lib_id = lib_data.get("libraryId", f"/pypi/{library}")

                # Query docs
                cmd2 = [
                    "npx",
                    "@claude-flow/cli@latest",
                    "mcp",
                    "call",
                    "context7",
                    "query-docs",
                    "--libraryId",
                    lib_id,
                    "--query",
                    query,
                ]
                proc2 = await asyncio.create_subprocess_exec(
                    *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=15)

                if proc2.returncode == 0:
                    docs_data = json.loads(stdout2.decode())
                    for doc in docs_data.get("results", [])[:limit]:
                        results.append(
                            ResearchResult(
                                source="context7",
                                title=f"{library}: {doc.get('title', 'Doc')}",
                                content=doc.get("content", "")[:500],
                                url=doc.get("url"),
                                metadata={"library": library},
                            )
                        )
        except Exception as e:
            print(f"[WARN] Context7 search failed: {e}", file=sys.stderr)

        return results

    async def search_memory(self, query: str, limit: int = 5) -> list[ResearchResult]:
        """Search claude-flow memory for stored patterns."""
        results: list[ResearchResult] = []

        try:
            cmd = [
                "npx",
                "@claude-flow/cli@latest",
                "memory",
                "search",
                "--query",
                query,
                "--limit",
                str(limit),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode == 0:
                # Parse memory search results
                for line in stdout.decode().strip().split("\n"):
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            results.append(
                                ResearchResult(
                                    source="memory",
                                    title=entry.get("key", "Pattern"),
                                    content=str(entry.get("value", ""))[:500],
                                    relevance=entry.get("score", 0.5),
                                    metadata={"namespace": entry.get("namespace")},
                                )
                            )
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[WARN] Memory search failed: {e}", file=sys.stderr)

        return results

    async def search_local_docs(self, query: str, limit: int = 5) -> list[ResearchResult]:
        """Search local documentation files."""
        results: list[ResearchResult] = []
        query_lower = query.lower()

        # Paths to search
        doc_paths = [
            self.project_root / ".planning",
            self.project_root / "docs",
            self.project_root / "ARCHITECTURE.md",
            self.project_root / "README.md",
            self.project_root / "CLAUDE.md",
        ]

        for path in doc_paths:
            if not path.exists():
                continue

            if path.is_file():
                files = [path]
            else:
                files = list(path.glob("**/*.md"))[:20]

            for file in files:
                try:
                    content = file.read_text()
                    # Simple relevance: count query terms
                    relevance = sum(1 for word in query_lower.split() if word in content.lower()) / len(
                        query_lower.split()
                    )

                    if relevance > 0.3:
                        results.append(
                            ResearchResult(
                                source="local",
                                title=str(file.relative_to(self.project_root)),
                                content=content[:500],
                                relevance=relevance,
                                metadata={"path": str(file)},
                            )
                        )
                except Exception:
                    pass

        # Sort by relevance
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]

    def merge_and_rank(
        self, results: list[ResearchResult], query: str, limit: int
    ) -> list[ResearchResult]:
        """Merge and rank results across sources."""
        query_lower = query.lower()

        for result in results:
            if result.relevance == 0:
                # Calculate relevance if not set
                text = (result.title + " " + result.content).lower()
                matches = sum(1 for word in query_lower.split() if word in text)
                result.relevance = matches / max(len(query_lower.split()), 1)

        # Sort by relevance
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Unified Research Aggregator")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--sources",
        "-s",
        default="academic,context7,memory,local",
        help="Comma-separated sources (default: all)",
    )
    parser.add_argument("--limit", "-l", type=int, default=5, help="Results per source")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]
    research = UnifiedResearch()
    results = await research.search(args.query, sources, args.limit)

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "source": r.source,
                        "title": r.title,
                        "content": r.content[:200],
                        "relevance": round(r.relevance, 2),
                        "url": r.url,
                    }
                    for r in results
                ],
                indent=2,
            )
        )
    else:
        print(f"Found {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r.source}] {r.title}")
            print(f"   Relevance: {r.relevance:.2f}")
            if r.url:
                print(f"   URL: {r.url}")
            print(f"   {r.content[:100]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
