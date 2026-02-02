#!/usr/bin/env python3
"""
OSSReuseValidator - Tier 2 OSS Package Suggestion Validator

Detects reimplemented patterns and suggests well-maintained OSS packages.
Uses pattern-based detection with confidence scoring.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# Import patterns (with fallback for standalone testing)
try:
    from .patterns import OSS_PATTERNS
except ImportError:
    from patterns import OSS_PATTERNS


# Standalone types for testing (orchestrator imports these when available)
class ValidationTier(Enum):
    BLOCKER = 1
    WARNING = 2
    MONITOR = 3


@dataclass
class ValidationResult:
    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None
    duration_ms: int = 0


class BaseValidator:
    dimension = "unknown"
    tier = ValidationTier.MONITOR
    agent = None


@dataclass
class PatternMatch:
    """A detected pattern match."""

    pattern_name: str
    file_path: str
    line_number: int
    match_text: str
    suggestion: str
    reason: str
    confidence: str


class OSSReuseValidator(BaseValidator):
    """
    Tier 2: OSS reuse suggestions for reimplemented patterns.

    Scans Python files for common patterns that could be replaced
    with well-maintained OSS packages.
    """

    dimension = "oss_reuse"
    tier = ValidationTier.WARNING
    agent = None  # No auto-fix agent for this

    # Confidence levels: high > medium > low
    CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.min_confidence = self.config.get("min_confidence", "medium")

    async def validate(self) -> ValidationResult:
        """Scan Python files for reimplemented patterns."""
        start = datetime.now()

        matches = []
        files_scanned = 0

        # Scan Python files in current directory
        for py_file in Path(".").rglob("*.py"):
            # Skip common non-source directories
            if any(
                part.startswith(".")
                or part
                in (
                    "venv",
                    "env",
                    "__pycache__",
                    "node_modules",
                    ".git",
                    "build",
                    "dist",
                    ".eggs",
                )
                for part in py_file.parts
            ):
                continue

            try:
                content = py_file.read_text()
                files_scanned += 1
                file_matches = self._scan_file(py_file, content)
                matches.extend(file_matches)
            except Exception:
                continue

        # Filter by confidence threshold
        min_level = self.CONFIDENCE_ORDER.get(self.min_confidence, 2)
        filtered_matches = [
            m
            for m in matches
            if self.CONFIDENCE_ORDER.get(m.confidence, 0) >= min_level
        ]

        passed = len(filtered_matches) == 0

        # Build suggestion message
        suggestions = []
        for m in filtered_matches[:5]:  # Top 5 suggestions
            suggestions.append(
                f"{m.file_path}:{m.line_number} - {m.pattern_name}: use {m.suggestion}"
            )

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message=(
                f"{len(filtered_matches)} OSS suggestions"
                if not passed
                else "No reimplementations detected"
            ),
            details={
                "files_scanned": files_scanned,
                "total_matches": len(matches),
                "filtered_matches": len(filtered_matches),
                "suggestions": [self._match_to_dict(m) for m in filtered_matches[:10]],
            },
            fix_suggestion="\n".join(suggestions) if suggestions else None,
            duration_ms=duration_ms,
        )

    def _scan_file(self, file_path: Path, content: str) -> list[PatternMatch]:
        """Scan a single file for patterns."""
        matches = []
        lines = content.split("\n")

        for pattern_name, pattern_config in OSS_PATTERNS.items():
            for pattern in pattern_config["patterns"]:
                try:
                    regex = re.compile(pattern)
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            # Check if already using the suggested package
                            if not self._already_using_suggestion(
                                content, pattern_config["suggestion"]
                            ):
                                matches.append(
                                    PatternMatch(
                                        pattern_name=pattern_name,
                                        file_path=str(file_path),
                                        line_number=i,
                                        match_text=line.strip()[:80],
                                        suggestion=pattern_config["suggestion"],
                                        reason=pattern_config["reason"],
                                        confidence=pattern_config["confidence"],
                                    )
                                )
                except re.error:
                    continue

        return matches

    def _already_using_suggestion(self, content: str, suggestion: str) -> bool:
        """Check if file already imports the suggested package."""
        # Handle "X or Y" suggestions
        packages = suggestion.replace(" or ", ",").replace(" ", "").split(",")
        for pkg in packages:
            # Handle special cases like "yaml.safe_load"
            if "." in pkg and not pkg.startswith("Use "):
                pkg_base = pkg.split(".")[0]
            else:
                pkg_base = pkg.split()[0] if " " in pkg else pkg

            # Skip non-package suggestions like "Use yaml.safe_load()"
            if pkg_base.lower() in ("use", "subprocess.run"):
                continue

            pkg_base = pkg_base.replace("-", "_")
            if re.search(rf"^\s*(import|from)\s+{pkg_base}", content, re.MULTILINE):
                return True
        return False

    def _match_to_dict(self, m: PatternMatch) -> dict:
        """Convert PatternMatch to dict for serialization."""
        return {
            "pattern_name": m.pattern_name,
            "file_path": m.file_path,
            "line_number": m.line_number,
            "match_text": m.match_text,
            "suggestion": m.suggestion,
            "reason": m.reason,
            "confidence": m.confidence,
        }


__all__ = ["OSSReuseValidator", "PatternMatch"]
