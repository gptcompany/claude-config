#!/usr/bin/env python3
"""Unit tests for mathematical validators."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.mathematical.cas_client import HTTPX_AVAILABLE, CASClient, CASResponse
from validators.mathematical.formula_extractor import ExtractedFormula, FormulaExtractor
from validators.mathematical.validator import MathematicalValidator


class TestCASResponse:
    """Tests for CASResponse dataclass."""

    def test_creation(self):
        """Test CASResponse creation."""
        response = CASResponse(
            success=True,
            cas="maxima",
            input_latex="x^2",
            simplified="x^2",
            confidence="HIGH",
        )
        assert response.success is True
        assert response.cas == "maxima"
        assert response.input_latex == "x^2"
        assert response.confidence == "HIGH"

    def test_defaults(self):
        """Test CASResponse default values."""
        response = CASResponse(
            success=False,
            cas="sagemath",
            input_latex="test",
        )
        assert response.simplified is None
        assert response.factored is None
        assert response.is_identity is None
        assert response.confidence == "UNKNOWN"
        assert response.time_ms == 0
        assert response.error is None
        assert response.cas_available is True

    def test_error_response(self):
        """Test CASResponse with error."""
        response = CASResponse(
            success=False,
            cas="matlab",
            input_latex="bad",
            error="Parse error",
            cas_available=False,
        )
        assert response.success is False
        assert response.error == "Parse error"
        assert response.cas_available is False


class TestCASClient:
    """Tests for CASClient class."""

    def test_init_defaults(self):
        """Test default initialization."""
        client = CASClient()
        assert client.base_url == "http://localhost:8769"
        assert client.timeout == 30.0

    def test_init_custom(self):
        """Test custom initialization."""
        client = CASClient(base_url="http://cas:9000", timeout=60.0)
        assert client.base_url == "http://cas:9000"
        assert client.timeout == 60.0

    def test_get_client_no_httpx(self):
        """Test _get_client when httpx not available."""
        client = CASClient()
        with patch("validators.mathematical.cas_client.HTTPX_AVAILABLE", False):
            result = client._get_client()
        assert result is None

    def test_health_check_no_httpx(self):
        """Test health_check when httpx not available."""
        client = CASClient()
        client._get_client = MagicMock(return_value=None)
        result = client.health_check()
        assert result["status"] == "unavailable"
        assert "httpx not installed" in result["error"]

    def test_health_check_success(self):
        """Test health_check with successful response."""
        client = CASClient()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy", "engines": ["maxima"]}
        mock_client.get.return_value = mock_response
        client._get_client = MagicMock(return_value=mock_client)

        result = client.health_check()
        assert result["status"] == "healthy"

    def test_health_check_error(self):
        """Test health_check with error."""
        client = CASClient()
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        client._get_client = MagicMock(return_value=mock_client)

        result = client.health_check()
        assert result["status"] == "unavailable"
        assert "Connection refused" in result["error"]

    def test_is_available_cached(self):
        """Test is_available caching."""
        client = CASClient()
        client._available = True
        assert client.is_available() is True

    def test_is_available_checks_health(self):
        """Test is_available calls health_check."""
        client = CASClient()
        client.health_check = MagicMock(return_value={"status": "healthy"})
        result = client.is_available()
        assert result is True
        assert client._available is True

    def test_validate_no_httpx(self):
        """Test validate when httpx not available."""
        client = CASClient()
        client._get_client = MagicMock(return_value=None)

        result = client.validate("x^2")
        assert result.success is False
        assert result.cas_available is False
        assert result.error and "httpx not installed" in result.error

    def test_validate_success(self):
        """Test validate with successful response."""
        client = CASClient()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "cas": "maxima",
            "simplified": "(x+1)^2",
            "confidence": "HIGH",
            "time_ms": 50,
        }
        mock_client.post.return_value = mock_response
        client._get_client = MagicMock(return_value=mock_client)

        result = client.validate("x^2 + 2*x + 1")
        assert result.success is True
        assert result.simplified == "(x+1)^2"
        assert result.confidence == "HIGH"

    def test_validate_connection_error(self):
        """Test validate with connection error (fallback)."""
        client = CASClient()
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("ConnectError: refused")
        client._get_client = MagicMock(return_value=mock_client)

        result = client.validate("x^2")
        assert result.success is False
        assert result.cas_available is False

    def test_validate_timeout(self):
        """Test validate with timeout error."""
        client = CASClient()
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("TimeoutError")
        client._get_client = MagicMock(return_value=mock_client)

        result = client.validate("x^2")
        assert result.success is False
        assert result.error and "timeout" in result.error.lower()

    def test_validate_other_error(self):
        """Test validate with other errors."""
        client = CASClient()
        mock_client = MagicMock()
        mock_client.post.side_effect = ValueError("Some error")
        client._get_client = MagicMock(return_value=mock_client)

        result = client.validate("x^2")
        assert result.success is False
        assert result.error and "Some error" in result.error

    def test_wolfram_fallback(self):
        """Test _wolfram_fallback returns unavailable."""
        client = CASClient()
        result = client._wolfram_fallback("x^2", "maxima")
        assert result.success is False
        assert result.cas_available is False
        assert result.error and "Wolfram fallback" in result.error

    def test_close(self):
        """Test close method."""
        client = CASClient()
        mock_httpx_client = MagicMock()
        client._client = mock_httpx_client

        client.close()
        mock_httpx_client.close.assert_called_once()
        assert client._client is None

    def test_close_no_client(self):
        """Test close when no client exists."""
        client = CASClient()
        client.close()  # Should not raise

    def test_context_manager(self):
        """Test context manager protocol."""
        client = CASClient()
        mock_httpx_client = MagicMock()
        client._client = mock_httpx_client

        with client as c:
            assert c is client
        mock_httpx_client.close.assert_called_once()


class TestExtractedFormula:
    """Tests for ExtractedFormula dataclass."""

    def test_creation(self):
        """Test ExtractedFormula creation."""
        formula = ExtractedFormula(
            latex="x^2",
            file=Path("test.py"),
            line=10,
            context="test_func",
            source="rst_math",
        )
        assert formula.latex == "x^2"
        assert formula.file == Path("test.py")
        assert formula.line == 10
        assert formula.context == "test_func"
        assert formula.source == "rst_math"


class TestFormulaExtractor:
    """Tests for FormulaExtractor class."""

    def test_init_default(self):
        """Test default initialization."""
        extractor = FormulaExtractor()
        assert "venv" in extractor.skip_dirs
        assert "__pycache__" in extractor.skip_dirs

    def test_init_custom_skip_dirs(self):
        """Test custom skip directories."""
        extractor = FormulaExtractor(skip_dirs={"custom_dir"})
        assert "custom_dir" in extractor.skip_dirs
        assert "venv" not in extractor.skip_dirs

    def test_extract_from_file_not_found(self):
        """Test extract from non-existent file."""
        extractor = FormulaExtractor()
        result = extractor.extract_from_file(Path("/nonexistent.py"))
        assert result == []

    def test_extract_from_file_no_formulas(self):
        """Test extract from file with no formulas."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def hello():
    '''Just a simple docstring.'''
    return "Hello"
