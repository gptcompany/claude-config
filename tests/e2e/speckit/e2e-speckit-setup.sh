#!/bin/bash
# E2E SpecKit Setup - Crea repo isolata per test completo pipeline SpecKit
# Usage: ./e2e-speckit-setup.sh

set -e

REPO_NAME="e2e-speckit-calculator-$(date +%s)"
REPO_PATH="/tmp/$REPO_NAME"

echo "==========================================="
echo "  SpecKit E2E Test Setup"
echo "==========================================="
echo ""

# 1. Crea repo locale
echo "[1/6] Creating local repository..."
mkdir -p "$REPO_PATH"
cd "$REPO_PATH"
git init -q

# 2. Crea struttura .claude/validation/
echo "[2/6] Creating .claude/validation/ structure..."
mkdir -p .claude/validation

cat > .claude/validation/config.json << 'EOF'
{
  "domain": "cli-tools",
  "anti_patterns": ["eval()", "exec()", "os.system("],
  "research_keywords": {
    "trigger": ["click", "argparse", "cli", "command-line"],
    "skip": ["gui", "web", "flask", "django"]
  },
  "validation": {
    "tiers": {
      "tier1": ["syntax", "security", "tests"],
      "tier2": ["coverage", "complexity", "documentation"],
      "tier3": ["performance", "maintainability"]
    },
    "thresholds": {
      "coverage_min": 80,
      "complexity_max": 10
    }
  }
}
EOF

# 3. Crea spec iniziale
echo "[3/6] Creating spec file..."
mkdir -p specs

cat > specs/01-calculator-cli.md << 'EOF'
# Feature: Calculator CLI

## Description
Implementare una CLI calculator in Python che supporta operazioni matematiche base.

## Requirements

### Functional
1. Supportare operazioni: addizione, sottrazione, moltiplicazione, divisione
2. Input via argomenti CLI: `calc <operation> <num1> <num2>`
3. Gestire errori (divisione per zero, input non validi)
4. Output formattato con precisione configurabile (default: 2 decimali)
5. Help integrato con `--help`

### Non-Functional
1. Tempo di risposta < 100ms
2. Zero dipendenze runtime oltre Click
3. Compatibile Python 3.11+

## Acceptance Criteria

- [ ] `calc add 2 3` restituisce `5.00`
- [ ] `calc sub 10 4` restituisce `6.00`
- [ ] `calc mul 3 4` restituisce `12.00`
- [ ] `calc div 10 2` restituisce `5.00`
- [ ] `calc div 10 0` mostra messaggio errore (non crash)
- [ ] `calc add abc 2` mostra messaggio errore input non valido
- [ ] `calc --help` mostra usage completo
- [ ] `calc add 1.5 2.5 --precision 4` restituisce `4.0000`

## Tech Constraints

- Python 3.11+
- Click per CLI parsing
- No dipendenze esterne oltre Click
- Struttura package standard (src layout)

## Out of Scope

- Operazioni complesse (radice, potenza, etc.)
- Modalita interattiva
- GUI
- History dei calcoli
EOF

# 4. Crea struttura base progetto
echo "[4/6] Creating project structure..."
mkdir -p src/calculator tests

cat > src/__init__.py << 'EOF'
"""Calculator CLI package."""
EOF

cat > src/calculator/__init__.py << 'EOF'
"""Calculator module."""
EOF

cat > tests/__init__.py << 'EOF'
"""Test package."""
EOF

cat > pyproject.toml << 'EOF'
[project]
name = "calculator-cli"
version = "0.1.0"
description = "E2E Test Calculator CLI - SpecKit"
requires-python = ">=3.11"
dependencies = ["click>=8.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov"]

[project.scripts]
calc = "calculator.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src/calculator"]
branch = true

[tool.coverage.report]
fail_under = 80
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

# 5. Init git e commit iniziale
echo "[5/6] Creating initial commit..."
git add -A
git commit -q -m "chore: initial project structure for SpecKit E2E test"

# 6. Crea repo GitHub (gptcompany org)
echo "[6/6] Creating GitHub repository..."
if gh repo create "gptcompany/$REPO_NAME" --private --source=. --push 2>/dev/null; then
    GITHUB_URL="https://github.com/gptcompany/$REPO_NAME"
else
    echo "  [WARN] GitHub repo creation failed - continuing with local only"
    GITHUB_URL="N/A (local only)"
fi

# Init claude-flow
if [ -x ~/.claude/scripts/claude-flow-init.sh ]; then
    ~/.claude/scripts/claude-flow-init.sh 2>/dev/null || true
else
    npx @claude-flow/cli@latest init 2>/dev/null || true
fi

# Output info
echo ""
echo "==========================================="
echo "  SpecKit E2E Test Repo Created"
echo "==========================================="
echo ""
echo "  Path:   $REPO_PATH"
echo "  GitHub: $GITHUB_URL"
echo "  Spec:   specs/01-calculator-cli.md"
echo ""
echo "==========================================="
echo "  NEXT STEPS"
echo "==========================================="
echo ""
echo "  1. Apri NUOVA sessione Claude Code"
echo "  2. cd $REPO_PATH"
echo "  3. Copia prompt da: ~/.claude/tests/e2e/speckit/e2e-speckit-prompt.md"
echo "  4. Esegui i comandi SpecKit uno per uno"
echo ""
echo "  Dopo completamento, verifica con:"
echo "  ~/.claude/tests/e2e/speckit/e2e-speckit-verify.sh $REPO_PATH"
echo ""

# Salva path per riferimento
echo "$REPO_PATH" > /tmp/e2e-speckit-last-repo.txt
