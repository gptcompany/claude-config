# Phase 19: Production Hardening - Research

**Researched:** 2026-01-26
**Domain:** Python asyncio resilience patterns (circuit breaker, caching, E2E testing)
**Confidence:** HIGH

<research_summary>
## Summary

Researched the Python ecosystem for production hardening of the ValidationOrchestrator. The standard approach combines:
1. **tenacity** for retry logic with exponential backoff
2. **pybreaker/aiobreaker** for circuit breaker pattern
3. **diskcache** for file-based persistent caching
4. **pytest-asyncio 1.x** for async E2E testing

Key finding: The current orchestrator already has basic error handling (`try/except` in `_run_validator`) and timeouts (hardcoded per validator). Phase 19 needs to systematize this into a proper resilience layer with:
- Configurable timeouts per validator (not hardcoded)
- Circuit breaker per external integration (MCP, QuestDB, Prometheus)
- File hash-based caching for incremental validation
- E2E tests that exercise real `spawn_agent()` + claude-flow MCP

**Primary recommendation:** Use tenacity + diskcache as core libraries. Avoid aiobreaker (inactive maintenance) - implement circuit breaker with tenacity's retry_if_exception_type + custom state tracking, or use purgatory-circuitbreaker for async support.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tenacity | 8.5.x | Retry with backoff, stop conditions | 96 code snippets, HIGH reputation, benchmark 76.4 |
| diskcache | 5.6.x | File-based persistent cache | 118 code snippets, HIGH reputation, faster than Redis |
| pytest-asyncio | 1.3.x | Async test fixtures | 104 code snippets, official pytest plugin |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| purgatory-circuitbreaker | 1.x | Async circuit breaker | If need Redis-backed distributed state |
| aiomisc | 17.x | Utilities including circuit breaker | If already using aiomisc elsewhere |
| xxhash | 3.x | Fast file hashing | For cache key generation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| diskcache | aiocache | aiocache better for Redis/memcached, diskcache better for local file |
| tenacity | backoff | backoff simpler but tenacity more flexible |
| purgatory | aiobreaker | aiobreaker inactive since 2023, purgatory actively maintained |

**Installation:**
```bash
pip install tenacity diskcache pytest-asyncio xxhash
# Optional for distributed circuit breaker:
pip install purgatory-circuitbreaker
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
~/.claude/templates/validation/
├── resilience/
│   ├── __init__.py           # Exports circuit_breaker, retry_with_timeout
│   ├── circuit_breaker.py    # CircuitBreakerRegistry for all integration points
│   ├── cache.py              # ValidationCache with file hash keys
│   └── timeout.py            # Configurable timeout wrapper
├── orchestrator.py           # Uses resilience module
└── tests/
    ├── e2e/
    │   ├── test_spawn_agent_live.py  # Real MCP integration
    │   ├── test_full_validation.py   # End-to-end flow
    │   └── conftest.py               # E2E fixtures
    └── test_orchestrator.py          # Unit tests (existing)
```

### Pattern 1: Tenacity Retry with Circuit Breaker
**What:** Combine tenacity's retry with manual circuit breaker state
**When to use:** External service calls (MCP, QuestDB, Prometheus)
**Example:**
```python
# Source: tenacity docs + pybreaker pattern
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CircuitState:
    failures: int = 0
    last_failure: datetime | None = None
    state: str = "closed"  # closed, open, half-open

    FAIL_MAX = 5
    RESET_TIMEOUT = timedelta(seconds=60)

    def record_failure(self):
        self.failures += 1
        self.last_failure = datetime.now()
        if self.failures >= self.FAIL_MAX:
            self.state = "open"

    def record_success(self):
        self.failures = 0
        self.state = "closed"

    def should_attempt(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if datetime.now() - self.last_failure > self.RESET_TIMEOUT:
                self.state = "half-open"
                return True
            return False
        return True  # half-open

# Registry of circuit breakers
BREAKERS: dict[str, CircuitState] = {}

def get_breaker(name: str) -> CircuitState:
    if name not in BREAKERS:
        BREAKERS[name] = CircuitState()
    return BREAKERS[name]

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
)
async def call_with_breaker(name: str, coro):
    breaker = get_breaker(name)
    if not breaker.should_attempt():
        raise CircuitOpenError(f"Circuit {name} is open")
    try:
        result = await coro
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        raise
```

