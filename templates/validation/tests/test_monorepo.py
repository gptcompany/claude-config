#!/usr/bin/env python3
"""
Unit tests for monorepo package discovery.

Tests cover:
1. Single project discovery
2. Multi-package (monorepo) discovery
3. Ignore patterns (node_modules, __pycache__, .git)
4. Max depth enforcement
5. is_monorepo() function
6. Config merging
7. Edge cases (empty directory)
"""

import json
from pathlib import Path

import pytest

from monorepo import IGNORE_DIRS, discover_packages, is_ignored, is_monorepo


def create_package(base_path: Path, name: str, config: dict) -> Path:
    """Helper to create a package directory with validation config."""
    pkg_path = base_path / name
    config_dir = pkg_path / ".claude" / "validation"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(config, indent=2))
    return pkg_path


@pytest.fixture
def minimal_config() -> dict:
    """Minimal valid config for testing."""
    return {
        "project_name": "test-project",
        "domain": "general",
    }


class TestDiscoverSingleProject:
    """Test 1: test_discover_single_project"""

    def test_discover_single_project(self, tmp_path: Path, minimal_config: dict):
        """Single package found at root."""
        # Create a single package at root
        create_package(tmp_path, "my-project", minimal_config)
        project_path = tmp_path / "my-project"

        packages = discover_packages(project_path)

        assert len(packages) == 1
        assert packages[0].name == "my-project"
        assert packages[0].path == project_path.resolve()
        assert packages[0].config_path.exists()


class TestDiscoverMonorepo:
    """Test 2: test_discover_monorepo"""

    def test_discover_monorepo(self, tmp_path: Path, minimal_config: dict):
        """Multiple packages found in monorepo structure."""
        # Create monorepo structure
        create_package(tmp_path / "packages", "frontend", minimal_config)
        create_package(tmp_path / "packages", "backend", minimal_config)
        create_package(tmp_path / "packages", "shared", minimal_config)

        packages = discover_packages(tmp_path)

        assert len(packages) == 3
        names = {pkg.name for pkg in packages}
        assert names == {"frontend", "backend", "shared"}


class TestIgnoreNodeModules:
    """Test 3: test_ignore_node_modules"""

    def test_ignore_node_modules(self, tmp_path: Path, minimal_config: dict):
        """node_modules directory should be skipped."""
        # Create a valid package
        create_package(tmp_path, "my-app", minimal_config)

        # Create a package inside node_modules (should be ignored)
        node_modules = tmp_path / "my-app" / "node_modules"
        create_package(node_modules, "some-dep", minimal_config)

        packages = discover_packages(tmp_path)

        assert len(packages) == 1
        assert packages[0].name == "my-app"


class TestIgnorePycache:
    """Test 4: test_ignore_pycache"""

    def test_ignore_pycache(self, tmp_path: Path, minimal_config: dict):
        """__pycache__ directory should be skipped."""
        # Create a valid package
        create_package(tmp_path, "my-app", minimal_config)

        # Create a directory inside __pycache__ that looks like a package
        pycache = tmp_path / "my-app" / "__pycache__"
        create_package(pycache, "cached", minimal_config)

        packages = discover_packages(tmp_path)

        assert len(packages) == 1
        assert packages[0].name == "my-app"


class TestIgnoreGit:
    """Test 5: test_ignore_git"""

    def test_ignore_git(self, tmp_path: Path, minimal_config: dict):
        """ ".git directory should be skipped."""
        # Create a valid package
        create_package(tmp_path, "my-repo", minimal_config)

        # Create something inside .git
        git_dir = tmp_path / "my-repo" / ".git"
        create_package(git_dir, "hooks", minimal_config)

        packages = discover_packages(tmp_path)

        assert len(packages) == 1
        assert packages[0].name == "my-repo"


class TestMaxDepthRespected:
    """Test 6: test_max_depth_respected"""

    def test_max_depth_respected(self, tmp_path: Path, minimal_config: dict):
        """Deep packages should not be found if beyond max_depth."""
        # Create package at depth 1
        create_package(tmp_path / "level1", "shallow", minimal_config)

        # Create package at depth 4 (should be ignored with default max_depth=3)
        deep_path = tmp_path / "a" / "b" / "c" / "d"
        create_package(deep_path, "deep", minimal_config)

        # With max_depth=3, deep package should not be found
        packages = discover_packages(tmp_path, max_depth=3)
        names = {pkg.name for pkg in packages}
        assert "shallow" in names
        assert "deep" not in names

        # With max_depth=5, deep package should be found
        packages = discover_packages(tmp_path, max_depth=5)
        names = {pkg.name for pkg in packages}
        assert "shallow" in names
        assert "deep" in names


