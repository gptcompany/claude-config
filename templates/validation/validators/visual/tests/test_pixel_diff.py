#!/usr/bin/env python3
"""Tests for ODiffRunner pixel comparison module."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from validators.visual.pixel_diff import ODiffResult, ODiffRunner


class TestODiffResult:
    """Tests for ODiffResult dataclass."""

    def test_result_creation(self):
        """Test creating a basic result."""
        result = ODiffResult(
            match=True,
            diff_percentage=0.0,
            diff_count=0,
            pixel_score=1.0,
        )
        assert result.match is True
        assert result.diff_percentage == 0.0
        assert result.diff_count == 0
        assert result.pixel_score == 1.0
        assert result.diff_path is None
        assert result.error is None
        assert result.details == {}

    def test_result_with_error(self):
        """Test creating a result with error."""
        result = ODiffResult(
            match=False,
            diff_percentage=100.0,
            diff_count=0,
            pixel_score=0.0,
            error="Test error",
        )
        assert result.match is False
        assert result.error == "Test error"

    def test_result_with_details(self):
        """Test creating a result with details."""
        result = ODiffResult(
            match=False,
            diff_percentage=5.5,
            diff_count=1234,
            pixel_score=0.945,
            diff_path="/path/to/diff.png",
            details={"odiff_available": True, "threshold": 0.1},
        )
        assert result.diff_path == "/path/to/diff.png"
        assert result.details["odiff_available"] is True


class TestODiffRunner:
    """Tests for ODiffRunner class."""

    def test_init_default_values(self):
        """Test runner initializes with correct defaults."""
        runner = ODiffRunner()
        assert runner.threshold == 0.1
        assert runner.antialiasing is True
        assert runner.ignore_regions == []
        assert runner.timeout == 30

    def test_init_custom_values(self):
        """Test runner accepts custom values."""
        regions = [{"x1": 0, "y1": 0, "x2": 100, "y2": 50}]
        runner = ODiffRunner(
            threshold=0.05,
            antialiasing=False,
            ignore_regions=regions,
            timeout=60,
        )
        assert runner.threshold == 0.05
        assert runner.antialiasing is False
        assert runner.ignore_regions == regions
        assert runner.timeout == 60

    @patch("shutil.which")
    def test_is_available_found_in_path(self, mock_which):
        """Test odiff is found in PATH."""
        mock_which.return_value = "/usr/bin/odiff"
        runner = ODiffRunner()
        assert runner.is_available() is True
        assert runner._odiff_path == "/usr/bin/odiff"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_is_available_via_npx(self, mock_run, mock_which):
        """Test odiff is available via npx."""
        mock_which.return_value = None
        mock_run.return_value = MagicMock(returncode=0)

        runner = ODiffRunner()
        assert runner.is_available() is True
        assert runner._odiff_path == "npx"

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_is_available_not_installed(self, mock_run, mock_which):
        """Test odiff not installed."""
        mock_which.return_value = None
        mock_run.side_effect = FileNotFoundError()

        runner = ODiffRunner()
        assert runner.is_available() is False
        assert runner._odiff_path == ""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_is_available_npx_timeout(self, mock_run, mock_which):
        """Test odiff check via npx times out."""
        mock_which.return_value = None
        mock_run.side_effect = subprocess.TimeoutExpired("npx", 10)

        runner = ODiffRunner()
        assert runner.is_available() is False

    def test_build_command_basic(self):
        """Test building basic command."""
        runner = ODiffRunner()
        runner._odiff_path = "/usr/bin/odiff"

        cmd = runner._build_command("base.png", "curr.png", "diff.png")

        assert cmd[0] == "/usr/bin/odiff"
        assert "base.png" in cmd
        assert "curr.png" in cmd
        assert "diff.png" in cmd
        assert "--threshold" in cmd
        assert "0.1" in cmd
        assert "--antialiasing" in cmd
        assert "--parsable-stdout" in cmd

    def test_build_command_with_npx(self):
        """Test building command with npx."""
        runner = ODiffRunner()
        runner._odiff_path = "npx"

        cmd = runner._build_command("base.png", "curr.png", "diff.png")

        assert cmd[0] == "npx"
        assert cmd[1] == "--yes"
        assert cmd[2] == "odiff-bin"

    def test_build_command_without_antialiasing(self):
        """Test building command without antialiasing."""
        runner = ODiffRunner(antialiasing=False)
        runner._odiff_path = "/usr/bin/odiff"

        cmd = runner._build_command("base.png", "curr.png", "diff.png")

        assert "--antialiasing" not in cmd

    def test_build_command_with_ignore_regions(self):
        """Test building command with ignore regions."""
        regions = [
            {"x1": 0, "y1": 0, "x2": 100, "y2": 50},
            {"x1": 200, "y1": 100, "x2": 300, "y2": 150},
        ]
        runner = ODiffRunner(ignore_regions=regions)
        runner._odiff_path = "/usr/bin/odiff"

        cmd = runner._build_command("base.png", "curr.png", "diff.png")

        assert cmd.count("--ignore") == 2
        assert "0:0-100:50" in cmd
        assert "200:100-300:150" in cmd

    def test_parse_output_parsable_match(self):
        """Test parsing parsable stdout for matching images (exit code 0)."""
        runner = ODiffRunner()
        # Parsable format: diffCount;diffPercentage
        # For matching images, exit code is 0 (even though diff output exists)
        stdout = "0;0.00"

        result = runner._parse_output(stdout, "", 0)

        assert result["match"] is True
        assert result["diffPercentage"] == 0.0
        assert result["diffCount"] == 0

    def test_parse_output_parsable_mismatch(self):
        """Test parsing parsable stdout for mismatched images (exit code 22)."""
        runner = ODiffRunner()
        # Parsable format: diffCount;diffPercentage
        stdout = "10000;100.00"

        result = runner._parse_output(stdout, "", 22)

        assert result["match"] is False
        assert result["diffPercentage"] == 100.0
        assert result["diffCount"] == 10000

    def test_parse_output_human_readable(self):
        """Test parsing human-readable output format."""
        runner = ODiffRunner()
        stdout = "Found 5000 different pixels (50.00%)"

        result = runner._parse_output(stdout, "", 22)

        assert result["match"] is False
        assert result["diffPercentage"] == 50.0
        assert result["diffCount"] == 5000

    def test_parse_output_percentage_fallback(self):
        """Test parsing text with just percentage."""
        runner = ODiffRunner()
        stdout = "Images differ by 3.2%"

        result = runner._parse_output(stdout, "", 22)

        assert result["match"] is False
        assert result["diffPercentage"] == 3.2

    def test_parse_output_no_pattern_match(self):
        """Test handling output with no recognized pattern."""
        runner = ODiffRunner()
        stdout = "Images are identical"

        result = runner._parse_output(stdout, "", 0)

        assert result["match"] is True
        assert result["diffPercentage"] == 0.0

    def test_compare_missing_baseline(self):
        """Test comparison with missing baseline file."""
        runner = ODiffRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            current = Path(tmpdir) / "current.png"
            current.touch()

            result = runner.compare(
                "/nonexistent/baseline.png",
                str(current),
                str(Path(tmpdir) / "diff.png"),
            )

        assert result.match is False
        assert result.pixel_score == 0.0
        assert "not found" in result.error.lower()
        assert "baseline" in result.error.lower()

    def test_compare_missing_current(self):
        """Test comparison with missing current file."""
        runner = ODiffRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            baseline.touch()

            result = runner.compare(
                str(baseline),
                "/nonexistent/current.png",
                str(Path(tmpdir) / "diff.png"),
            )

        assert result.match is False
        assert result.pixel_score == 0.0
        assert "not found" in result.error.lower()
        assert "current" in result.error.lower()

    @patch.object(ODiffRunner, "is_available", return_value=False)
    def test_compare_odiff_not_installed(self, mock_available):
        """Test graceful degradation when odiff not installed."""
        runner = ODiffRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = runner.compare(
                str(baseline),
                str(current),
                str(Path(tmpdir) / "diff.png"),
            )

        assert result.match is False
        assert result.pixel_score == 0.0
        assert "not installed" in result.error.lower()
        assert result.details.get("odiff_available") is False

    @patch.object(ODiffRunner, "is_available", return_value=True)
    @patch("subprocess.run")
    def test_compare_identical_images(self, mock_run, mock_available):
        """Test comparing identical images returns match=True, score=1.0."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="0;0.00",  # Parsable format: diffCount;diffPercentage
            stderr="",
        )

        runner = ODiffRunner()
        runner._odiff_path = "/usr/bin/odiff"

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = runner.compare(
                str(baseline),
                str(current),
                str(Path(tmpdir) / "diff.png"),
            )

        assert result.match is True
        assert result.pixel_score == 1.0
        assert result.diff_percentage == 0.0
        assert result.diff_path is None
        assert result.error is None

    @patch.object(ODiffRunner, "is_available", return_value=True)
    @patch("subprocess.run")
    def test_compare_different_images(self, mock_run, mock_available):
        """Test comparing different images returns match=False, score<1.0."""
        mock_run.return_value = MagicMock(
            returncode=22,  # Exit code 22 = pixel differences found
            stdout="500;15.50",  # Parsable format: diffCount;diffPercentage
            stderr="",
        )

        runner = ODiffRunner()
        runner._odiff_path = "/usr/bin/odiff"

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            diff = Path(tmpdir) / "diff.png"
            baseline.touch()
            current.touch()

            result = runner.compare(str(baseline), str(current), str(diff))

        assert result.match is False
        assert result.pixel_score == pytest.approx(0.845, rel=0.01)
        assert result.diff_percentage == 15.5
        assert result.diff_count == 500
        assert result.diff_path == str(diff)

    @patch.object(ODiffRunner, "is_available", return_value=True)
    @patch("subprocess.run")
    def test_compare_timeout(self, mock_run, mock_available):
        """Test handling comparison timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("odiff", 30)

        runner = ODiffRunner(timeout=30)
        runner._odiff_path = "/usr/bin/odiff"

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = runner.compare(
                str(baseline),
                str(current),
                str(Path(tmpdir) / "diff.png"),
            )

        assert result.match is False
        assert result.pixel_score == 0.0
        assert "timed out" in result.error.lower()
        assert result.details.get("timeout") is True

    @patch.object(ODiffRunner, "is_available", return_value=True)
    @patch("subprocess.run")
    def test_compare_exception(self, mock_run, mock_available):
        """Test handling unexpected exception during comparison."""
        mock_run.side_effect = OSError("Permission denied")

        runner = ODiffRunner()
        runner._odiff_path = "/usr/bin/odiff"

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = runner.compare(
                str(baseline),
                str(current),
                str(Path(tmpdir) / "diff.png"),
            )

        assert result.match is False
        assert result.pixel_score == 0.0
        assert "failed" in result.error.lower()
        assert result.details.get("exception") == "OSError"

    @patch.object(ODiffRunner, "is_available", return_value=True)
    @patch("subprocess.run")
    def test_pixel_score_calculation(self, mock_run, mock_available):
        """Test pixel score is correctly calculated from diff percentage."""
        test_cases = [
            (0.0, 1.0),  # No diff = perfect score
            (50.0, 0.5),  # 50% diff = 0.5 score
            (100.0, 0.0),  # 100% diff = 0 score
            (25.0, 0.75),  # 25% diff = 0.75 score
        ]

        runner = ODiffRunner()
        runner._odiff_path = "/usr/bin/odiff"

        for diff_pct, expected_score in test_cases:
            diff_count = int(diff_pct * 100)  # Arbitrary count based on percentage
            mock_run.return_value = MagicMock(
                returncode=0 if diff_pct == 0 else 22,
                stdout=f"{diff_count};{diff_pct:.2f}",  # Parsable format
                stderr="",
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                baseline = Path(tmpdir) / "baseline.png"
                current = Path(tmpdir) / "current.png"
                baseline.touch()
                current.touch()

                result = runner.compare(
                    str(baseline),
                    str(current),
                    str(Path(tmpdir) / "diff.png"),
                )

            assert result.pixel_score == pytest.approx(
                expected_score, rel=0.01
            ), f"diff_pct={diff_pct} expected score={expected_score}, got {result.pixel_score}"

    @patch.object(ODiffRunner, "is_available", return_value=True)
    @patch("subprocess.run")
    def test_diff_output_directory_created(self, mock_run, mock_available):
        """Test that diff output directory is created if it doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=22,
            stdout="100;5.00",  # Parsable format
            stderr="",
        )

        runner = ODiffRunner()
        runner._odiff_path = "/usr/bin/odiff"

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            diff_dir = Path(tmpdir) / "nested" / "output"
            diff = diff_dir / "diff.png"

            baseline.touch()
            current.touch()

            assert not diff_dir.exists()

            runner.compare(str(baseline), str(current), str(diff))

            assert diff_dir.exists()