### Pattern 2: File Hash-Based Caching
**What:** Skip validation for unchanged files using content hash
**When to use:** Incremental validation runs
**Example:**
```python
# Source: diskcache docs + mypy cache pattern
import diskcache
import xxhash
from pathlib import Path

class ValidationCache:
    def __init__(self, cache_dir: Path = Path.home() / ".cache" / "validation"):
        self.cache = diskcache.Cache(str(cache_dir))
        self.config_hash = None

    def _file_hash(self, path: Path) -> str:
        """Fast content hash using xxhash."""
        h = xxhash.xxh64()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _cache_key(self, file_path: Path, dimension: str) -> str:
        """Cache key = file_hash + config_hash + dimension."""
        file_hash = self._file_hash(file_path)
        return f"{file_hash}:{self.config_hash}:{dimension}"

    def get(self, file_path: Path, dimension: str) -> dict | None:
        """Get cached result if file unchanged."""
        key = self._cache_key(file_path, dimension)
        return self.cache.get(key)

    def set(self, file_path: Path, dimension: str, result: dict, ttl: int = 86400):
        """Cache result with 24h TTL."""
        key = self._cache_key(file_path, dimension)
        self.cache.set(key, result, expire=ttl)

    def invalidate_config(self, config: dict):
        """Invalidate cache when config changes."""
        import json
        self.config_hash = xxhash.xxh64(json.dumps(config, sort_keys=True).encode()).hexdigest()
```

### Pattern 3: Graceful Degradation with Partial Results
**What:** Return partial results when some validators fail
**When to use:** Always - never hang on validator failure
**Example:**
```python
# Source: asyncio best practices
import asyncio
from typing import NamedTuple

class ValidatorOutcome(NamedTuple):
    name: str
    result: ValidationResult | None
    error: Exception | None

async def run_validators_with_timeout(
    validators: list[tuple[str, BaseValidator]],
    timeout_seconds: float = 30.0,
) -> list[ValidatorOutcome]:
    """Run validators with individual timeouts, return partial results on failure."""

    async def run_one(name: str, validator: BaseValidator) -> ValidatorOutcome:
        try:
            result = await asyncio.wait_for(
                validator.validate(),
                timeout=validator.timeout or timeout_seconds
            )
            return ValidatorOutcome(name, result, None)
        except asyncio.TimeoutError as e:
            return ValidatorOutcome(name, None, TimeoutError(f"{name} timed out"))
        except Exception as e:
            return ValidatorOutcome(name, None, e)

    outcomes = await asyncio.gather(
        *[run_one(name, v) for name, v in validators],
        return_exceptions=False  # We handle exceptions inside run_one
    )

    return outcomes
```

### Anti-Patterns to Avoid
- **Global try/except that swallows all errors:** Makes debugging impossible
- **Hardcoded timeouts:** Should be configurable per validator type
- **No circuit breaker on external calls:** Leads to cascade failures
- **Cache by mtime instead of content hash:** Unreliable across machines
- **asyncio.gather without return_exceptions:** One failure cancels all
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Custom sleep loops | tenacity | Edge cases: jitter, max attempts, exception filtering |
| File caching | Custom pickle/json files | diskcache | Handles corruption, TTL, concurrent access |
| Fast file hashing | hashlib.md5 | xxhash | 10x faster for large files |
| Circuit breaker | Simple counter | tenacity + state class | State machine complexity, half-open state |
| Async timeout | manual asyncio.sleep | asyncio.wait_for | Proper cancellation handling |

