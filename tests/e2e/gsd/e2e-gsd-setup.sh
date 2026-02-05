#!/bin/bash
# E2E GSD Setup - Crea repo isolata per test completo pipeline GSD
# Usage: ./e2e-gsd-setup.sh

set -e

REPO_NAME="e2e-gsd-calculator-$(date +%s)"
REPO_PATH="/tmp/$REPO_NAME"

echo "==========================================="
echo "  GSD E2E Test Setup"
echo "==========================================="
echo ""

# 1. Crea repo locale
echo "[1/6] Creating local repository..."
mkdir -p "$REPO_PATH"
cd "$REPO_PATH"
git init -q

# 2. Crea struttura .planning/
echo "[2/6] Creating .planning/ structure..."
mkdir -p .planning/plans

cat > .planning/PROJECT.md << 'EOF'
# Calculator CLI - E2E Test Project

## Vision
CLI calculator per operazioni matematiche base.

## Scope
- Operazioni: +, -, *, /
- Input da CLI args
- Output formattato

## Tech Stack
- Python 3.11+
- Click per CLI
- Pytest per test

## Success Criteria
- Tutte le operazioni funzionano correttamente
- Gestione errori (divisione per zero)
- Coverage test >= 80%
EOF

cat > .planning/ROADMAP.md << 'EOF'
# Roadmap - Calculator CLI

## Milestone 1: MVP (v0.1.0)

### Phase 01: Core Operations
- [ ] Implementare addizione
- [ ] Implementare sottrazione
- [ ] Implementare moltiplicazione
- [ ] Implementare divisione
- [ ] Gestione errori divisione per zero

### Phase 02: CLI Interface
- [ ] Setup Click
- [ ] Parsing argomenti
- [ ] Output formattato
- [ ] Help command

### Phase 03: Testing & Quality
- [ ] Unit tests operazioni
- [ ] Integration tests CLI
- [ ] Coverage 80%+
- [ ] Documentazione
EOF

# 3. Crea struttura base progetto
echo "[3/6] Creating project structure..."
mkdir -p src/calculator tests

cat > src/__init__.py << 'EOF'
"""Calculator CLI package."""
EOF

cat > src/calculator/__init__.py << 'EOF'
"""Calculator module."""
from .operations import add, subtract, multiply, divide

__all__ = ["add", "subtract", "multiply", "divide"]
EOF

cat > tests/__init__.py << 'EOF'
"""Test package."""
EOF

cat > pyproject.toml << 'EOF'
[project]
name = "calculator-cli"
version = "0.1.0"
description = "E2E Test Calculator CLI"
requires-python = ">=3.11"
dependencies = ["click>=8.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov"]

[project.scripts]
calc = "calculator.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
EOF

cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
dist/
*.egg-info/
.venv/
EOF

# 4. Init git e commit iniziale
echo "[4/6] Creating initial commit..."
git add -A
git commit -q -m "chore: initial project structure for E2E test"

# 5. Crea repo GitHub (gptcompany org)
echo "[5/6] Creating GitHub repository..."
if gh repo create "gptcompany/$REPO_NAME" --private --source=. --push 2>/dev/null; then
    GITHUB_URL="https://github.com/gptcompany/$REPO_NAME"
else
    echo "  [WARN] GitHub repo creation failed - continuing with local only"
    GITHUB_URL="N/A (local only)"
fi

# 6. Init claude-flow
echo "[6/6] Initializing claude-flow..."
if [ -x ~/.claude/scripts/claude-flow-init.sh ]; then
    ~/.claude/scripts/claude-flow-init.sh 2>/dev/null || true
else
    npx @claude-flow/cli@latest init 2>/dev/null || true
fi

# Output info
echo ""
echo "==========================================="
echo "  GSD E2E Test Repo Created"
echo "==========================================="
echo ""
echo "  Path:   $REPO_PATH"
echo "  GitHub: $GITHUB_URL"
echo ""
echo "==========================================="
echo "  NEXT STEPS"
echo "==========================================="
echo ""
echo "  1. Apri NUOVA sessione Claude Code"
echo "  2. cd $REPO_PATH"
echo "  3. Copia prompt da: ~/.claude/tests/e2e/gsd/e2e-gsd-prompt.md"
echo "  4. Esegui i comandi GSD uno per uno"
echo ""
echo "  Dopo completamento, verifica con:"
echo "  ~/.claude/tests/e2e/gsd/e2e-gsd-verify.sh $REPO_PATH"
echo ""

# Salva path per riferimento
echo "$REPO_PATH" > /tmp/e2e-gsd-last-repo.txt
