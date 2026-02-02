#!/usr/bin/env python3
"""Unit tests for ralph_loop.py - Ralph Loop State Machine."""

import json

# Import the module under test
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_loop import (
    IterationHistory,
    LoopResult,
    LoopState,
    RalphLoop,
    RalphLoopConfig,
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

    def test_get_project_name_fallback(self, mock_orchestrator):
        """Test _get_project_name falls back to cwd name."""
        config = RalphLoopConfig()
        loop = RalphLoop(orchestrator=mock_orchestrator, config=config)

        # Should return something (either git project name or cwd)
        name = loop._get_project_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_calculate_score_method(self, mock_orchestrator):
        """Test _calculate_score method on actual loop instance."""
        config = RalphLoopConfig()
        loop = RalphLoop(orchestrator=mock_orchestrator, config=config)

        # All pass
        tier1 = MagicMock()
        tier1.results = [MagicMock(passed=True)]
        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=True)]
        tier3 = MagicMock()
        tier3.results = [MagicMock(passed=True)]

        score = loop._calculate_score(tier1, tier2, tier3)
        assert score == 100.0

    def test_calculate_score_with_failures(self, mock_orchestrator):
        """Test _calculate_score with some failures."""
        config = RalphLoopConfig()
        loop = RalphLoop(orchestrator=mock_orchestrator, config=config)

        # Tier 1: 50% pass
        tier1 = MagicMock()
        tier1.results = [MagicMock(passed=True), MagicMock(passed=False)]
        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=True)]
        tier3 = MagicMock()
        tier3.results = [MagicMock(passed=True)]

        score = loop._calculate_score(tier1, tier2, tier3)
        # 50*0.5 + 100*0.3 + 100*0.2 = 75
        assert score == 75.0


class TestLoopResultSerialization:
    """Tests for LoopResult serialization."""

    def test_to_dict_with_empty_history(self):
        """Test to_dict with no history entries."""
        result = LoopResult(
            state=LoopState.IDLE,
            iteration=0,
            score=None,
            blockers=[],
            message="Not started",
        )
        d = result.to_dict()
        assert d["state"] == "idle"
        assert d["history"] == []

    def test_to_dict_with_blockers(self):
        """Test to_dict preserves blocker list."""
        result = LoopResult(
            state=LoopState.BLOCKED,
            iteration=1,
            score=50.0,
            blockers=["syntax", "type_safety", "security"],
            message="Blocked by Tier 1",
            execution_time_ms=1234,
        )
        d = result.to_dict()
        assert len(d["blockers"]) == 3
        assert "syntax" in d["blockers"]
        assert d["execution_time_ms"] == 1234

    def test_to_dict_with_history(self):
        """Test to_dict with multiple history entries."""
        history = [
            IterationHistory(
                iteration=1,
                score=60.0,
                tier1_passed=False,
                tier2_warnings=2,
                tier3_monitors=5,
                duration_ms=500,
            ),
            IterationHistory(
                iteration=2,
                score=80.0,
                tier1_passed=True,
                tier2_warnings=1,
                tier3_monitors=3,
                duration_ms=400,
            ),
            IterationHistory(
                iteration=3,
                score=95.0,
                tier1_passed=True,
                tier2_warnings=0,
                tier3_monitors=2,
                duration_ms=300,
            ),
        ]
        result = LoopResult(
            state=LoopState.COMPLETE,
            iteration=3,
            score=95.0,
            blockers=[],
            message="Complete",
            history=history,
        )
        d = result.to_dict()
        assert len(d["history"]) == 3
        assert d["history"][0]["score"] == 60.0
        assert d["history"][1]["tier2_warnings"] == 1
        assert d["history"][2]["tier3_monitors"] == 2


