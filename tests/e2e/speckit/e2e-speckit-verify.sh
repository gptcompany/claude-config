#!/bin/bash
# E2E SpecKit Verification - Verifica post-esecuzione pipeline SpecKit
# Usage: ./e2e-speckit-verify.sh [repo_path]

set +e  # Non uscire su errori

REPO_PATH="${1:-$(cat /tmp/e2e-speckit-last-repo.txt 2>/dev/null)}"

if [ -z "$REPO_PATH" ] || [ ! -d "$REPO_PATH" ]; then
    echo "Usage: $0 <repo_path>"
    echo "  or run e2e-speckit-setup.sh first"
    exit 1
fi

cd "$REPO_PATH"

echo "==========================================="
echo "  SpecKit E2E Verification"
echo "  Repo: $REPO_PATH"
echo "==========================================="
echo ""

PASSED=0
FAILED=0
WARNINGS=0

check() {
    local result=$1
    local name=$2
    local critical=${3:-false}

    if [ $result -eq 0 ]; then
        echo "  [PASS] $name"
        ((PASSED++))
    elif [ "$critical" = "true" ]; then
        echo "  [FAIL] $name"
        ((FAILED++))
    else
        echo "  [WARN] $name"
        ((WARNINGS++))
    fi
}

# ===========================================
# 1. Struttura specs/
# ===========================================
echo "--- Struttura specs/ ---"

[ -f "specs/01-calculator-cli.md" ]
check $? "spec.md exists" true

[ -d "specs/01-calculator-cli" ] || [ -d "specs/01-calculator-cli/" ]
check $? "spec directory created" true

[ -f "specs/01-calculator-cli/plan.md" ]
check $? "plan.md generated" true

[ -f "specs/01-calculator-cli/tasks.md" ]
check $? "tasks.md generated" true

# Verifica contenuto plan.md
if [ -f "specs/01-calculator-cli/plan.md" ]; then
    grep -qi "architecture\|design\|component\|module" "specs/01-calculator-cli/plan.md" 2>/dev/null
    check $? "plan.md has architecture section"
fi

# Verifica contenuto tasks.md
if [ -f "specs/01-calculator-cli/tasks.md" ]; then
    TASK_COUNT=$(grep -c "^\s*-\s*\[" "specs/01-calculator-cli/tasks.md" 2>/dev/null || echo 0)
    [ "$TASK_COUNT" -ge 4 ]
    check $? "tasks.md has $TASK_COUNT tasks (min 4)"
fi

# ===========================================
# 2. Codice implementato
# ===========================================
echo ""
echo "--- Codice Implementato ---"

# CLI module
[ -f "src/calculator/cli.py" ] || [ -f "src/calculator/main.py" ]
check $? "CLI module exists" true

# Operations module
[ -f "src/calculator/operations.py" ] || [ -f "src/calculator/core.py" ] || [ -f "src/calculator/math_ops.py" ]
check $? "Operations module exists" true

# Click usage
grep -rq "import click\|from click\|@click" src/ 2>/dev/null
check $? "Click framework used" true

# Math operations
grep -rq "def add\|def subtract\|def multiply\|def divide" src/ 2>/dev/null
check $? "Math operations implemented" true

# Error handling
grep -rq "ZeroDivisionError\|division.*zero\|cannot divide" src/ 2>/dev/null
check $? "Division by zero handling"

# ===========================================
# 3. Test
# ===========================================
echo ""
echo "--- Test ---"

ls tests/test_*.py >/dev/null 2>&1
check $? "Test files exist" true

# Conta test
TEST_COUNT=$(grep -r "def test_" tests/ 2>/dev/null | wc -l)
[ "$TEST_COUNT" -ge 6 ]
check $? "At least 6 test functions ($TEST_COUNT found)"

# Test per acceptance criteria
grep -rq "test.*add\|test.*subtract\|test.*mul\|test.*div" tests/ 2>/dev/null
check $? "Tests for all operations"