**Key insight:** The orchestrator already has 40+ validators. Adding resilience to each manually is error-prone. A centralized resilience module with decorators/wrappers ensures consistency.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Flaky E2E Tests
**What goes wrong:** E2E tests pass locally but fail in CI due to MCP server timing
**Why it happens:** No retry on MCP connection, hardcoded timeouts
**How to avoid:** Use tenacity retry on MCP connection, pytest-asyncio fixtures with proper cleanup
**Warning signs:** Tests that "usually pass" or need re-runs

### Pitfall 2: Cache Stampede
**What goes wrong:** Multiple validators regenerate cache simultaneously
**Why it happens:** Cache expires at same time for all validators
**How to avoid:** Use diskcache's `@cache.memoize(expire=1)` with `@dc.barrier`
**Warning signs:** Sudden CPU spikes when cache expires

### Pitfall 3: Circuit Breaker Configuration
**What goes wrong:** Circuit opens too aggressively (5 failures in 10 seconds ≠ 5 failures in 10 minutes)
**Why it happens:** Default fail_max=5 without considering failure rate
**How to avoid:** Configure reset_timeout based on actual recovery time of service
**Warning signs:** Circuit "flapping" between open/closed

### Pitfall 4: Timeout vs Circuit Breaker Confusion
**What goes wrong:** Timeout triggers but circuit doesn't open
**Why it happens:** TimeoutError not in circuit breaker's exception list
**How to avoid:** Include TimeoutError in circuit breaker's tracked exceptions
**Warning signs:** Repeated timeouts without circuit opening

### Pitfall 5: pytest-asyncio 1.0 Migration
**What goes wrong:** Tests fail after upgrading pytest-asyncio
**Why it happens:** `event_loop` fixture removed in 1.0, scope handling changed
**How to avoid:** Use `asyncio_default_fixture_loop_scope = function` in pytest.ini
**Warning signs:** "event_loop fixture not found" errors
</common_pitfalls>

<code_examples>
## Code Examples

Verified patterns from official sources:

### Tenacity Async Retry with Stop Conditions
```python
# Source: tenacity README
from tenacity import retry, stop_after_delay, stop_after_attempt, wait_exponential

@retry(
    stop=(stop_after_delay(10) | stop_after_attempt(5)),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def call_external_service():
    # Stops after 10 seconds OR 5 attempts
    # Wait 2^x * 1 second between retries (min 4s, max 10s)
    pass
```

### DiskCache with Stampede Protection
```python
# Source: diskcache case study
import diskcache as dc

cache = dc.Cache('/tmp/validation-cache')

@cache.memoize(expire=0)  # Outer: no expiry
@dc.barrier(cache, dc.Lock)  # Synchronize concurrent workers
@cache.memoize(expire=3600)  # Inner: 1 hour expiry
def expensive_validation(file_path: str, dimension: str):
    # Only one worker regenerates when cache expires
    pass
```

### pytest-asyncio 1.x Fixture Pattern
```python
# Source: pytest-asyncio docs
import pytest
import pytest_asyncio

# pytest.ini: asyncio_mode = "auto"

@pytest_asyncio.fixture
async def mcp_client():
    """Async fixture for MCP client with proper cleanup."""
    client = await create_mcp_connection()
    yield client
    await client.close()

async def test_spawn_agent(mcp_client):
    """E2E test with real MCP."""
    result = await mcp_client.spawn_agent("test-agent", "do something")
    assert result.success
```