""")
            result = extractor.extract_from_file(test_file)
        assert result == []

    def test_extract_rst_math(self):
        """Test extract :math:`...` RST directive."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
def quadratic():
    """Calculate quadratic formula.

    Uses :math:`x^2 + y^2`
    """
    pass
''')
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert "x^2" in result[0].latex
        assert result[0].source == "rst_math"

    def test_extract_single_dollar(self):
        """Test extract $...$ inline math."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
def area():
    """Calculate area.

    Returns $a + b$ for sum.
    """
    pass
''')
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert "a + b" in result[0].latex
        assert result[0].source == "single_dollar"

    def test_extract_double_dollar(self):
        """Test extract $$...$$ display math."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
def calc():
    """Calculate.

    $$x + y + z$$
    """
    pass
''')
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert "x + y" in result[0].latex
        assert result[0].source == "double_dollar"

    def test_extract_from_comments(self):
        """Test extract formulas from comments."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
# This uses $E = mc^2$ formula
x = 1
""")
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert "E = mc^2" in result[0].latex
        assert result[0].context == "comment"

    def test_extract_from_class_docstring(self):
        """Test extract from class docstring."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
class Calculator:
    """Calculator class.

    Implements :math:`f(x) = x^2`
    """
    pass
''')
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert result[0].context == "Calculator"

    def test_extract_from_module_docstring(self):
        """Test extract from module docstring."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''"""
Math module.

Uses :math:`y = mx + b` formula.
"""

x = 1
''')
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert result[0].context == "module"

    def test_extract_deduplicates(self):
        """Test that duplicate formulas at same line are removed."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            # Same formula appears twice at same location
            test_file.write_text('''
def test():
    """Uses $x^2$ and also $x^2$."""
    pass
''')
            result = extractor.extract_from_file(test_file)
        # Should deduplicate
        assert len([f for f in result if f.latex == "x^2"]) == 1

    def test_extract_syntax_error(self):
        """Test extract from file with syntax error."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def broken(")
            result = extractor.extract_from_file(test_file)
        # Should not crash, may return empty
        assert isinstance(result, list)

    def test_extract_from_directory(self):
        """Test extract from directory."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files
            (Path(tmpdir) / "a.py").write_text('''
def a():
    """:math:`a^2`"""
    pass
''')
            (Path(tmpdir) / "b.py").write_text('''
def b():
    """:math:`b^2`"""
    pass
''')
            result = extractor.extract_from_directory(Path(tmpdir))
        assert len(result) == 2

    def test_extract_from_directory_skips_venv(self):
        """Test extract skips venv directory."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            venv = Path(tmpdir) / "venv"
            venv.mkdir()
            (venv / "test.py").write_text('""":math:`x^2`"""')
            result = extractor.extract_from_directory(Path(tmpdir))
        assert len(result) == 0

    def test_extract_async_function(self):
        """Test extract from async function docstring."""
        extractor = FormulaExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