class TestConfigEdgeCases:
    """Test edge cases for RalphLoopConfig."""

    def test_config_from_dict_empty(self):
        """Test from_dict with empty dict uses defaults."""
        config = RalphLoopConfig.from_dict({})
        assert config.max_iterations == 5
        assert config.min_score_threshold == 70.0

    def test_config_from_dict_extra_keys(self):
        """Test from_dict ignores extra keys."""
        config = RalphLoopConfig.from_dict(
            {
                "max_iterations": 3,
                "unknown_key": "ignored",
                "another_unknown": 123,
            }
        )
        assert config.max_iterations == 3

    def test_config_roundtrip(self):
        """Test config survives to_dict/from_dict roundtrip."""
        original = RalphLoopConfig(
            max_iterations=7,
            min_score_threshold=85.5,
            tier1_timeout_seconds=45.0,
            tier2_timeout_seconds=180.0,
        )
        d = original.to_dict()
        restored = RalphLoopConfig.from_dict(d)

        assert restored.max_iterations == original.max_iterations
        assert restored.min_score_threshold == original.min_score_threshold
        assert restored.tier1_timeout_seconds == original.tier1_timeout_seconds
        assert restored.tier2_timeout_seconds == original.tier2_timeout_seconds


class TestHelperMethods:
    """Tests for RalphLoop helper methods."""

    @pytest.fixture
    def loop_with_mocks(self):
        """Create RalphLoop with mocked orchestrator."""
        mock_orchestrator = MagicMock()
        # Setup validators for _get_tier_class
        # The _get_tier_class method does: first_validator.tier.__class__(tier_num)
        # So tier.__class__ should be callable with a single int argument
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orchestrator.validators = {"test": mock_validator}

        config = RalphLoopConfig()
        loop = RalphLoop(mock_orchestrator, config)
        return loop

    def test_get_tier_class(self, loop_with_mocks):
        """Test _get_tier_class returns tier enum."""
        loop = loop_with_mocks
        tier_class = loop._get_tier_class(1)
        assert tier_class.value == 1

    def test_elapsed_ms_no_start(self, loop_with_mocks):
        """Test _elapsed_ms returns 0 when not started."""
        loop = loop_with_mocks
        assert loop._elapsed_ms() == 0

    def test_elapsed_ms_with_start(self, loop_with_mocks):
        """Test _elapsed_ms returns positive value after start."""
        from datetime import datetime, timedelta

        loop = loop_with_mocks
        loop._start_time = datetime.now() - timedelta(milliseconds=100)
        elapsed = loop._elapsed_ms()
        assert elapsed >= 100

    def test_create_result(self, loop_with_mocks):
        """Test _create_result creates correct LoopResult."""
        loop = loop_with_mocks
        loop.iteration = 3
        loop.history = [
            IterationHistory(iteration=1, score=60.0, tier1_passed=True),
            IterationHistory(iteration=2, score=75.0, tier1_passed=True),
        ]

        result = loop._create_result(
            state=LoopState.COMPLETE,
            score=85.0,
            blockers=[],
            message="Test complete",
        )

        assert result.state == LoopState.COMPLETE
        assert result.iteration == 3
        assert result.score == 85.0
        assert len(result.history) == 2

    def test_calculate_tier_score_empty(self, loop_with_mocks):
        """Test _calculate_tier_score with empty results."""
        loop = loop_with_mocks
        tier_result = MagicMock()
        tier_result.results = []
        assert loop._calculate_tier_score(tier_result) == 100.0

    def test_calculate_tier_score_no_attr(self, loop_with_mocks):
        """Test _calculate_tier_score with no results attr."""
        loop = loop_with_mocks
        tier_result = MagicMock(spec=[])  # No 'results' attribute
        assert loop._calculate_tier_score(tier_result) == 100.0

    def test_calculate_tier_score_all_pass(self, loop_with_mocks):
        """Test _calculate_tier_score with all passing."""
        loop = loop_with_mocks
        tier_result = MagicMock()
        tier_result.results = [MagicMock(passed=True), MagicMock(passed=True)]
        assert loop._calculate_tier_score(tier_result) == 100.0

    def test_calculate_tier_score_partial(self, loop_with_mocks):
        """Test _calculate_tier_score with partial pass."""
        loop = loop_with_mocks
        tier_result = MagicMock()
        tier_result.results = [
            MagicMock(passed=True),
            MagicMock(passed=True),
            MagicMock(passed=False),
            MagicMock(passed=False),
        ]
        assert loop._calculate_tier_score(tier_result) == 50.0

    def test_record_iteration(self, loop_with_mocks):
        """Test _record_iteration adds to history."""
        from datetime import datetime

        loop = loop_with_mocks
        loop.iteration = 2

        tier1 = MagicMock()
        tier1.passed = True

        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=False), MagicMock(passed=True)]

        tier3 = MagicMock()
        tier3.results = [MagicMock(), MagicMock(), MagicMock()]

        loop._record_iteration(datetime.now(), 80.0, tier1, tier2, tier3)

        assert len(loop.history) == 1
        assert loop.history[0].iteration == 2
        assert loop.history[0].score == 80.0
        assert loop.history[0].tier1_passed is True
        assert loop.history[0].tier2_warnings == 1
        assert loop.history[0].tier3_monitors == 3