class TestODiffRunnerIntegration:
    """Integration tests (skipped if odiff not available)."""

    @pytest.fixture
    def runner(self):
        """Create runner and skip if odiff not available."""
        runner = ODiffRunner()
        if not runner.is_available():
            pytest.skip("odiff not installed")
        return runner

    @pytest.fixture
    def sample_images(self, tmp_path):
        """Create sample test images using PIL if available."""
        try:
            from PIL import Image

            # Create identical images
            img1 = Image.new("RGB", (100, 100), color="red")
            img2 = Image.new("RGB", (100, 100), color="red")

            baseline = tmp_path / "baseline.png"
            current_identical = tmp_path / "current_identical.png"

            img1.save(baseline)
            img2.save(current_identical)

            # Create different image
            img3 = Image.new("RGB", (100, 100), color="blue")
            current_different = tmp_path / "current_different.png"
            img3.save(current_different)

            return {
                "baseline": str(baseline),
                "identical": str(current_identical),
                "different": str(current_different),
                "diff_output": str(tmp_path / "diff.png"),
            }
        except ImportError:
            pytest.skip("PIL not installed")

    def test_integration_identical_images(self, runner, sample_images):
        """Integration test: identical images should match."""
        result = runner.compare(
            sample_images["baseline"],
            sample_images["identical"],
            sample_images["diff_output"],
        )
        assert result.match is True
        assert result.pixel_score >= 0.99

    def test_integration_different_images(self, runner, sample_images):
        """Integration test: different images should not match."""
        result = runner.compare(
            sample_images["baseline"],
            sample_images["different"],
            sample_images["diff_output"],
        )
        assert result.match is False
        assert result.pixel_score < 1.0