async def async_func():
    """Async function with :math:`f(x)`."""
    pass
''')
            result = extractor.extract_from_file(test_file)
        assert len(result) == 1
        assert result[0].context == "async_func"


class TestMathematicalValidator:
    """Tests for MathematicalValidator class."""

    def test_import(self):
        """Test validator can be imported."""
        assert MathematicalValidator is not None

    def test_attributes(self):
        """Test validator attributes."""
        validator = MathematicalValidator()
        assert validator.dimension == "mathematical"
        assert validator.agent is None

    def test_default_config(self):
        """Test default config merging."""
        validator = MathematicalValidator({"cas_timeout": 60.0})
        assert validator.config["cas_timeout"] == 60.0
        assert validator.config["cas_url"] == "http://localhost:8769"
        assert validator.config["scan_patterns"] == ["**/*.py"]

    @pytest.mark.asyncio
    async def test_validate_no_formulas(self):
        """Test validate when no formulas found."""
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = []
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = False

        result = await validator.validate()
        assert result.passed is True
        assert "No formulas found" in result.message
        assert result.details["formulas_found"] == 0

    @pytest.mark.asyncio
    async def test_validate_formulas_cas_unavailable(self):
        """Test validate with formulas but CAS unavailable."""
        formulas = [
            ExtractedFormula(
                latex="x^2",
                file=Path("a.py"),
                line=1,
                context="func",
                source="rst_math",
            ),
            ExtractedFormula(
                latex="y^2",
                file=Path("b.py"),
                line=5,
                context="func2",
                source="single_dollar",
            ),
        ]
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = formulas
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = False

        result = await validator.validate()
        assert result.passed is True
        assert "CAS unavailable" in result.message
        assert result.details["formulas_found"] == 2
        assert result.details["cas_available"] is False
        assert len(result.details["formulas"]) == 2

    @pytest.mark.asyncio
    async def test_validate_formulas_limited_to_20_when_cas_unavailable(self):
        """Test formulas list limited to 20 when CAS unavailable."""
        formulas = [
            ExtractedFormula(
                latex=f"x_{i}",
                file=Path(f"f{i}.py"),
                line=i,
                context="f",
                source="rst_math",
            )
            for i in range(25)
        ]
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = formulas
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = False

        result = await validator.validate()
        assert result.details["formulas_found"] == 25
        assert len(result.details["formulas"]) == 20

    @pytest.mark.asyncio
    async def test_validate_all_pass(self):
        """Test validate with CAS available, all formulas pass."""
        formulas = [
            ExtractedFormula(
                latex="x^2",
                file=Path("a.py"),
                line=1,
                context="func",
                source="rst_math",
            ),
        ]
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = formulas
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = True
        validator.cas_client.validate.return_value = CASResponse(
            success=True,
            cas="maxima",
            input_latex="x^2",
            simplified="x^2",
        )

        result = await validator.validate()
        assert result.passed is True
        assert "1/1 formulas validated" in result.message
        assert result.details["validated"] == 1
        assert result.details["errors"] == 0
        assert result.details["cas_available"] is True
        assert result.fix_suggestion is None

    @pytest.mark.asyncio
    async def test_validate_mixed_pass_fail(self):
        """Test validate with some formulas failing."""
        formulas = [
            ExtractedFormula(
                latex="x^2", file=Path("a.py"), line=1, context="f1", source="rst_math"
            ),
            ExtractedFormula(
                latex="bad formula",
                file=Path("b.py"),
                line=5,
                context="f2",
                source="rst_math",
            ),
            ExtractedFormula(
                latex="y+z", file=Path("c.py"), line=10, context="f3", source="rst_math"
            ),
        ]
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = formulas
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = True
        validator.cas_client.validate.side_effect = [
            CASResponse(success=True, cas="maxima", input_latex="x^2"),
            CASResponse(
                success=False,
                cas="maxima",
                input_latex="bad formula",
                error="Parse error",
            ),
            CASResponse(success=True, cas="maxima", input_latex="y+z"),
        ]

        result = await validator.validate()
        assert result.passed is True  # Tier 3 never blocks
        assert "1 formula errors" in result.message
        assert result.details["validated"] == 2
        assert result.details["errors"] == 1
        assert result.details["cas_engine"] == "maxima"
        assert len(result.details["error_details"]) == 1
        assert result.details["error_details"][0]["latex"] == "bad formula"
        assert result.fix_suggestion is not None
        assert "bad formula" in result.fix_suggestion

    @pytest.mark.asyncio
    async def test_validate_error_details_limited_to_10(self):
        """Test error_details limited to 10."""
        formulas = [
            ExtractedFormula(
                latex=f"bad_{i}",
                file=Path(f"f{i}.py"),
                line=i,
                context="f",
                source="rst_math",
            )
            for i in range(15)
        ]
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = formulas
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = True
        validator.cas_client.validate.return_value = CASResponse(
            success=False,
            cas="maxima",
            input_latex="bad",
            error="err",
        )

        result = await validator.validate()
        assert result.details["errors"] == 15
        assert len(result.details["error_details"]) == 10

    @pytest.mark.asyncio
    async def test_validate_fix_suggestion_limited_to_3(self):
        """Test fix_suggestion only includes first 3 error formulas."""
        formulas = [
            ExtractedFormula(
                latex=f"bad_{i}",
                file=Path(f"f{i}.py"),
                line=i,
                context="f",
                source="rst_math",
            )
            for i in range(5)
        ]
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = formulas
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = True
        validator.cas_client.validate.return_value = CASResponse(
            success=False,
            cas="maxima",
            input_latex="bad",
            error="err",
        )

        result = await validator.validate()
        assert result.fix_suggestion is not None
        assert "bad_0" in result.fix_suggestion
        assert "bad_2" in result.fix_suggestion
        assert "bad_4" not in result.fix_suggestion

    @pytest.mark.asyncio
    async def test_validate_multiple_scan_patterns(self):
        """Test validate iterates over multiple scan patterns."""
        formulas_py = [
            ExtractedFormula(
                latex="x^2", file=Path("a.py"), line=1, context="f", source="rst_math"
            )
        ]
        formulas_md = [
            ExtractedFormula(
                latex="y^2", file=Path("b.md"), line=1, context="f", source="rst_math"
            )
        ]
        validator = MathematicalValidator({"scan_patterns": ["**/*.py", "**/*.md"]})
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.side_effect = [
            formulas_py,
            formulas_md,
        ]
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = True
        validator.cas_client.validate.return_value = CASResponse(
            success=True,
            cas="maxima",
            input_latex="x",
        )

        result = await validator.validate()
        assert result.details["formulas_found"] == 2
        assert validator.extractor.extract_from_directory.call_count == 2

    def test_close(self):
        """Test close delegates to cas_client."""
        validator = MathematicalValidator()
        validator.cas_client = MagicMock()
        validator.close()
        validator.cas_client.close.assert_called_once()

    def test_context_manager(self):
        """Test __enter__ and __exit__."""
        validator = MathematicalValidator()
        validator.cas_client = MagicMock()
        with validator as v:
            assert v is validator
        validator.cas_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_duration_ms(self):
        """Test that duration_ms is set."""
        validator = MathematicalValidator()
        validator.extractor = MagicMock()
        validator.extractor.extract_from_directory.return_value = []
        validator.cas_client = MagicMock()
        validator.cas_client.is_available.return_value = False

        result = await validator.validate()
        assert result.duration_ms >= 0


class TestHTTPXAvailability:
    """Tests for HTTPX_AVAILABLE flag."""

    def test_is_bool(self):
        """Test HTTPX_AVAILABLE is boolean."""
        assert isinstance(HTTPX_AVAILABLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