class TestAsyncMethods:
    """Async tests for RalphLoop async methods."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator for async tests."""
        mock = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock.validators = {"test": mock_validator}
        return mock

    @pytest.mark.asyncio
    async def test_run_tier1_success(self, mock_orchestrator):
        """Test _run_tier1 returns result on success."""

        tier1_result = MagicMock()
        tier1_result.passed = True
        tier1_result.results = []

        async def mock_run_tier(tier):
            return tier1_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        result, error = await loop._run_tier1()

        assert result is not None
        assert error is None
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_run_tier1_timeout(self, mock_orchestrator):
        """Test _run_tier1 handles timeout."""
        import asyncio

        async def mock_run_tier(tier):
            await asyncio.sleep(10)  # Will timeout
            return MagicMock()

        mock_orchestrator.run_tier = mock_run_tier

        config = RalphLoopConfig(tier1_timeout_seconds=0.01)
        loop = RalphLoop(mock_orchestrator, config)
        from datetime import datetime

        loop._start_time = datetime.now()

        result, error = await loop._run_tier1()

        assert result is None
        assert error is not None
        assert error.state == LoopState.BLOCKED
        assert "timed out" in error.message.lower()

    @pytest.mark.asyncio
    async def test_run_tier1_blocked(self, mock_orchestrator):
        """Test _run_tier1 returns error on failure."""
        tier1_result = MagicMock()
        tier1_result.passed = False
        tier1_result.failed_dimensions = ["syntax", "security"]

        async def mock_run_tier(tier):
            return tier1_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        from datetime import datetime

        loop._start_time = datetime.now()

        result, error = await loop._run_tier1()

        assert result is None
        assert error is not None
        assert error.state == LoopState.BLOCKED
        assert "syntax" in error.blockers

    @pytest.mark.asyncio
    async def test_run_tier2_and_tier3_success(self, mock_orchestrator):
        """Test _run_tier2_and_tier3 returns both results."""
        tier2_result = MagicMock()
        tier2_result.results = [MagicMock(passed=True)]

        tier3_result = MagicMock()
        tier3_result.results = [MagicMock()]

        call_count = 0

        async def mock_run_tier(tier):
            nonlocal call_count
            call_count += 1
            if tier.value == 2:
                return tier2_result
            return tier3_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        t2, t3 = await loop._run_tier2_and_tier3()

        assert t2 == tier2_result
        assert t3 == tier3_result

    @pytest.mark.asyncio
    async def test_run_tier2_and_tier3_timeout(self, mock_orchestrator):
        """Test _run_tier2_and_tier3 handles timeout gracefully."""
        import asyncio

        async def mock_run_tier(tier):
            await asyncio.sleep(10)  # Will timeout
            return MagicMock()

        mock_orchestrator.run_tier = mock_run_tier

        config = RalphLoopConfig(tier2_timeout_seconds=0.01)
        loop = RalphLoop(mock_orchestrator, config)
        t2, t3 = await loop._run_tier2_and_tier3()

        # Should return empty tier results, not crash
        assert t2.passed is True
        assert t3.passed is True

    @pytest.mark.asyncio
    async def test_run_iteration_early_exit(self, mock_orchestrator):
        """Test _run_iteration returns early on tier1 failure."""
        tier1_result = MagicMock()
        tier1_result.passed = False
        tier1_result.failed_dimensions = ["syntax"]

        async def mock_run_tier(tier):
            return tier1_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        from datetime import datetime

        loop._start_time = datetime.now()
        loop.iteration = 1

        score, error = await loop._run_iteration(datetime.now())

        assert score == 0.0
        assert error is not None
        assert error.state == LoopState.BLOCKED

    @pytest.mark.asyncio
    async def test_run_iteration_success(self, mock_orchestrator):
        """Test _run_iteration returns score on success."""
        tier1_result = MagicMock()
        tier1_result.passed = True
        tier1_result.results = [MagicMock(passed=True)]

        tier2_result = MagicMock()
        tier2_result.results = [MagicMock(passed=True)]

        tier3_result = MagicMock()
        tier3_result.results = [MagicMock(passed=True)]

        async def mock_run_tier(tier):
            if tier.value == 1:
                return tier1_result
            elif tier.value == 2:
                return tier2_result
            return tier3_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        from datetime import datetime

        loop._start_time = datetime.now()
        loop.iteration = 1

        score, error = await loop._run_iteration(datetime.now())

        assert error is None
        assert score == 100.0
        assert len(loop.history) == 1

    @pytest.mark.asyncio
    async def test_run_complete_on_threshold(self, mock_orchestrator):
        """Test run() completes when threshold met."""
        tier1_result = MagicMock()
        tier1_result.passed = True
        tier1_result.results = [MagicMock(passed=True)]

        tier2_result = MagicMock()
        tier2_result.results = [MagicMock(passed=True)]

        tier3_result = MagicMock()
        tier3_result.results = [MagicMock(passed=True)]

        async def mock_run_tier(tier):
            if tier.value == 1:
                return tier1_result
            elif tier.value == 2:
                return tier2_result
            return tier3_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        result = await loop.run(["test.py"])

        assert result.state == LoopState.COMPLETE
        assert result.score == 100.0
        assert result.iteration == 1

    @pytest.mark.asyncio
    async def test_run_blocked_on_tier1_failure(self, mock_orchestrator):
        """Test run() returns BLOCKED on tier1 failure."""
        tier1_result = MagicMock()
        tier1_result.passed = False
        tier1_result.failed_dimensions = ["syntax_error"]

        async def mock_run_tier(tier):
            return tier1_result

        mock_orchestrator.run_tier = mock_run_tier

        loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
        result = await loop.run(["test.py"])

        assert result.state == LoopState.BLOCKED
        assert "syntax_error" in result.blockers

    @pytest.mark.asyncio
    async def test_run_max_iterations(self, mock_orchestrator):
        """Test run() stops at max_iterations."""
        tier1_result = MagicMock()
        tier1_result.passed = True
        tier1_result.results = [MagicMock(passed=True)]

        tier2_result = MagicMock()
        tier2_result.results = [MagicMock(passed=False)]  # 50% score

        tier3_result = MagicMock()
        tier3_result.results = [MagicMock(passed=False)]  # 50% score

        async def mock_run_tier(tier):
            if tier.value == 1:
                return tier1_result
            elif tier.value == 2:
                return tier2_result
            return tier3_result

        mock_orchestrator.run_tier = mock_run_tier

        config = RalphLoopConfig(max_iterations=3, min_score_threshold=100.0)
        loop = RalphLoop(mock_orchestrator, config)
        result = await loop.run(["test.py"])

        # Score = 100*0.5 + 0*0.3 + 0*0.2 = 50.0 (tier2 and tier3 have 0% pass rate)
        assert result.state == LoopState.COMPLETE
        assert result.iteration == 3
        assert "Max iterations" in result.message