### Graceful Shutdown with Signal Handling
```python
# Source: python-graceful-shutdown
import asyncio
import signal

class GracefulOrchestrator:
    def __init__(self):
        self.shutdown_event = asyncio.Event()

    async def run(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.shutdown_event.set)

        try:
            await self._run_validation()
        finally:
            await self._cleanup()

    async def _cleanup(self):
        """Graceful cleanup - close connections, flush caches."""
        pass
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pybreaker with Tornado | aiobreaker/purgatory with native asyncio | 2023 | Native async support |
| pytest-asyncio event_loop fixture | Scoped event loops, no event_loop | May 2025 (v1.0) | Simpler test setup |
| mtime-based cache invalidation | Content hash (xxhash) | 2024 | Reliable across machines |
| asyncio.gather for parallel | asyncio.TaskGroup (3.11+) | 2022 | Better error handling |

**New tools/patterns to consider:**
- **structlog:** Structured logging for better observability
- **asyncio.timeout():** Python 3.11+ timeout context manager (replaces wait_for in some cases)
- **TaskGroup:** Python 3.11+ structured concurrency (better than gather for error handling)

**Deprecated/outdated:**
- **aiobreaker:** Inactive maintenance since 2023, use purgatory instead
- **event_loop fixture:** Removed in pytest-asyncio 1.0
- **bare asyncio.gather:** Prefer TaskGroup for production code
</sota_updates>

<open_questions>
## Open Questions

Things that couldn't be fully resolved:

1. **MCP Server Availability in E2E Tests**
   - What we know: claude-flow MCP is configured in ~/.mcp.json
   - What's unclear: How to reliably start/stop MCP for E2E tests in CI
   - Recommendation: Use environment variable to skip MCP tests in CI, run full E2E locally

2. **Cache Storage Location**
   - What we know: diskcache defaults to /tmp or custom path
   - What's unclear: Should cache be per-project or global?
   - Recommendation: Global cache (~/.cache/validation) with project-scoped keys

3. **Circuit Breaker State Persistence**
   - What we know: In-memory state resets on process restart
   - What's unclear: Do we need Redis-backed distributed state?
   - Recommendation: Start with in-memory, add Redis if multi-process validation needed
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [tenacity GitHub /jd/tenacity](https://github.com/jd/tenacity) - retry patterns, stop conditions, async support
- [diskcache GitHub /grantjenks/python-diskcache](https://github.com/grantjenks/python-diskcache) - caching, memoization, stampede protection
- [pybreaker GitHub /danielfm/pybreaker](https://github.com/danielfm/pybreaker) - circuit breaker basics, state machine
- [pytest-asyncio docs](https://pytest-asyncio.readthedocs.io/en/stable/) - async fixtures, event loop scope

### Secondary (MEDIUM confidence)
- [pytest-asyncio 1.0 migration guide](https://thinhdanggroup.github.io/pytest-asyncio-v1-migrate/) - verified against official docs
- [Building Resilient Python Apps with Tenacity](https://www.amitavroy.com/articles/building-resilient-python-applications-with-tenacity-smart-retries-for-a-fail-proof-architecture) - verified patterns
- [aiobreaker GitHub /arlyon/aiobreaker](https://github.com/arlyon/aiobreaker) - async circuit breaker (note: inactive maintenance)

### Tertiary (LOW confidence - needs validation)
- [purgatory GitHub /mardiros/purgatory](https://github.com/mardiros/purgatory) - mentioned as actively maintained alternative
- [aiomisc circuit breaker docs](https://aiomisc.readthedocs.io/en/latest/circuit_breaker.html) - if already using aiomisc
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Python asyncio resilience patterns
- Ecosystem: tenacity, diskcache, pybreaker, pytest-asyncio
- Patterns: Circuit breaker, retry with backoff, file hash caching, graceful degradation
- Pitfalls: Flaky tests, cache stampede, circuit configuration, timeout handling

**Confidence breakdown:**
- Standard stack: HIGH - all from Context7 with high reputation scores
- Architecture: HIGH - patterns from official docs
- Pitfalls: HIGH - documented issues verified in multiple sources
- Code examples: HIGH - from Context7/official sources

**Research date:** 2026-01-26
**Valid until:** 2026-02-26 (30 days - Python ecosystem stable)
</metadata>

---

*Phase: 19-production-hardening*
*Research completed: 2026-01-26*
*Ready for planning: yes*