class TestIsMonorepoTrue:
    """Test 7: test_is_monorepo_true"""

    def test_is_monorepo_true(self, tmp_path: Path, minimal_config: dict):
        """Returns True for multi-package directory."""
        create_package(tmp_path / "packages", "pkg1", minimal_config)
        create_package(tmp_path / "packages", "pkg2", minimal_config)

        assert is_monorepo(tmp_path) is True


class TestIsMonorepoFalse:
    """Test 8: test_is_monorepo_false"""

    def test_is_monorepo_false(self, tmp_path: Path, minimal_config: dict):
        """Returns False for single package."""
        create_package(tmp_path, "single-project", minimal_config)

        assert is_monorepo(tmp_path) is False


class TestPackageInfoHasMergedConfig:
    """Test 9: test_package_info_has_merged_config"""

    def test_package_info_has_merged_config(self, tmp_path: Path):
        """Config includes global merge (has default dimensions)."""
        # Create package with minimal config (no dimensions specified)
        config = {
            "project_name": "test-merged",
            "domain": "general",
        }
        create_package(tmp_path, "test-pkg", config)

        packages = discover_packages(tmp_path)

        assert len(packages) == 1
        pkg = packages[0]

        # Config should have been merged with defaults
        assert "dimensions" in pkg.config
        assert "code_quality" in pkg.config["dimensions"]
        assert "coverage" in pkg.config["dimensions"]
        # Check a default value was applied
        assert pkg.config["dimensions"]["code_quality"]["enabled"] is True


class TestEmptyDirectory:
    """Test 10: test_empty_directory"""

    def test_empty_directory(self, tmp_path: Path):
        """Returns empty list gracefully for empty directory."""
        packages = discover_packages(tmp_path)

        assert packages == []


class TestIsIgnored:
    """Additional tests for is_ignored helper."""

    def test_is_ignored_explicit_dirs(self):
        """Tests for explicitly ignored directories."""
        assert is_ignored(Path("node_modules")) is True
        assert is_ignored(Path("__pycache__")) is True
        assert is_ignored(Path(".git")) is True
        assert is_ignored(Path(".venv")) is True
        assert is_ignored(Path("venv")) is True
        assert is_ignored(Path("dist")) is True
        assert is_ignored(Path("build")) is True

    def test_is_ignored_glob_patterns(self):
        """Tests for glob patterns like *.egg-info."""
        assert is_ignored(Path("mypackage.egg-info")) is True
        assert is_ignored(Path("another.egg-info")) is True

    def test_is_ignored_hidden_dirs(self):
        """Hidden directories (except .claude) should be ignored."""
        assert is_ignored(Path(".hidden")) is True
        assert is_ignored(Path(".mypy_cache")) is True
        assert is_ignored(Path(".ruff_cache")) is True
        # .claude should NOT be ignored
        assert is_ignored(Path(".claude")) is False

    def test_is_not_ignored_normal_dirs(self):
        """Normal directories should not be ignored."""
        assert is_ignored(Path("src")) is False
        assert is_ignored(Path("packages")) is False
        assert is_ignored(Path("apps")) is False
        assert is_ignored(Path("lib")) is False


class TestIgnoreDirsConstant:
    """Tests for IGNORE_DIRS constant."""

    def test_ignore_dirs_contains_expected(self):
        """IGNORE_DIRS should contain all expected patterns."""
        expected = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
        }
        assert expected.issubset(IGNORE_DIRS)


class TestPackageInfoDataclass:
    """Tests for PackageInfo dataclass."""

    def test_package_info_fields(self, tmp_path: Path, minimal_config: dict):
        """PackageInfo should have all required fields."""
        create_package(tmp_path, "test-pkg", minimal_config)
        packages = discover_packages(tmp_path)

        assert len(packages) == 1
        pkg = packages[0]

        # Verify all fields exist and have correct types
        assert isinstance(pkg.name, str)
        assert isinstance(pkg.path, Path)
        assert isinstance(pkg.config_path, Path)
        assert isinstance(pkg.config, dict)


class TestDiscoverPackagesEdgeCases:
    """Edge case tests for discover_packages."""

    def test_nonexistent_path(self):
        """Should return empty list for nonexistent path."""
        packages = discover_packages(Path("/nonexistent/path/that/does/not/exist"))
        assert packages == []

    def test_file_instead_of_directory(self, tmp_path: Path):
        """Should return empty list when given a file instead of directory."""
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("content")

        packages = discover_packages(file_path)
        assert packages == []

    def test_packages_sorted_by_path(self, tmp_path: Path, minimal_config: dict):
        """Packages should be returned sorted by path."""
        # Create packages in non-alphabetical order
        create_package(tmp_path / "z-package", "z-package", minimal_config)
        create_package(tmp_path / "a-package", "a-package", minimal_config)
        create_package(tmp_path / "m-package", "m-package", minimal_config)

        packages = discover_packages(tmp_path)

        names = [pkg.name for pkg in packages]
        assert names == ["a-package", "m-package", "z-package"]

    def test_root_with_config_and_subpackages(
        self, tmp_path: Path, minimal_config: dict
    ):
        """Root directory can also be a package alongside subpackages."""
        # Create config at root level directly
        config_dir = tmp_path / ".claude" / "validation"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps(minimal_config))

        # Create subpackages
        create_package(tmp_path / "packages", "sub1", minimal_config)
        create_package(tmp_path / "packages", "sub2", minimal_config)

        packages = discover_packages(tmp_path)

        # Should find root + 2 subpackages
        assert len(packages) == 3
        names = {pkg.name for pkg in packages}
        assert "sub1" in names
        assert "sub2" in names
        # Root package name is the tmp_path directory name
        assert tmp_path.name in names