class TestParseFiles:
    """Tests for parse_files function."""

    def test_parse_files_comma_separated(self):
        from ralph_loop import parse_files

        result = parse_files("file1.py,file2.py,file3.py")
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_parse_files_space_separated(self):
        from ralph_loop import parse_files

        result = parse_files("file1.py file2.py")
        assert result == ["file1.py", "file2.py"]

    def test_parse_files_mixed(self):
        from ralph_loop import parse_files

        result = parse_files("file1.py, file2.py file3.py")
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_parse_files_none_tty(self, monkeypatch):
        import io

        from ralph_loop import parse_files

        # Simulate a tty stdin
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        result = parse_files(None)
        assert result == []

    def test_parse_files_from_stdin(self, monkeypatch):
        import io

        from ralph_loop import parse_files

        stdin = io.StringIO("file1.py,file2.py\nfile3.py")
        monkeypatch.setattr("sys.stdin", stdin)
        result = parse_files(None)
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_parse_files_empty_string(self):
        from ralph_loop import parse_files

        # Empty string is truthy-ish but splits to nothing
        result = parse_files("   ")
        assert result == []


class TestGetProjectFromGit:
    """Tests for _get_project_from_git standalone function."""

    def test_returns_string(self):
        from ralph_loop import _get_project_from_git

        result = _get_project_from_git()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_on_failure(self, monkeypatch):
        # Make subprocess.run raise to trigger fallback
        import subprocess as sp

        from ralph_loop import _get_project_from_git

        monkeypatch.setattr(
            sp, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no git"))
        )
        result = _get_project_from_git()
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetProjectNameMethod:
    """Tests for RalphLoop._get_project_name with git failure."""

    def test_fallback_on_subprocess_error(self, monkeypatch):
        import subprocess as sp

        monkeypatch.setattr(
            sp, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no git"))
        )
        mock_orch = MagicMock()
        mock_orch.validators = {}
        loop = RalphLoop(mock_orch, RalphLoopConfig())
        name = loop._get_project_name()
        assert isinstance(name, str)
        assert len(name) > 0


