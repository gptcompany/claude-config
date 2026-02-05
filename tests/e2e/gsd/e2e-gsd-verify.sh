#!/bin/bash
# E2E GSD Verification - Verifica post-esecuzione pipeline GSD
# Usage: ./e2e-gsd-verify.sh [repo_path]

set +e  # Non uscire su errori

REPO_PATH="${1:-$(cat /tmp/e2e-gsd-last-repo.txt 2>/dev/null)}"

if [ -z "$REPO_PATH" ] || [ ! -d "$REPO_PATH" ]; then
    echo "Usage: $0 <repo_path>"
    echo "  or run e2e-gsd-setup.sh first"
    exit 1
fi

cd "$REPO_PATH"

echo "==========================================="
echo "  GSD E2E Verification"
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
# 1. Struttura .planning/
# ===========================================
echo "--- Struttura .planning/ ---"

[ -f ".planning/PROJECT.md" ]
check $? "PROJECT.md exists" true

[ -f ".planning/ROADMAP.md" ]
check $? "ROADMAP.md exists" true

ls .planning/plans/PLAN-01-*.md >/dev/null 2>&1
check $? "PLAN-01-*.md generated" true

# Verifica contenuto PLAN
if ls .planning/plans/PLAN-01-*.md >/dev/null 2>&1; then
    PLAN_FILE=$(ls .planning/plans/PLAN-01-*.md | head -1)
    grep -q "## Task\|## Implementation\|## Steps" "$PLAN_FILE" 2>/dev/null
    check $? "PLAN has task breakdown"
fi

# ===========================================
# 2. Codice implementato
# ===========================================
echo ""
echo "--- Codice Implementato ---"

# Cerca file operations
[ -f "src/calculator/operations.py" ] || [ -f "src/calculator/core.py" ] || [ -f "src/calculator/math.py" ]
check $? "Core operations file exists" true

# Cerca funzioni matematiche
grep -rq "def add\|def subtract\|def multiply\|def divide" src/ 2>/dev/null
check $? "Math operations implemented" true

# Cerca CLI
[ -f "src/calculator/cli.py" ] || [ -f "src/calculator/main.py" ]
check $? "CLI module exists"

# Verifica import Click
grep -rq "import click\|from click" src/ 2>/dev/null
check $? "Click framework used"

# ===========================================
# 3. Test
# ===========================================
echo ""
echo "--- Test ---"

ls tests/test_*.py >/dev/null 2>&1
check $? "Test files exist" true

# Conta test
TEST_COUNT=$(grep -r "def test_" tests/ 2>/dev/null | wc -l)
[ "$TEST_COUNT" -ge 4 ]
check $? "At least 4 test functions ($TEST_COUNT found)"

# Esegui test
if command -v python3 >/dev/null 2>&1; then
    python3 -m pytest tests/ -v --tb=short 2>/dev/null
    check $? "Tests pass" true
else
    echo "  [SKIP] python3 not available"
fi

# ===========================================
# 4. Claude-flow memory checkpoints
# ===========================================
echo ""
echo "--- Claude-flow Memory ---"

# Cerca checkpoints in memory
if command -v npx >/dev/null 2>&1; then
    MEMORY_RESULT=$(npx @claude-flow/cli@latest memory search --query "gsd phase 01 calculator" --limit 5 2>/dev/null)
    echo "$MEMORY_RESULT" | grep -qi "phase\|plan\|task\|gsd"
    check $? "Memory checkpoints exist"

    # Verifica session save
    npx @claude-flow/cli@latest session list 2>/dev/null | grep -qi "gsd\|calculator"
    check $? "Session saved"
else
    echo "  [SKIP] npx not available"
fi

# ===========================================
# 5. GitHub sync
# ===========================================
echo ""
echo "--- GitHub Sync ---"

REPO_NAME=$(basename "$REPO_PATH")

if command -v gh >/dev/null 2>&1; then
    # Check issues
    ISSUE_COUNT=$(gh issue list -R "gptcompany/$REPO_NAME" --limit 10 2>/dev/null | wc -l)
    [ "$ISSUE_COUNT" -gt 0 ]
    check $? "GitHub issues created ($ISSUE_COUNT found)"

    # Check milestones
    MILESTONE_COUNT=$(gh api repos/gptcompany/$REPO_NAME/milestones 2>/dev/null | jq -e 'length' 2>/dev/null || echo 0)
    [ "$MILESTONE_COUNT" -gt 0 ]
    check $? "GitHub milestone created ($MILESTONE_COUNT found)"

    # Check project (optional)
    gh api graphql -f query='query{organization(login:"gptcompany"){projectsV2(first:5){nodes{title}}}}' 2>/dev/null | grep -qi "calculator"
    check $? "GitHub project board created"
else
    echo "  [SKIP] gh CLI not available"
fi

# ===========================================
# 6. Git history
# ===========================================
echo ""
echo "--- Git History ---"

COMMIT_COUNT=$(git log --oneline 2>/dev/null | wc -l)
[ "$COMMIT_COUNT" -ge 2 ]
check $? "Multiple commits ($COMMIT_COUNT found)"

git log --oneline 2>/dev/null | grep -qi "implement\|add\|feat\|fix"
check $? "Meaningful commit messages"

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
        echo "  [SUCCESS] GSD E2E TEST PASSED (100%)"
        SCORE=10
    else
        echo "  [SUCCESS] GSD E2E TEST PASSED (with warnings)"
        SCORE=$((10 - WARNINGS))
    fi
else
    echo "  [FAILURE] GSD E2E TEST FAILED"
    SCORE=$((PASSED * 10 / (PASSED + FAILED + WARNINGS)))
fi

echo "  Score: $SCORE/10"
echo ""
echo "==========================================="

exit $FAILED
