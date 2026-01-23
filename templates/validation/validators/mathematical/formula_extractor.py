#!/usr/bin/env python3
"""
Formula Extractor - Extract LaTeX formulas from Python code.

Finds formulas in:
- :math:`...` RST directives in docstrings
- $...$ and $$...$$ LaTeX delimiters in docstrings/comments
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedFormula:
    """A formula extracted from source code."""

    latex: str
    file: Path
    line: int
    context: str  # Function/class name or "module"
    source: str  # "rst_math", "single_dollar", "double_dollar"


class FormulaExtractor:
    """
    Extract LaTeX formulas from Python source files.

    Usage:
        extractor = FormulaExtractor()
        formulas = extractor.extract_from_file(Path("module.py"))
        for f in formulas:
            print(f"{f.file}:{f.line} - {f.latex}")
    """

    # Regex patterns for formula detection
    RST_MATH_PATTERN = re.compile(r":math:`([^`]+)`")
    SINGLE_DOLLAR_PATTERN = re.compile(r"(?<!\$)\$([^\$\n]+)\$(?!\$)")
    DOUBLE_DOLLAR_PATTERN = re.compile(r"\$\$([^\$]+)\$\$", re.DOTALL)

    def __init__(self, skip_dirs: set[str] | None = None):
        self.skip_dirs = skip_dirs or {
            "venv",
            "env",
            ".venv",
            "__pycache__",
            "node_modules",
            ".git",
            "build",
            "dist",
            ".eggs",
            ".tox",
        }

    def extract_from_file(self, file_path: Path) -> list[ExtractedFormula]:
        """
        Extract formulas from a single Python file.

        Args:
            file_path: Path to Python file

        Returns:
            List of extracted formulas
        """
        formulas: list[ExtractedFormula] = []

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        # Parse AST for docstrings
        try:
            tree = ast.parse(content)
            formulas.extend(self._extract_from_ast(tree, file_path))
        except SyntaxError:
            pass  # Invalid Python - skip AST analysis

        # Also scan raw content for comments with formulas
        formulas.extend(self._extract_from_comments(content, file_path))

        # Deduplicate (same formula at same line)
        seen = set()
        unique = []
        for f in formulas:
            key = (f.latex, f.line)
            if key not in seen:
                seen.add(key)
                unique.append(f)

        return unique

    def extract_from_directory(
        self,
        directory: Path,
        pattern: str = "**/*.py",
    ) -> list[ExtractedFormula]:
        """
        Extract formulas from all Python files in directory.

        Args:
            directory: Root directory to scan
            pattern: Glob pattern for files (default: **/*.py)

        Returns:
            List of extracted formulas
        """
        formulas: list[ExtractedFormula] = []

        for file_path in directory.glob(pattern):
            # Skip excluded directories
            if any(part in self.skip_dirs for part in file_path.parts):
                continue

            formulas.extend(self.extract_from_file(file_path))

        return formulas

    def _extract_from_ast(
        self,
        tree: ast.AST,
        file_path: Path,
    ) -> list[ExtractedFormula]:
        """Extract formulas from AST docstrings."""
        formulas: list[ExtractedFormula] = []

        for node in ast.walk(tree):
            # Get docstring-bearing nodes
            if isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                docstring = ast.get_docstring(node)
                if not docstring:
                    continue

                # Determine context name
                if isinstance(node, ast.Module):
                    context = "module"
                    line = 1
                else:
                    context = node.name
                    line = node.lineno

                # Extract formulas from docstring
                formulas.extend(
                    self._extract_from_text(docstring, file_path, line, context)
                )

        return formulas

    def _extract_from_text(
        self,
        text: str,
        file_path: Path,
        base_line: int,
        context: str,
    ) -> list[ExtractedFormula]:
        """Extract formulas from a text block."""
        formulas: list[ExtractedFormula] = []

        # :math:`...` RST directive
        for match in self.RST_MATH_PATTERN.finditer(text):
            latex = match.group(1).strip()
            if latex:
                formulas.append(
                    ExtractedFormula(
                        latex=latex,
                        file=file_path,
                        line=base_line,
                        context=context,
                        source="rst_math",
                    )
                )

        # $$...$$ (display math)
        for match in self.DOUBLE_DOLLAR_PATTERN.finditer(text):
            latex = match.group(1).strip()
            if latex:
                formulas.append(
                    ExtractedFormula(
                        latex=latex,
                        file=file_path,
                        line=base_line,
                        context=context,
                        source="double_dollar",
                    )
                )

        # $...$ (inline math) - but not already matched by $$
        for match in self.SINGLE_DOLLAR_PATTERN.finditer(text):
            latex = match.group(1).strip()
            if latex:
                formulas.append(
                    ExtractedFormula(
                        latex=latex,
                        file=file_path,
                        line=base_line,
                        context=context,
                        source="single_dollar",
                    )
                )

        return formulas

    def _extract_from_comments(
        self,
        content: str,
        file_path: Path,
    ) -> list[ExtractedFormula]:
        """Extract formulas from Python comments."""
        formulas: list[ExtractedFormula] = []

        for line_no, line in enumerate(content.splitlines(), start=1):
            # Check for # comment with formula
            if "#" in line:
                comment_start = line.find("#")
                comment = line[comment_start + 1 :]

                for f in self._extract_from_text(
                    comment, file_path, line_no, "comment"
                ):
                    formulas.append(f)

        return formulas


# Export for testing
__all__ = ["FormulaExtractor", "ExtractedFormula"]