class TestIsIgnoredGlobEndsWith:
    """Test is_ignored glob pattern with prefix* (lines 110-113)."""

    def test_glob_pattern_prefix_star(self):
        """Test pattern ending with * (e.g. hypothetical 'build*' pattern)."""
        # The actual IGNORE_DIRS has *.egg-info (startswith *), but no pattern ending with *.
        # Lines 110-113 handle pattern.endswith("*"), which is a prefix match.
        # We need a pattern like "prefix*" in IGNORE_DIRS to hit this.
        # Since there's no such pattern, let's test via patching.
        from unittest.mock import patch

        from monorepo import is_ignored as _is_ignored

        with patch("monorepo.IGNORE_DIRS", {"build*"}):
            assert _is_ignored(Path("build-output")) is True
            assert _is_ignored(Path("buildsomething")) is True
            assert _is_ignored(Path("nobuild")) is False


class TestDiscoverPackagesInvalidConfig:
    """Test _discover_packages_recursive with invalid config (lines 150-152)."""

    def test_invalid_config_skipped(self, tmp_path: Path):
        """Packages with configs that cause exceptions are silently skipped."""
        from unittest.mock import patch

        # Create a package with a config
        pkg_path = tmp_path / "bad-pkg"
        config_dir = pkg_path / ".claude" / "validation"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"project_name": "bad"}')

        # Patch load_config to raise an exception for this package
        with patch("monorepo.load_config", side_effect=Exception("load failed")):
            packages = discover_packages(tmp_path)
        # Should not include the bad package
        assert len(packages) == 0


class TestDiscoverPackagesPermissionError:
    """Test PermissionError handling (lines 161-163)."""

    def test_permission_error_skipped(self, tmp_path: Path, minimal_config: dict):
        """Directories with permission errors are skipped."""
        from unittest.mock import patch

        create_package(tmp_path, "good-pkg", minimal_config)

        # Create a dir that will raise PermissionError on iterdir
        bad_dir = tmp_path / "restricted"
        bad_dir.mkdir()

        original_iterdir = Path.iterdir

        def patched_iterdir(self):
            if self == bad_dir:
                raise PermissionError("Access denied")
            return original_iterdir(self)

        with patch.object(Path, "iterdir", patched_iterdir):
            packages = discover_packages(tmp_path)

        # Should still find the good package
        names = {pkg.name for pkg in packages}
        assert "good-pkg" in names


class TestDiscoverPackagesDefaultRoot:
    """Test discover_packages with None root (line 198)."""

    def test_discover_with_none_root(self):
        """discover_packages(None) uses cwd."""
        packages = discover_packages(None)
        assert isinstance(packages, list)


class TestMonorepoCLI:
    """Test CLI entry point (lines 241-252)."""

    def test_cli_no_packages(self, tmp_path: Path, capsys):
        """CLI prints 'No packages found' for empty dir."""
        import runpy
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["monorepo.py", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc_info:
                runpy.run_path(
                    str(Path(__file__).parent.parent / "monorepo.py"),
                    run_name="__main__",
                )
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "No packages found" in captured.out

    def test_cli_with_packages(self, tmp_path: Path, minimal_config: dict, capsys):
        """CLI prints package list."""
        import runpy
        import sys
        from unittest.mock import patch

        create_package(tmp_path / "packages", "pkg1", minimal_config)
        create_package(tmp_path / "packages", "pkg2", minimal_config)

        with patch.object(sys, "argv", ["monorepo.py", str(tmp_path)]):
            runpy.run_path(
                str(Path(__file__).parent.parent / "monorepo.py"),
                run_name="__main__",
            )

        captured = capsys.readouterr()
        assert "Found 2 package(s):" in captured.out

    def test_cli_no_args(self, capsys):
        """CLI with no args uses cwd."""
        import runpy
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["monorepo.py"]):
            # This will use cwd, likely find no packages
            try:
                runpy.run_path(
                    str(Path(__file__).parent.parent / "monorepo.py"),
                    run_name="__main__",
                )
            except SystemExit:
                pass