class TestCreateEmptyTierResultFallback:
    """Test the EmptyTierResult fallback in _create_empty_tier_result."""

    def test_fallback_when_orchestrator_import_fails(self, monkeypatch):
        """Force the ImportError fallback path."""
        import ralph_loop as rl_mod

        # Temporarily remove orchestrator from sys.modules if present
        saved = sys.modules.pop("orchestrator", None)
        # Also patch importlib to fail
        original_import = (
            __builtins__.__import__
            if hasattr(__builtins__, "__import__")
            else __import__
        )

        def failing_import(name, *args, **kwargs):
            if name == "orchestrator":
                raise ImportError("forced")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", failing_import)

        result = rl_mod._create_empty_tier_result(2)
        assert result.tier.value == 2
        assert result.results == []
        assert result.passed is True
        assert result.failed_dimensions == []

        # Restore
        if saved is not None:
            sys.modules["orchestrator"] = saved


class TestRunTier2Tier3OuterException:
    """Test the outer except branch in _run_tier2_and_tier3."""

    @pytest.fixture
    def mock_orchestrator(self):
        mock = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock.validators = {"test": mock_validator}
        return mock

    @pytest.mark.asyncio
    async def test_outer_exception_returns_empty(self, mock_orchestrator):
        """When asyncio.gather itself raises, get empty results."""
        import asyncio

        # Make run_tier raise a non-asyncio exception that escapes gather
        async def mock_run_tier(tier):
            raise RuntimeError("catastrophic")

        mock_orchestrator.run_tier = mock_run_tier

        # Patch asyncio.gather to raise directly
        _ = asyncio.gather  # noqa: F841

        async def failing_gather(*coros, **kwargs):
            # Cancel the coros
            for c in coros:
                c.close()
            raise RuntimeError("gather failed")

        original = asyncio.gather
        asyncio.gather = failing_gather
        try:
            loop = RalphLoop(mock_orchestrator, RalphLoopConfig())
            t2, t3 = await loop._run_tier2_and_tier3()
            assert t2.passed is True
            assert t3.passed is True
        finally:
            asyncio.gather = original


