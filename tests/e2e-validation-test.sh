#!/bin/bash
# E2E Validation Test - Tests all Phase 1-4 fixes
# Score: PASS if all tests green, FAIL otherwise

# Don't exit on error - we handle errors manually
set +e

echo "=========================================="
echo "  E2E Validation Test Suite"
echo "  Testing Phase 1-4 Fixes"
echo "=========================================="
echo ""

PASSED=0
FAILED=0

# Helper function
test_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ PASS: $2"
        ((PASSED++))
    else
        echo "❌ FAIL: $2"
        ((FAILED++))
    fi
}

# ===========================================
# PHASE 1: Critical Fixes
# ===========================================
echo "--- PHASE 1: Critical Fixes ---"

# FIX 5: confidence-gate model names
echo -n "Testing FIX 5 (config.yaml models)... "
if grep -q "google/gemini-3-flash-preview" ~/.claude/validation-framework/.claude-flow/config.yaml 2>/dev/null && \
   grep -q "moonshotai/kimi-k2.5" ~/.claude/validation-framework/.claude-flow/config.yaml 2>/dev/null; then
    test_result 0 "FIX 5 - config.yaml models correct"
else
    test_result 1 "FIX 5 - config.yaml models"
fi

# FIX 7: GH_PROJECT_ORG
echo -n "Testing FIX 7 (GH_PROJECT_ORG)... "
if dotenvx get GH_PROJECT_ORG -f /media/sam/1TB/.env 2>/dev/null | grep -q "gptcompany"; then
    test_result 0 "FIX 7 - GH_PROJECT_ORG=gptcompany"
else
    test_result 1 "FIX 7 - GH_PROJECT_ORG missing"
fi

# ===========================================
# PHASE 2: Structural Fixes
# ===========================================
echo ""
echo "--- PHASE 2: Structural Fixes ---"

# FIX 4: spawn_agent context injection
echo -n "Testing FIX 4 (context injection)... "
if grep -q "inject_context" ~/.claude/templates/validation/orchestrator.py 2>/dev/null && \
   grep -q "CONTEXT.md" ~/.claude/templates/validation/orchestrator.py 2>/dev/null; then
    test_result 0 "FIX 4 - spawn_agent context injection"
else
    test_result 1 "FIX 4 - spawn_agent context injection"
fi

# FIX 6: discuss-phase JSON round
echo -n "Testing FIX 6 (JSON round output)... "
if grep -q "round_tracking" ~/.claude/commands/gsd/discuss-phase.md 2>/dev/null && \
   grep -q "confidence_delta" ~/.claude/commands/gsd/discuss-phase.md 2>/dev/null; then
    test_result 0 "FIX 6 - discuss-phase JSON round output"
else
    test_result 1 "FIX 6 - discuss-phase JSON round output"
fi

# FIX 2: Visual validator
echo -n "Testing FIX 2 (visual validator)... "
cd ~/.claude/templates/validation && python3 -c "
import sys
sys.path.insert(0, '.')
from validators.visual.validator import VisualTargetValidator
v = VisualTargetValidator()
avail = v.is_available()
assert avail['ssim'] or avail['odiff'], 'No visual tools available'
" 2>/dev/null
test_result $? "FIX 2 - Visual validator available"

# ===========================================
# PHASE 3: Integration Fixes
# ===========================================
echo ""
echo "--- PHASE 3: Integration Fixes ---"

# FIX 3: research_unified.py
echo -n "Testing FIX 3 (research_unified)... "
if [ -f ~/.claude/scripts/research_unified.py ] && \
   grep -q "search_academic" ~/.claude/scripts/research_unified.py && \
   grep -q "search_context7" ~/.claude/scripts/research_unified.py && \
   grep -q "search_memory" ~/.claude/scripts/research_unified.py && \
   grep -q "search_local_docs" ~/.claude/scripts/research_unified.py; then
    test_result 0 "FIX 3 - research_unified.py (4 sources)"
else
    test_result 1 "FIX 3 - research_unified.py"
fi

# FIX 8: skill-reload + skill-audit
echo -n "Testing FIX 8 (skill helpers)... "
if [ -x ~/.claude/helpers/skill-reload.sh ] && [ -x ~/.claude/helpers/skill-audit.py ]; then
    test_result 0 "FIX 8 - skill-reload.sh + skill-audit.py"
else
    test_result 1 "FIX 8 - skill helpers missing or not executable"
fi

# ===========================================
# PHASE 4: Optimization
# ===========================================
echo ""
echo "--- PHASE 4: Optimization ---"

# FIX 1: claude-flow daemon
echo -n "Testing FIX 1 (daemon status)... "
cd ~/.claude/validation-framework
DAEMON_STATUS=$(npx @claude-flow/cli@latest daemon status 2>&1 | head -5)
if echo "$DAEMON_STATUS" | grep -q "RUNNING\|Workers Enabled"; then
    test_result 0 "FIX 1 - claude-flow daemon running"
else
    test_result 1 "FIX 1 - claude-flow daemon not running"
fi

# ===========================================
# FUNCTIONAL TEST: confidence-gate
# ===========================================
echo ""
echo "--- FUNCTIONAL TEST: confidence-gate ---"

echo -n "Testing confidence-gate API call... "
cd /tmp
RESULT=$(dotenvx run -f /media/sam/1TB/.env -- python3 ~/.claude/scripts/confidence_gate.py \
    --output "Implement a simple REST API with FastAPI that returns hello world" \
    --json 2>&1)

# Check if JSON output contains expected fields
if echo "$RESULT" | grep -q '"decision":' && echo "$RESULT" | grep -q '"provider":'; then
    test_result 0 "confidence-gate functional test (Gemini + Kimi responded)"
else
    test_result 1 "confidence-gate functional test"
    echo "  Output: $(echo "$RESULT" | tail -10)"
fi

# ===========================================
# SUMMARY
# ===========================================
echo ""
echo "=========================================="
echo "  SUMMARY"
echo "=========================================="
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo "  Total:  $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "  ✅ ALL TESTS PASSED"
    echo "  Score: 10/10"
    exit 0
else
    echo "  ⚠️  SOME TESTS FAILED"
    SCORE=$((PASSED * 10 / (PASSED + FAILED)))
    echo "  Score: $SCORE/10"
    exit 1
fi
