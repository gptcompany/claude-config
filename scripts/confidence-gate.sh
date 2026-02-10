#!/bin/bash
# Confidence Gate - Autonomous Verification
# Wrapper script for workflow integration
#
# Exit codes:
#   0 = AUTO_APPROVE or approved by verifiers
#   1 = ITERATE - issues found, retry suggested
#   2 = HUMAN_REVIEW - human approval required
#   3 = Error

set -euo pipefail

# Defaults
CONFIDENCE=""
STEP_NAME="unknown"
THRESHOLD=85
JSON_OUTPUT=false
SAVE_RESULT=true
NO_ITERATE=false
EVOLVE=false
DETECT_EVOLVE=false
MAX_ITERATIONS=3
INPUT=""
FILES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -i|--input)
      INPUT="$2"
      shift 2
      ;;
    -f|--files)
      shift
      while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
        FILES+=("$1")
        shift
      done
      ;;
    -c|--confidence)
      CONFIDENCE="$2"
      shift 2
      ;;
    -s|--step)
      STEP_NAME="$2"
      shift 2
      ;;
    -t|--threshold)
      THRESHOLD="$2"
      shift 2
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    --no-save)
      SAVE_RESULT=false
      shift
      ;;
    --no-iterate)
      NO_ITERATE=true
      shift
      ;;
    -e|--evolve)
      EVOLVE=true
      shift
      ;;
    --detect-evolve)
      DETECT_EVOLVE=true
      shift
      ;;
    -m|--max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: confidence-gate [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -i, --input TEXT     Step output to verify (or stdin)"
      echo "  -f, --files FILE...  File paths to ingest (multiple files supported)"
      echo "  -c, --confidence N   Internal confidence score (0-100)"
      echo "  -s, --step NAME      Step name for tracking"
      echo "  -t, --threshold N    Auto-approve threshold (default: 85)"
      echo "  --json               JSON output for parsing"
      echo "  --no-save            Don't save to memory"
      echo "  --no-iterate         Skip iteration suggestions"
      echo "  -h, --help           Show this help"
      echo ""
      echo "Exit codes:"
      echo "  0 = Approved (proceed)"
      echo "  1 = Iterate (retry with feedback)"
      echo "  2 = Human review required"
      echo "  3 = Error"
      exit 0
      ;;
    *)
      # Unknown option, might be input
      if [[ -z "$INPUT" ]]; then
        INPUT="$1"
      fi
      shift
      ;;
  esac
done

# Handle file input mode
if [[ ${#FILES[@]} -gt 0 ]]; then
  # Files mode - pass directly to Python
  :
elif [[ -z "$INPUT" ]]; then
  if [[ ! -t 0 ]]; then
    INPUT=$(cat)
  else
    echo "Error: No input provided. Use --input, --files, or pipe data." >&2
    exit 3
  fi
fi

# Auto-calculate confidence if not provided
if [[ -z "$CONFIDENCE" ]]; then
  CONFIDENCE=$(python3 -c "
from pathlib import Path
import json
import sys

# Try validation result
val_file = Path('.claude/validation/last-result.json')
if val_file.exists():
    try:
        data = json.loads(val_file.read_text())
        score = data.get('overall_score', 70)
        print(int(score))
        sys.exit(0)
    except:
        pass

# Try test coverage
cov_file = Path('coverage.json')
if cov_file.exists():
    try:
        data = json.loads(cov_file.read_text())
        pct = data.get('totals', {}).get('percent_covered', 70)
        print(int(pct))
        sys.exit(0)
    except:
        pass

# Default
print(70)
" 2>/dev/null || echo 70)
fi

# Build command
CMD=(python3 ~/.claude/scripts/confidence_gate.py)
CMD+=(--confidence "$CONFIDENCE")
CMD+=(--step "$STEP_NAME")

if [[ "$JSON_OUTPUT" == "true" ]]; then
  CMD+=(--json)
fi

if [[ "$EVOLVE" == "true" ]]; then
  CMD+=(--evolve)
  CMD+=(--max-iterations "$MAX_ITERATIONS")
fi

if [[ "$DETECT_EVOLVE" == "true" ]]; then
  CMD+=(--detect-evolve)
fi

# Add files if specified
if [[ ${#FILES[@]} -gt 0 ]]; then
  CMD+=(--files "${FILES[@]}")
fi

# Run gate
if [[ ${#FILES[@]} -gt 0 ]]; then
  # Files mode - no stdin needed
  RESULT=$("${CMD[@]}" 2>&1)
else
  RESULT=$(echo "$INPUT" | "${CMD[@]}" 2>&1)
fi
GATE_EXIT=$?

# Parse decision from output
if [[ "$JSON_OUTPUT" == "true" ]]; then
  DECISION=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('decision','error'))" 2>/dev/null || echo "error")
else
  DECISION=$(echo "$RESULT" | grep "^Decision:" | awk '{print $2}' || echo "error")
fi

# Output result
echo "$RESULT"

# Save to memory if enabled
if [[ "$SAVE_RESULT" == "true" ]]; then
  PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  TIMESTAMP=$(date +%s)

  # Best effort save via claude-flow CLI
  npx claude-flow@v3alpha memory store \
    --key "gate:${PROJECT}:${STEP_NAME}:${TIMESTAMP}" \
    --value "{\"decision\":\"$DECISION\",\"confidence\":$CONFIDENCE,\"step\":\"$STEP_NAME\"}" \
    --namespace confidence-gate 2>/dev/null || true
fi

# Return appropriate exit code
case "$DECISION" in
  auto_approve)
    exit 0
    ;;
  cross_verify)
    # Check if approved after verification
    if [[ "$JSON_OUTPUT" == "true" ]]; then
      APPROVED=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('final_approved') else 'false')" 2>/dev/null || echo "false")
    else
      APPROVED=$(echo "$RESULT" | grep "Final Approved:" | awk '{print $3}' || echo "false")
    fi

    if [[ "$APPROVED" == "true" || "$APPROVED" == "True" ]]; then
      exit 0
    else
      exit 1  # Iterate
    fi
    ;;
  iterate)
    exit 1
    ;;
  human_review)
    exit 2
    ;;
  *)
    exit 3
    ;;
esac