# Esegui test
if command -v python3 >/dev/null 2>&1; then
    python3 -m pytest tests/ -v --tb=short 2>/dev/null
    check $? "Tests pass" true
else
    echo "  [SKIP] python3 not available"
fi

# ===========================================
# 4. Validation artifacts
# ===========================================
echo ""
echo "--- Validation ---"

[ -f ".claude/validation/config.json" ]
check $? "validation config exists" true

# Check for validation run artifacts
[ -f ".claude/validation/last-run.json" ] || \
[ -f ".claude/validation/report.json" ] || \
ls .claude/validation/*.json 2>/dev/null | grep -qv config
check $? "Validation report generated"

# ===========================================
# 5. Claude-flow memory checkpoints
# ===========================================
echo ""
echo "--- Claude-flow Memory ---"

if command -v npx >/dev/null 2>&1; then
    MEMORY_RESULT=$(npx @claude-flow/cli@latest memory search --query "speckit 01 calculator" --limit 5 2>/dev/null)
    echo "$MEMORY_RESULT" | grep -qi "spec\|task\|implement\|speckit"
    check $? "Memory checkpoints exist"

    # Session save
    npx @claude-flow/cli@latest session list 2>/dev/null | grep -qi "speckit\|calculator"
    check $? "Session saved"
else
    echo "  [SKIP] npx not available"
fi

# ===========================================
# 6. GitHub sync
# ===========================================
echo ""
echo "--- GitHub Sync ---"

REPO_NAME=$(basename "$REPO_PATH")

if command -v gh >/dev/null 2>&1; then
    # Check issues from tasks
    ISSUE_COUNT=$(gh issue list -R "gptcompany/$REPO_NAME" --limit 20 2>/dev/null | wc -l)
    [ "$ISSUE_COUNT" -gt 0 ]
    check $? "GitHub issues created ($ISSUE_COUNT found)"

    # Check labels
    gh label list -R "gptcompany/$REPO_NAME" 2>/dev/null | grep -qi "task\|speckit\|feature"
    check $? "GitHub labels created"
else
    echo "  [SKIP] gh CLI not available"
fi

# ===========================================
# 7. Acceptance criteria coverage
# ===========================================
echo ""
echo "--- Acceptance Criteria ---"

# Check implementation covers acceptance criteria
grep -rq "add.*2.*3\|add(2.*3)\|2.*\\+.*3" tests/ 2>/dev/null
check $? "Test: calc add 2 3"

grep -rq "div.*10.*0\|divide.*10.*0\|ZeroDivision" tests/ 2>/dev/null
check $? "Test: calc div 10 0 (error)"

grep -rq "--help\|help" src/ 2>/dev/null
check $? "Help command implemented"

# ===========================================
# 8. Git history
# ===========================================
echo ""
echo "--- Git History ---"

COMMIT_COUNT=$(git log --oneline 2>/dev/null | wc -l)
[ "$COMMIT_COUNT" -ge 2 ]
check $? "Multiple commits ($COMMIT_COUNT found)"

# ===========================================
# Summary
# ===========================================
echo ""
echo "==========================================="
echo "  SUMMARY"
echo "==========================================="
echo "  Passed:   $PASSED"
echo "  Warnings: $WARNINGS"
echo "  Failed:   $FAILED"
echo "  Total:    $((PASSED + WARNINGS + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo "  [SUCCESS] SPECKIT E2E TEST PASSED (100%)"
        SCORE=10
    else
        echo "  [SUCCESS] SPECKIT E2E TEST PASSED (with warnings)"
        SCORE=$((10 - WARNINGS))
        [ $SCORE -lt 7 ] && SCORE=7
    fi
else
    echo "  [FAILURE] SPECKIT E2E TEST FAILED"
    SCORE=$((PASSED * 10 / (PASSED + FAILED + WARNINGS)))
fi

echo "  Score: $SCORE/10"
echo ""
echo "==========================================="

exit $FAILED
