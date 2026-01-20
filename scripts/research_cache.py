#!/usr/bin/env python3
"""
Research Cache - File-based caching with TTL

Provides caching for research results to avoid redundant API calls.
Features:
- 1-hour default TTL
- File-based storage (JSON)
- Cache key based on query hash
- Automatic cleanup of expired entries
- Cache statistics

USAGE:
    from research_cache import ResearchCache

    cache = ResearchCache()
    result = cache.get(query)
    if result is None:
        result = do_expensive_research(query)
        cache.set(query, result)

CLI:
    python research_cache.py get "query"
    python research_cache.py set "query" '{"data": "value"}'
    python research_cache.py stats
    python research_cache.py clear
    python research_cache.py clear --expired
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


# =============================================================================
# Configuration
# =============================================================================

CACHE_DIR = Path.home() / ".claude" / "cache" / "research"
DEFAULT_TTL_HOURS = 1
MAX_CACHE_SIZE_MB = 100  # Max cache size before cleanup


# =============================================================================
# Cache Entry
# =============================================================================


def _hash_query(query: str) -> str:
    """Generate cache key from query."""
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]


def _get_cache_path(key: str) -> Path:
    """Get cache file path for key."""
    return CACHE_DIR / f"{key}.json"


# =============================================================================
# Research Cache
# =============================================================================


class ResearchCache:
    """
    File-based research cache with TTL.

    Each cache entry is stored as a separate JSON file:
    - Key: SHA256 hash of normalized query (first 16 chars)
    - Value: JSON with metadata and cached result

    Structure:
    {
        "query": "original query",
        "key": "cache key",
        "created_at": "ISO timestamp",
        "expires_at": "ISO timestamp",
        "ttl_hours": 1,
        "source": "search_type",
        "result": { ... cached data ... }
    }
    """

    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS, cache_dir: Path = CACHE_DIR):
        self.ttl_hours = ttl_hours
        self.cache_dir = cache_dir
        self._ensure_dir()

    def _ensure_dir(self):
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, query: str, source: str | None = None) -> Optional[Dict[str, Any]]:
        """
        Get cached result for query.

        Args:
            query: Research query
            source: Optional source filter (e.g., "arxiv", "semantic")

        Returns:
            Cached result or None if not found/expired
        """
        key = _hash_query(query)
        cache_path = _get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text())

            # Check expiration
            expires_at = datetime.fromisoformat(data["expires_at"])
            if datetime.now() > expires_at:
                # Expired - delete and return None
                cache_path.unlink(missing_ok=True)
                return None

            # Check source filter
            if source and data.get("source") != source:
                return None

            # Cache hit
            print(
                f"  Cache HIT: {key} (expires {expires_at.strftime('%H:%M:%S')})",
                file=sys.stderr,
            )
            return data.get("result")

        except (json.JSONDecodeError, KeyError, ValueError):
            # Invalid cache entry - delete it
            cache_path.unlink(missing_ok=True)
            return None

    def set(
        self,
        query: str,
        result: Any,
        source: str | None = None,
        ttl_hours: int | None = None,
    ) -> bool:
        """
        Cache result for query.

        Args:
            query: Research query
            result: Result to cache
            source: Source identifier (e.g., "arxiv", "semantic")
            ttl_hours: Override default TTL

        Returns:
            True if cached successfully
        """
        key = _hash_query(query)
        cache_path = _get_cache_path(key)
        ttl = ttl_hours or self.ttl_hours

        now = datetime.now()
        expires_at = now + timedelta(hours=ttl)

        data = {
            "query": query,
            "key": key,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "ttl_hours": ttl,
            "source": source,
            "result": result,
        }

        try:
            cache_path.write_text(json.dumps(data, indent=2, default=str))
            print(f"  Cache SET: {key} (TTL {ttl}h)", file=sys.stderr)
            return True
        except (OSError, TypeError) as e:
            print(f"  Cache SET failed: {e}", file=sys.stderr)
            return False

    def delete(self, query: str) -> bool:
        """Delete cache entry for query."""
        key = _hash_query(query)
        cache_path = _get_cache_path(key)

        if cache_path.exists():
            cache_path.unlink()
            return True
        return False

    def clear(self, expired_only: bool = False) -> int:
        """
        Clear cache entries.

        Args:
            expired_only: If True, only clear expired entries

        Returns:
            Number of entries cleared
        """
        cleared = 0
        now = datetime.now()

        for cache_file in self.cache_dir.glob("*.json"):
            if expired_only:
                try:
                    data = json.loads(cache_file.read_text())
                    expires_at = datetime.fromisoformat(data["expires_at"])
                    if now <= expires_at:
                        continue  # Not expired
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass  # Invalid entry - delete it

            cache_file.unlink()
            cleared += 1

        return cleared

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = 0
        total_size = 0
        expired_count = 0
        source_counts: Dict[str, int] = {}
        oldest_entry = None
        newest_entry = None
        now = datetime.now()

        for cache_file in self.cache_dir.glob("*.json"):
            total_entries += 1
            total_size += cache_file.stat().st_size

            try:
                data = json.loads(cache_file.read_text())

                # Check expiration
                expires_at = datetime.fromisoformat(data["expires_at"])
                if now > expires_at:
                    expired_count += 1

                # Track sources
                source = data.get("source", "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1

                # Track oldest/newest
                created_at = datetime.fromisoformat(data["created_at"])
                if oldest_entry is None or created_at < oldest_entry:
                    oldest_entry = created_at
                if newest_entry is None or created_at > newest_entry:
                    newest_entry = created_at

            except (json.JSONDecodeError, KeyError, ValueError):
                expired_count += 1  # Invalid entries count as expired

        return {
            "total_entries": total_entries,
            "expired_entries": expired_count,
            "valid_entries": total_entries - expired_count,
            "total_size_kb": round(total_size / 1024, 2),
            "source_counts": source_counts,
            "oldest_entry": oldest_entry.isoformat() if oldest_entry else None,
            "newest_entry": newest_entry.isoformat() if newest_entry else None,
            "cache_dir": str(self.cache_dir),
        }

    def cleanup_if_needed(self, max_size_mb: int = MAX_CACHE_SIZE_MB) -> int:
        """
        Cleanup cache if it exceeds size limit.

        Removes oldest entries first until under limit.
        """
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
        max_size_bytes = max_size_mb * 1024 * 1024

        if total_size <= max_size_bytes:
            return 0

        # Get entries sorted by creation time (oldest first)
        entries = []
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text())
                created_at = datetime.fromisoformat(data["created_at"])
                entries.append((cache_file, created_at, cache_file.stat().st_size))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Invalid entry - delete immediately
                cache_file.unlink()
                total_size -= cache_file.stat().st_size if cache_file.exists() else 0

        # Sort by creation time (oldest first)
        entries.sort(key=lambda x: x[1])

        removed = 0
        for cache_file, _, size in entries:
            if total_size <= max_size_bytes:
                break
            cache_file.unlink()
            total_size -= size
            removed += 1

        return removed


# =============================================================================
# CLI
# =============================================================================


def cmd_get(args):
    """Get cached result."""
    cache = ResearchCache()
    result = cache.get(args.query, args.source)

    if result is None:
        print("Cache MISS")
        sys.exit(1)
    else:
        print(json.dumps(result, indent=2))


def cmd_set(args):
    """Set cache entry."""
    cache = ResearchCache()

    try:
        result = json.loads(args.result)
    except json.JSONDecodeError:
        result = args.result  # Store as string

    success = cache.set(args.query, result, args.source, args.ttl)
    sys.exit(0 if success else 1)


def cmd_stats(args):
    """Show cache statistics."""
    cache = ResearchCache()
    stats = cache.stats()

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"\n{'=' * 40}")
        print("Research Cache Statistics")
        print(f"{'=' * 40}")
        print(f"Total Entries:   {stats['total_entries']}")
        print(f"Valid Entries:   {stats['valid_entries']}")
        print(f"Expired Entries: {stats['expired_entries']}")
        print(f"Total Size:      {stats['total_size_kb']} KB")
        print(f"Cache Dir:       {stats['cache_dir']}")
        if stats["source_counts"]:
            print("\nSources:")
            for source, count in stats["source_counts"].items():
                print(f"  - {source}: {count}")
        if stats["oldest_entry"]:
            print(f"\nOldest: {stats['oldest_entry']}")
        if stats["newest_entry"]:
            print(f"Newest: {stats['newest_entry']}")
        print(f"{'=' * 40}\n")


def cmd_clear(args):
    """Clear cache."""
    cache = ResearchCache()
    cleared = cache.clear(expired_only=args.expired)
    print(f"Cleared {cleared} cache entries")


def cmd_cleanup(args):
    """Run cleanup if needed."""
    cache = ResearchCache()
    removed = cache.cleanup_if_needed(args.max_size)
    if removed > 0:
        print(f"Cleaned up {removed} old cache entries")
    else:
        print("Cache size OK, no cleanup needed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Research cache management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # get command
    get_parser = subparsers.add_parser("get", help="Get cached result")
    get_parser.add_argument("query", help="Search query")
    get_parser.add_argument("--source", "-s", help="Filter by source")
    get_parser.set_defaults(func=cmd_get)

    # set command
    set_parser = subparsers.add_parser("set", help="Set cache entry")
    set_parser.add_argument("query", help="Search query")
    set_parser.add_argument("result", help="Result to cache (JSON or string)")
    set_parser.add_argument("--source", "-s", help="Source identifier")
    set_parser.add_argument("--ttl", "-t", type=int, help="TTL in hours")
    set_parser.set_defaults(func=cmd_set)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show cache statistics")
    stats_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    stats_parser.set_defaults(func=cmd_stats)

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear cache")
    clear_parser.add_argument(
        "--expired", "-e", action="store_true", help="Only clear expired entries"
    )
    clear_parser.set_defaults(func=cmd_clear)

    # cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Run cleanup if needed")
    cleanup_parser.add_argument(
        "--max-size", "-m", type=int, default=100, help="Max size in MB"
    )
    cleanup_parser.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
