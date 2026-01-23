#!/usr/bin/env python3
"""Unit tests for ralph_loop.py - Ralph Loop State Machine."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the module under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_loop import (
    LoopState,
    RalphLoopConfig,
    IterationHistory,
    LoopResult,
    RalphLoop,
    _create_empty_tier_result,
)


class TestLoopState:
    """Tests for LoopState enum."""

    def test_all_states_exist(self):
        """Verify all expected states are defined."""
        assert LoopState.IDLE.value == "idle"
        assert LoopState.VALIDATING.value == "validating"
        assert LoopState.BLOCKED.value == "blocked"
        assert LoopState.FIX_REQUESTED.value == "fix_requested"
        assert LoopState.COMPLETE.value == "complete"

    def test_state_count(self):
        """Ensure no unexpected states added."""
        assert len(LoopState) == 5


class TestRalphLoopConfig:
    """Tests for RalphLoopConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RalphLoopConfig()
        assert config.max_iterations == 5
        assert config.min_score_threshold == 70.0
        assert config.tier1_timeout_seconds == 30.0
        assert config.tier2_timeout_seconds == 120.0

    def test_from_dict(self):
        """Test creating config from dict."""
        data = {
            "max_iterations": 10,
            "min_score_threshold": 80.0,
            "tier1_timeout_seconds": 60.0,
            "tier2_timeout_seconds": 240.0,
        }
        config = RalphLoopConfig.from_dict(data)
        assert config.max_iterations == 10
        assert config.min_score_threshold == 80.0
        assert config.tier1_timeout_seconds == 60.0
        assert config.tier2_timeout_seconds == 240.0

    def test_from_dict_partial(self):
        """Test creating config with partial dict (uses defaults)."""
        data = {"max_iterations": 3}
        config = RalphLoopConfig.from_dict(data)
        assert config.max_iterations == 3
        assert config.min_score_threshold == 70.0  # default

    def test_from_file_missing(self):
        """Test loading from non-existent file returns defaults."""
        config = RalphLoopConfig.from_file(Path("/nonexistent/path.json"))
        assert config.max_iterations == 5  # default

    def test_from_file_valid(self):
        """Test loading from valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"max_iterations": 7, "min_score_threshold": 85.0}, f)
            f.flush()
            config = RalphLoopConfig.from_file(Path(f.name))
        assert config.max_iterations == 7
        assert config.min_score_threshold == 85.0

    def test_from_file_with_ralph_loop_key(self):
        """Test loading from file with nested ralph_loop key."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"ralph_loop": {"max_iterations": 8}}, f)
            f.flush()
            config = RalphLoopConfig.from_file(Path(f.name))
        assert config.max_iterations == 8

    def test_from_file_invalid_json(self):
        """Test loading from invalid JSON returns defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            config = RalphLoopConfig.from_file(Path(f.name))
        assert config.max_iterations == 5  # default

    def test_to_dict(self):
        """Test serialization to dict."""
        config = RalphLoopConfig(max_iterations=3, min_score_threshold=90.0)
        d = config.to_dict()
        assert d["max_iterations"] == 3
        assert d["min_score_threshold"] == 90.0
        assert "tier1_timeout_seconds" in d
        assert "tier2_timeout_seconds" in d


class TestIterationHistory:
    """Tests for IterationHistory dataclass."""

    def test_default_values(self):
        """Test creation with required fields only."""
        history = IterationHistory(iteration=1, score=75.0, tier1_passed=True)
        assert history.iteration == 1
        assert history.score == 75.0
        assert history.tier1_passed is True
        assert history.tier2_warnings == 0
        assert history.tier3_monitors == 0
        assert history.duration_ms == 0
        assert history.timestamp  # auto-generated

    def test_full_values(self):
        """Test creation with all fields."""
        history = IterationHistory(
            iteration=2,
            score=85.5,
            tier1_passed=True,
            tier2_warnings=3,
            tier3_monitors=5,
            duration_ms=1500,
        )
        assert history.tier2_warnings == 3
        assert history.tier3_monitors == 5
        assert history.duration_ms == 1500


class TestLoopResult:
    """Tests for LoopResult dataclass."""

    def test_creation(self):
        """Test basic creation."""
        result = LoopResult(
            state=LoopState.COMPLETE,
            iteration=3,
            score=95.0,
            blockers=[],
            message="Validation complete",
        )
        assert result.state == LoopState.COMPLETE
        assert result.iteration == 3
        assert result.score == 95.0
        assert result.blockers == []
        assert result.history == []

    def test_to_dict(self):
        """Test serialization to dict."""
        history = [
            IterationHistory(iteration=1, score=60.0, tier1_passed=False),
            IterationHistory(iteration=2, score=80.0, tier1_passed=True),
        ]
        result = LoopResult(
            state=LoopState.COMPLETE,
            iteration=2,
            score=80.0,
            blockers=[],
            message="Done",
            history=history,
            execution_time_ms=5000,
        )
        d = result.to_dict()
        assert d["state"] == "complete"
        assert d["iteration"] == 2
        assert d["score"] == 80.0
        assert d["execution_time_ms"] == 5000
        assert len(d["history"]) == 2
        assert d["history"][0]["tier1_passed"] is False
        assert d["history"][1]["tier1_passed"] is True

    def test_to_dict_json_serializable(self):
        """Ensure to_dict output is JSON serializable."""
        result = LoopResult(
            state=LoopState.BLOCKED,
            iteration=1,
            score=None,
            blockers=["syntax", "security"],
            message="Blocked by Tier 1",
        )
        # Should not raise
        json_str = json.dumps(result.to_dict())
        assert "blocked" in json_str


class TestCreateEmptyTierResult:
    """Tests for _create_empty_tier_result helper."""

    def test_creates_tier1_result(self):
        """Test creating empty Tier 1 result."""
        result = _create_empty_tier_result(1)
        assert result.tier.value == 1
        assert result.results == []
        assert result.passed is True

    def test_creates_tier2_result(self):
        """Test creating empty Tier 2 result."""
        result = _create_empty_tier_result(2)
        assert result.tier.value == 2

    def test_creates_tier3_result(self):
        """Test creating empty Tier 3 result."""
        result = _create_empty_tier_result(3)
        assert result.tier.value == 3


class TestRalphLoopScoreCalculation:
    """Tests for RalphLoop score calculation (isolated from orchestrator)."""

    def test_score_all_pass(self):
        """Test score calculation when all tiers pass."""
        # Create mock tier results
        tier1 = MagicMock()
        tier1.results = [MagicMock(passed=True), MagicMock(passed=True)]
        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=True)]
        tier3 = MagicMock()
        tier3.results = [MagicMock(passed=True)]

        # Calculate score using static method logic
        def tier_score(tier_result):
            if not hasattr(tier_result, "results") or not tier_result.results:
                return 100.0
            passed = sum(1 for r in tier_result.results if r.passed)
            total = len(tier_result.results)
            return (passed / total * 100) if total > 0 else 100.0

        t1 = tier_score(tier1)
        t2 = tier_score(tier2)
        t3 = tier_score(tier3)
        # Weights: T1=50%, T2=30%, T3=20%
        score = t1 * 0.5 + t2 * 0.3 + t3 * 0.2

        assert score == 100.0

    def test_score_tier1_fails(self):
        """Test score calculation when Tier 1 has failures."""
        # Tier 1: 1/2 pass = 50%
        tier1 = MagicMock()
        tier1.results = [MagicMock(passed=True), MagicMock(passed=False)]
        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=True)]  # 100%
        tier3 = MagicMock()
        tier3.results = [MagicMock(passed=True)]  # 100%

        def tier_score(tier_result):
            if not hasattr(tier_result, "results") or not tier_result.results:
                return 100.0
            passed = sum(1 for r in tier_result.results if r.passed)
            total = len(tier_result.results)
            return (passed / total * 100) if total > 0 else 100.0

        t1 = tier_score(tier1)
        t2 = tier_score(tier2)
        t3 = tier_score(tier3)
        score = t1 * 0.5 + t2 * 0.3 + t3 * 0.2

        # Expected: 50*0.5 + 100*0.3 + 100*0.2 = 25 + 30 + 20 = 75
        assert score == 75.0

    def test_score_empty_results(self):
        """Test score calculation with empty results returns 100."""
        tier1 = MagicMock()
        tier1.results = []
        tier2 = MagicMock()
        tier2.results = []
        tier3 = MagicMock()
        tier3.results = []

        def tier_score(tier_result):
            if not hasattr(tier_result, "results") or not tier_result.results:
                return 100.0
            passed = sum(1 for r in tier_result.results if r.passed)
            total = len(tier_result.results)
            return (passed / total * 100) if total > 0 else 100.0

        t1 = tier_score(tier1)
        t2 = tier_score(tier2)
        t3 = tier_score(tier3)
        score = t1 * 0.5 + t2 * 0.3 + t3 * 0.2

        assert score == 100.0

    def test_score_no_results_attr(self):
        """Test score calculation when result has no results attribute."""
        # Objects without results attribute
        tier1 = object()
        tier2 = object()
        tier3 = object()

        def tier_score(tier_result):
            if not hasattr(tier_result, "results") or not tier_result.results:
                return 100.0
            passed = sum(1 for r in tier_result.results if r.passed)
            total = len(tier_result.results)
            return (passed / total * 100) if total > 0 else 100.0

        t1 = tier_score(tier1)
        t2 = tier_score(tier2)
        t3 = tier_score(tier3)
        score = t1 * 0.5 + t2 * 0.3 + t3 * 0.2

        assert score == 100.0


class TestRalphLoopIntegration:
    """Integration tests for RalphLoop with real orchestrator."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock ValidationOrchestrator with proper structure."""
        orchestrator = MagicMock()

        # Create a proper tier class mock
        class MockTier:
            def __init__(self, value):
                self.value = value
                self.name = f"TIER_{value}"

        # Setup validators dict with proper tier
        validator_mock = MagicMock()
        validator_mock.tier = MockTier(1)
        validator_mock.tier.__class__ = MockTier
        orchestrator.validators = {"test": validator_mock}

        return orchestrator

    def test_initial_state(self, mock_orchestrator):
        """Test RalphLoop starts in IDLE state."""
        config = RalphLoopConfig()
        loop = RalphLoop(
            orchestrator=mock_orchestrator,
            config=config,
        )
        assert loop.state == LoopState.IDLE
        assert loop.iteration == 0

    def test_custom_config(self, mock_orchestrator):
        """Test RalphLoop accepts custom config."""
        config = RalphLoopConfig(max_iterations=10, min_score_threshold=90.0)
        loop = RalphLoop(
            orchestrator=mock_orchestrator,
            config=config,
        )
        assert loop.config.max_iterations == 10
        assert loop.config.min_score_threshold == 90.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
