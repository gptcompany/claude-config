"""
Tests for SecurityEnhancedValidator.

Tests the OWASP pattern checking logic with mocked grep calls.
"""

from unittest.mock import patch
import pytest

from ..security_enhanced import SecurityEnhancedValidator
from ..base import ValidationTier


class TestSecurityEnhancedValidatorBasics:
    """Test SecurityEnhancedValidator class attributes."""

    def test_dimension(self):
        """SecurityEnhancedValidator has correct dimension."""
        assert SecurityEnhancedValidator.dimension == "security_enhanced"

    def test_tier_is_blocker(self):
        """SecurityEnhancedValidator is Tier 1 (BLOCKER)."""
        assert SecurityEnhancedValidator.tier == ValidationTier.BLOCKER

    def test_agent_name(self):
        """SecurityEnhancedValidator links to security-reviewer agent."""
        assert SecurityEnhancedValidator.agent == "security-reviewer"


class TestSecurityEnhancedValidatorClean:
    """Test SecurityEnhancedValidator with clean code (no issues)."""

    @pytest.mark.asyncio
    async def test_no_issues_found(self, tmp_path):
        """Pass when no OWASP patterns found."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("""
from flask import Flask
from auth import requires_auth
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/users")
@requires_auth
def get_users():
    try:
        return User.query.all()
    except Exception as e:
        logger.error(f"Failed: {e}")
        raise
""")

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        # Mock grep to return empty (no issues)
        async def mock_run_grep(pattern, path, include="*"):
            # Simulate auth decorators found
            if "requires_auth" in pattern or "login_required" in pattern:
                return "@requires_auth"
            # Simulate logging found
            if "import logging" in pattern or "logger" in pattern:
                return "import logging"
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is True
        assert "No OWASP" in result.message


class TestSecurityEnhancedValidatorA01:
    """Test A01 Broken Access Control detection."""

    @pytest.mark.asyncio
    async def test_routes_without_auth(self, tmp_path):
        """Detect Python routes without auth decorators."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("""
from flask import Flask

app = Flask(__name__)

@app.route("/users")
def get_users():
    return User.query.all()
""")

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        async def mock_run_grep(pattern, path, include="*"):
            # No auth decorators
            if "requires_auth" in pattern or "login_required" in pattern:
                return ""
            # But routes exist
            if "@app.route" in pattern or "@router" in pattern:
                return "@app.route('/users')"
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is False
        assert "A01" in result.message or "A01_broken_access_control" in str(
            result.details
        )


class TestSecurityEnhancedValidatorA03:
    """Test A03 Injection detection."""

    @pytest.mark.asyncio
    async def test_fstring_sql_injection(self, tmp_path):
        """Detect f-string SQL queries."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "db.py").write_text("""
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
""")

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        async def mock_run_grep(pattern, path, include="*"):
            # Match SQL injection pattern
            if "SELECT" in pattern and "{" in pattern:
                return (
                    'src/db.py:2: query = f"SELECT * FROM users WHERE id = {user_id}"'
                )
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is False
        assert "A03" in result.message or "A03_injection" in str(result.details)


class TestSecurityEnhancedValidatorA07:
    """Test A07 XSS detection."""

    @pytest.mark.asyncio
    async def test_innerhtml_xss(self, tmp_path):
        """Detect innerHTML usage."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "component.js").write_text("""
function render(data) {
    document.getElementById('output').innerHTML = data.content;
}
""")

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        async def mock_run_grep(pattern, path, include="*"):
            # Match innerHTML pattern
            if "innerHTML" in pattern:
                return "src/component.js:3: .innerHTML = data.content"
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is False
        assert "A07" in result.message or "A07_xss" in str(result.details)

    @pytest.mark.asyncio
    async def test_dangerously_set_innerhtml(self, tmp_path):
        """Detect dangerouslySetInnerHTML in React."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Component.tsx").write_text("""
export function MyComponent({ html }) {
    return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
""")

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        async def mock_run_grep(pattern, path, include="*"):
            if "dangerouslySetInnerHTML" in pattern:
                return "src/Component.tsx:3: dangerouslySetInnerHTML={{ __html: html }}"
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is False
        assert "XSS" in str(result.details) or "A07" in result.message


class TestSecurityEnhancedValidatorA09:
    """Test A09 Logging Failures detection."""

    @pytest.mark.asyncio
    async def test_except_without_logging(self, tmp_path):
        """Detect bare except blocks without logging setup."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("""
def process():
    try:
        do_something()
    except:
        pass  # Silent failure

def another():
    try:
        do_other()
    except:
        pass

def third():
    try:
        do_third()
    except:
        pass

def fourth():
    try:
        do_fourth()
    except:
        pass
""")

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        async def mock_run_grep(pattern, path, include="*"):
            if "except:" in pattern:
                return """src/app.py:5: except:
src/app.py:11: except:
src/app.py:17: except:
src/app.py:23: except:"""
            if "import logging" in pattern or "logger" in pattern:
                return ""  # No logging
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is False
        assert "A09" in result.message or "A09_logging" in str(result.details)


class TestSecurityEnhancedValidatorEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_project(self, tmp_path):
        """Handle empty project directory."""
        validator = SecurityEnhancedValidator(project_path=tmp_path)

        # All greps return empty
        async def mock_run_grep(pattern, path, include="*"):
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        # No issues in empty project
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_multiple_issues(self, tmp_path):
        """Report multiple OWASP issues."""
        (tmp_path / "src").mkdir()

        validator = SecurityEnhancedValidator(project_path=tmp_path)

        async def mock_run_grep(pattern, path, include="*"):
            # Routes without auth
            if "@app.route" in pattern:
                return "@app.route('/api')"
            if "requires_auth" in pattern:
                return ""
            # SQL injection
            if "SELECT" in pattern:
                return 'f"SELECT * FROM users"'
            # XSS
            if "innerHTML" in pattern:
                return ".innerHTML = x"
            return ""

        with patch.object(validator, "_run_grep", side_effect=mock_run_grep):
            result = await validator.validate()

        assert result.passed is False
        # Should have multiple issues
        assert len(result.details) >= 2
        assert result.fix_suggestion is not None
        assert result.agent == "security-reviewer"
