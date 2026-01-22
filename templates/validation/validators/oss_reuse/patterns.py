"""OSS pattern definitions for common reimplementations."""

OSS_PATTERNS = {
    "date_parsing": {
        "patterns": [r"strptime\s*\(", r"parse.*date", r"datetime\.strptime"],
        "suggestion": "python-dateutil",
        "reason": "Handles edge cases like timezones, relative dates",
        "confidence": "medium",  # strptime is sometimes fine
    },
    "http_client": {
        "patterns": [r"urllib\.request", r"http\.client\.HTTP", r"socket.*connect"],
        "suggestion": "requests or httpx",
        "reason": "Better API, connection pooling, retries",
        "confidence": "high",
    },
    "json_validation": {
        "patterns": [
            r"validate.*schema",
            r"isinstance.*dict.*for",
            r"if\s+['\"]type['\"]\s+in",
        ],
        "suggestion": "jsonschema or pydantic",
        "reason": "Battle-tested validation with error messages",
        "confidence": "medium",
    },
    "yaml_unsafe": {
        "patterns": [r"yaml\.load\s*\([^,)]+\)", r"yaml\.load\(\s*[^,]+\s*\)"],
        "suggestion": "Use yaml.safe_load() instead",
        "reason": "yaml.load() allows arbitrary code execution",
        "confidence": "high",
    },
    "cli_args_manual": {
        "patterns": [r"sys\.argv\[(?!0\])", r"for\s+arg\s+in\s+sys\.argv"],
        "suggestion": "click or typer",
        "reason": "Automatic help, type conversion, validation",
        "confidence": "high",
    },
    "retry_manual": {
        "patterns": [
            r"while.*retry",
            r"for.*attempt.*in.*range",
            r"except.*sleep.*continue",
        ],
        "suggestion": "tenacity",
        "reason": "Configurable backoff, jitter, retry conditions",
        "confidence": "medium",
    },
    "cache_dict": {
        "patterns": [
            r"cache\s*=\s*\{\}",
            r"_cache\s*=\s*\{\}",
            r"if\s+\w+\s+not\s+in\s+cache",
        ],
        "suggestion": "functools.lru_cache or cachetools",
        "reason": "LRU eviction, TTL, thread safety",
        "confidence": "medium",
    },
    "env_manual": {
        "patterns": [
            r"os\.environ\.get\s*\(\s*['\"][A-Z_]+['\"]\s*\)",
            r"os\.getenv\s*\(\s*['\"][A-Z_]+['\"]\s*\)",
        ],
        "suggestion": "pydantic-settings or python-dotenv",
        "reason": "Typed settings, validation, .env file support",
        "confidence": "low",  # os.environ.get is often fine
    },
    "subprocess_shell": {
        "patterns": [r"subprocess\..*shell\s*=\s*True", r"os\.system\s*\("],
        "suggestion": "subprocess.run with shell=False",
        "reason": "Security: shell injection risk",
        "confidence": "high",
    },
    "path_join": {
        "patterns": [r"os\.path\.join\s*\("],
        "suggestion": "pathlib.Path (stdlib)",
        "reason": "Object-oriented API, cross-platform",
        "confidence": "low",  # os.path.join is fine, just older style
    },
}

__all__ = ["OSS_PATTERNS"]
