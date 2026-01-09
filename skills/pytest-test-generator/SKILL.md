---
name: pytest-test-generator
description: Generate pytest test templates following TDD patterns. Automatically creates RED phase tests with fixtures, coverage markers, and integration test stubs.
---

# Pytest Test Generator

Generate standardized pytest tests following strict TDD discipline.

## Quick Start

**User says**: "Generate tests for UserService"

**Skill generates**:
```python
# tests/test_user_service.py
import pytest
from src.user_service import UserService

@pytest.fixture
def service():
    """Fixture for UserService"""
    return UserService()

def test_create_user_returns_user_id(service):
    """Test user creation returns ID"""
    result = service.create_user(name="John", email="john@example.com")
    assert result.id is not None

def test_get_user_by_id(service):
    """Test user retrieval by ID"""
    user = service.get_user(user_id=1)
    assert user is not None
```

## Templates

### 1. Service/Class Test Template
```python
import pytest
from {module_path} import {ClassName}

@pytest.fixture
def {fixture_name}():
    """Fixture for {ClassName}"""
    instance = {ClassName}(
        # Add constructor parameters
    )
    yield instance

def test_{method}_returns_expected(instance):
    """Test that {method} returns expected result"""
    result = instance.{method}()
    assert result is not None

def test_{method}_with_invalid_input(instance):
    """Test {method} handles invalid input"""
    with pytest.raises(ValueError):
        instance.{method}(invalid_param)
```

### 2. Function Test Template
```python
import pytest
from {module_path} import {function_name}

def test_{function_name}_basic():
    """Test basic functionality"""
    result = {function_name}(input_value)
    assert result == expected_value

def test_{function_name}_edge_case():
    """Test edge case handling"""
    result = {function_name}(edge_input)
    assert result is not None

@pytest.mark.parametrize("input_val,expected", [
    (1, 1),
    (2, 4),
    (3, 9),
])
def test_{function_name}_parametrized(input_val, expected):
    """Test with multiple inputs"""
    assert {function_name}(input_val) == expected
```

### 3. API/Integration Test Template
```python
import pytest
from fastapi.testclient import TestClient
from {app_module} import app

@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)

@pytest.mark.integration
def test_endpoint_returns_200(client):
    """Test endpoint success"""
    response = client.get("/api/endpoint")
    assert response.status_code == 200

@pytest.mark.integration
def test_endpoint_with_auth(client, auth_headers):
    """Test authenticated endpoint"""
    response = client.get("/api/protected", headers=auth_headers)
    assert response.status_code == 200
```

### 4. Async Test Template
```python
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def async_service():
    """Async fixture"""
    service = AsyncService()
    await service.connect()
    yield service
    await service.disconnect()

@pytest.mark.asyncio
async def test_async_operation(async_service):
    """Test async operation"""
    result = await async_service.fetch_data()
    assert result is not None
```

## Usage Patterns

### Pattern 1: New Class/Module
```
User: "Create tests for services/payment_service.py"

Skill:
1. Detect class and methods
2. Generate fixture with config
3. Create 3-5 core tests (RED phase)
4. Add integration test stub
5. Write to tests/test_payment_service.py
```

### Pattern 2: Add Test to Existing File
```
User: "Add test for calculate_discount method"

Skill:
1. Read existing tests/test_service.py
2. Generate new test function
3. Append to file
```

### Pattern 3: Integration Test
```
User: "Create integration test for API endpoints"

Skill:
1. Generate integration test in tests/integration/
2. Include client/fixture setup
3. Create end-to-end flow test
```

## Test Naming Conventions

| Pattern | Example | Use Case |
|---------|---------|----------|
| `test_{class}_{method}` | `test_user_service_create` | Class method test |
| `test_{action}_{expected}` | `test_login_returns_token` | Action-based test |
| `test_{scenario}` | `test_empty_input_raises` | Edge case |
| `test_{module}_integration` | `test_payment_integration` | Integration |

## Common Fixtures

```python
@pytest.fixture
def mock_db():
    """Mock database for testing"""
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def temp_file(tmp_path):
    """Temporary file fixture"""
    file = tmp_path / "test_file.txt"
    file.write_text("test content")
    return file

@pytest.fixture(scope="session")
def config():
    """Session-scoped config fixture"""
    return {"debug": True, "timeout": 30}
```

## Coverage Configuration

Auto-generate `pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: integration test
    slow: slow test (deselect with -m 'not slow')
addopts =
    --cov=src
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
```

## Output Format

**Generated test file**:
```python
"""
Tests for {module_name}
Coverage target: >80%
"""
import pytest
from {module_path} import {ClassName}

# Fixtures
@pytest.fixture
def {fixture_name}():
    """..."""
    pass

# Unit Tests (RED phase - should fail initially)
def test_{feature_1}():
    """Test {description}"""
    assert False  # RED: Not implemented yet

def test_{feature_2}():
    """Test {description}"""
    assert False  # RED: Not implemented yet

# Integration Tests
@pytest.mark.integration
def test_integration():
    """Test module integration"""
    pass
```

## Automatic Invocation

**Triggers**:
- "generate tests for [class/module]"
- "create test file for [file]"
- "add test for [function]"
- "write integration test for [module]"

**Does NOT trigger**:
- Complex test logic design (use subagent)
- Full TDD enforcement (use tdd-guard)
- Test debugging (use general debugging)

## Token Savings

| Task | Without Skill | With Skill | Savings |
|------|--------------|------------|---------|
| Class tests (5 tests) | ~1,200 tokens | ~200 tokens | 83% |
| Integration test | ~800 tokens | ~150 tokens | 81% |
| Fixture generation | ~400 tokens | ~100 tokens | 75% |

**Average Savings**: 80% (1,200 -> 240 tokens)