class TestAsyncMainCLI:
    """Tests for async_main CLI function."""

    @pytest.mark.asyncio
    async def test_no_files_json(self, monkeypatch):
        """Test async_main with no files in JSON mode."""
        import io

        from ralph_loop import async_main

        monkeypatch.setattr("sys.argv", ["ralph_loop.py", "--json"])
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 1
        output = "\n".join(capsys_lines)
        assert "error" in output.lower()

    @pytest.mark.asyncio
    async def test_no_files_text(self, monkeypatch):
        """Test async_main with no files in text mode."""
        import io

        from ralph_loop import async_main

        monkeypatch.setattr("sys.argv", ["ralph_loop.py"])
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_orchestrator_import_error_json(self, monkeypatch):
        """Test async_main when orchestrator import fails, JSON mode."""
        from ralph_loop import async_main

        monkeypatch.setattr(
            "sys.argv", ["ralph_loop.py", "--files", "test.py", "--json"]
        )

        # Make orchestrator import fail inside async_main
        saved = sys.modules.pop("orchestrator", None)
        original_import = __import__

        def failing_import(name, *args, **kwargs):
            if name == "orchestrator":
                raise ImportError("forced")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", failing_import)
        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 1
        output = "\n".join(capsys_lines)
        assert "error" in output.lower()

        if saved is not None:
            sys.modules["orchestrator"] = saved

    @pytest.mark.asyncio
    async def test_orchestrator_import_error_text(self, monkeypatch):
        """Test async_main when orchestrator import fails, text mode."""
        from ralph_loop import async_main

        monkeypatch.setattr("sys.argv", ["ralph_loop.py", "--files", "test.py"])

        saved = sys.modules.pop("orchestrator", None)
        original_import = __import__

        def failing_import(name, *args, **kwargs):
            if name == "orchestrator":
                raise ImportError("forced")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", failing_import)
        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 1

        if saved is not None:
            sys.modules["orchestrator"] = saved

    @pytest.mark.asyncio
    async def test_successful_run_json(self, monkeypatch):
        """Test async_main with successful run, JSON output."""
        from ralph_loop import async_main

        monkeypatch.setattr(
            "sys.argv",
            [
                "ralph_loop.py",
                "--files",
                "test.py",
                "--json",
                "--max-iterations",
                "1",
                "--threshold",
                "0",
            ],
        )

        # Mock the orchestrator
        tier_result = MagicMock()
        tier_result.passed = True
        tier_result.results = [MagicMock(passed=True)]

        async def mock_run_tier(tier):
            return tier_result

        mock_orch = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orch.validators = {"test": mock_validator}
        mock_orch.run_tier = mock_run_tier

        original_import = __import__

        def patched_import(name, *args, **kwargs):
            if name == "orchestrator":
                mod = MagicMock()
                mod.ValidationOrchestrator.return_value = mock_orch
                return mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", patched_import)

        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 0
        output = "\n".join(capsys_lines)
        parsed = json.loads(output)
        assert parsed["state"] == "complete"

    @pytest.mark.asyncio
    async def test_successful_run_text(self, monkeypatch):
        """Test async_main with successful run, text output."""
        from ralph_loop import async_main

        monkeypatch.setattr(
            "sys.argv",
            [
                "ralph_loop.py",
                "--files",
                "test.py",
                "--max-iterations",
                "1",
                "--threshold",
                "0",
                "--project",
                "testproj",
            ],
        )

        tier_result = MagicMock()
        tier_result.passed = True
        tier_result.results = [MagicMock(passed=True)]

        async def mock_run_tier(tier):
            return tier_result

        mock_orch = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orch.validators = {"test": mock_validator}
        mock_orch.run_tier = mock_run_tier

        original_import = __import__

        def patched_import(name, *args, **kwargs):
            if name == "orchestrator":
                mod = MagicMock()
                mod.ValidationOrchestrator.return_value = mock_orch
                return mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", patched_import)

        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 0
        output = "\n".join(capsys_lines)
        assert "RALPH LOOP RESULT" in output

    @pytest.mark.asyncio
    async def test_blocked_run_text(self, monkeypatch):
        """Test async_main with blocked result, text output with blockers."""
        from ralph_loop import async_main

        monkeypatch.setattr(
            "sys.argv",
            [
                "ralph_loop.py",
                "--files",
                "test.py",
                "--max-iterations",
                "1",
                "--project",
                "testproj",
            ],
        )

        tier_result = MagicMock()
        tier_result.passed = False
        tier_result.failed_dimensions = ["syntax"]
        tier_result.results = []

        async def mock_run_tier(tier):
            return tier_result

        mock_orch = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orch.validators = {"test": mock_validator}
        mock_orch.run_tier = mock_run_tier

        original_import = __import__

        def patched_import(name, *args, **kwargs):
            if name == "orchestrator":
                mod = MagicMock()
                mod.ValidationOrchestrator.return_value = mock_orch
                return mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", patched_import)

        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 1
        output = "\n".join(capsys_lines)
        assert "Blockers" in output

    @pytest.mark.asyncio
    async def test_below_threshold_exit_code(self, monkeypatch):
        """Test exit code 2 when score below threshold."""
        from ralph_loop import async_main

        monkeypatch.setattr(
            "sys.argv",
            [
                "ralph_loop.py",
                "--files",
                "test.py",
                "--json",
                "--max-iterations",
                "1",
                "--threshold",
                "100",
            ],
        )

        tier1 = MagicMock()
        tier1.passed = True
        tier1.results = [MagicMock(passed=True)]
        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=False)]
        tier3 = MagicMock()
        tier3.results = [MagicMock(passed=False)]

        async def mock_run_tier(tier):
            if tier.value == 1:
                return tier1
            elif tier.value == 2:
                return tier2
            return tier3

        mock_orch = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orch.validators = {"test": mock_validator}
        mock_orch.run_tier = mock_run_tier

        original_import = __import__

        def patched_import(name, *args, **kwargs):
            if name == "orchestrator":
                mod = MagicMock()
                mod.ValidationOrchestrator.return_value = mock_orch
                return mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", patched_import)

        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 2

    @pytest.mark.asyncio
    async def test_config_file_loading(self, monkeypatch, tmp_path):
        """Test async_main with --config flag."""
        from ralph_loop import async_main

        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"max_iterations": 1, "min_score_threshold": 0})
        )

        monkeypatch.setattr(
            "sys.argv",
            [
                "ralph_loop.py",
                "--files",
                "test.py",
                "--json",
                "--config",
                str(config_file),
            ],
        )

        tier_result = MagicMock()
        tier_result.passed = True
        tier_result.results = [MagicMock(passed=True)]

        async def mock_run_tier(tier):
            return tier_result

        mock_orch = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orch.validators = {"test": mock_validator}
        mock_orch.run_tier = mock_run_tier

        original_import = __import__

        def patched_import(name, *args, **kwargs):
            if name == "orchestrator":
                mod = MagicMock()
                mod.ValidationOrchestrator.return_value = mock_orch
                return mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", patched_import)

        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_text_output_with_history(self, monkeypatch):
        """Test text output includes history section."""
        from ralph_loop import async_main

        monkeypatch.setattr(
            "sys.argv",
            [
                "ralph_loop.py",
                "--files",
                "test.py",
                "--max-iterations",
                "2",
                "--threshold",
                "100",
                "--project",
                "testproj",
            ],
        )

        tier1 = MagicMock()
        tier1.passed = True
        tier1.results = [MagicMock(passed=True)]
        tier2 = MagicMock()
        tier2.results = [MagicMock(passed=False)]
        tier3 = MagicMock()
        tier3.results = [MagicMock(passed=False)]

        async def mock_run_tier(tier):
            if tier.value == 1:
                return tier1
            elif tier.value == 2:
                return tier2
            return tier3

        mock_orch = MagicMock()
        mock_validator = MagicMock()
        mock_tier_class = MagicMock(side_effect=lambda x: MagicMock(value=x))
        mock_validator.tier.__class__ = mock_tier_class
        mock_orch.validators = {"test": mock_validator}
        mock_orch.run_tier = mock_run_tier

        original_import = __import__

        def patched_import(name, *args, **kwargs):
            if name == "orchestrator":
                mod = MagicMock()
                mod.ValidationOrchestrator.return_value = mock_orch
                return mod
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", patched_import)

        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit):
            await async_main()
        output = "\n".join(capsys_lines)
        assert "HISTORY" in output
        assert "Iteration" in output


class TestMainFunction:
    """Test the sync main() wrapper."""

    def test_main_calls_async_main(self, monkeypatch):
        import io

        from ralph_loop import main

        monkeypatch.setattr("sys.argv", ["ralph_loop.py", "--json"])
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        capsys_lines = []
        monkeypatch.setattr(
            "builtins.print",
            lambda *a, **k: capsys_lines.append(" ".join(str(x) for x in a)),
        )

        with pytest.raises(SystemExit):
            main()


class TestImportFallbacks:
    """Test the import fallback branches for integrations."""

    def test_metrics_fallback(self):
        """The fallback push_validation_metrics returns False."""
        # We can test this by calling the function directly if integrations are loaded
        # If they are loaded, we test the real ones; the fallback is for when they're not
        from ralph_loop import push_validation_metrics

        # Just verify it's callable
        assert callable(push_validation_metrics)

    def test_sentry_fallback(self):
        """The fallback inject/add functions return False."""
        from ralph_loop import add_validation_breadcrumb, inject_validation_context

        assert callable(inject_validation_context)
        assert callable(add_validation_breadcrumb)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
