#!/bin/bash
# Backup Validator - Verify GitHub backups are recent and complete
#
# Usage:
#   ./backup-validator.sh              # Check all repositories
#   ./backup-validator.sh --fix        # Push any unpushed changes
#
# Checks:
#   - Local commits pushed to remote
#   - Last push age (warn if > 24h, critical if > 7d)
#   - Remote repository accessible

set -euo pipefail

FIX_MODE=false
EXIT_CODE=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fix) FIX_MODE=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Repository list from canonical.yaml
REPOS=(
    "/media/sam/1TB/nautilus_dev"
    "/media/sam/1TB/UTXOracle"
    "/media/sam/1TB/N8N_dev"
    "/media/sam/1TB/LiquidationHeatmap"
    "/home/sam/.claude"
)

# Thresholds (hours)
WARN_HOURS=24
CRITICAL_HOURS=168  # 7 days

# Colors
RED='\033[31m'
YELLOW='\033[33m'
GREEN='\033[32m'
BLUE='\033[34m'
NC='\033[0m'

echo "Backup Validator - Checking ${#REPOS[@]} repositories..."
echo ""

for repo_path in "${REPOS[@]}"; do
    repo_name=$(basename "$repo_path")
    status="ok"
    issues=""

    # Check if repo exists
    if [[ ! -d "$repo_path/.git" ]]; then
        printf "${RED}✗${NC} %-25s Not a git repository\n" "$repo_name"
        EXIT_CODE=2
        continue
    fi

    cd "$repo_path"

    # Get current branch
    current_branch=$(git branch --show-current 2>/dev/null || echo "HEAD")

    # Check remote accessibility (quick timeout)
    if ! timeout 5 git ls-remote --exit-code origin HEAD &>/dev/null; then
        issues+="Remote not accessible, "
        status="critical"
    fi

    # Check unpushed commits
    unpushed=$(git log origin/${current_branch}..HEAD --oneline 2>/dev/null | wc -l || echo 0)
    if [[ $unpushed -gt 0 ]]; then
        issues+="${unpushed} unpushed commits, "
        [[ "$status" == "ok" ]] && status="warning"

        # Fix mode: push unpushed commits
        if [[ "$FIX_MODE" == "true" ]]; then
            if git push origin "$current_branch" 2>/dev/null; then
                issues+="PUSHED, "
            fi
        fi
    fi

    # Check uncommitted changes
    uncommitted=$(git status --porcelain 2>/dev/null | wc -l || echo 0)
    if [[ $uncommitted -gt 0 ]]; then
        issues+="${uncommitted} uncommitted files, "
        [[ "$status" == "ok" ]] && status="info"
    fi

    # Check last push age
    last_push_date=$(git log origin/${current_branch} -1 --format=%ci 2>/dev/null || echo "")
    if [[ -n "$last_push_date" ]]; then
        last_push_ts=$(date -d "$last_push_date" +%s 2>/dev/null || echo 0)
        now_ts=$(date +%s)
        last_push_hours=$(( (now_ts - last_push_ts) / 3600 ))

        if [[ $last_push_hours -gt $CRITICAL_HOURS ]]; then
            issues+="Last push ${last_push_hours}h ago (>7d), "
            status="critical"
        elif [[ $last_push_hours -gt $WARN_HOURS ]]; then
            issues+="Last push ${last_push_hours}h ago (>24h), "
            [[ "$status" == "ok" ]] && status="warning"
        fi
    fi

    # Remove trailing comma
    issues="${issues%, }"

    # Display result
    case $status in
        ok)       printf "${GREEN}✓${NC} %-25s All backups current\n" "$repo_name" ;;
        info)     printf "${BLUE}ℹ${NC} %-25s %s\n" "$repo_name" "$issues" ;;
        warning)  printf "${YELLOW}⚠${NC} %-25s %s\n" "$repo_name" "$issues"; [[ $EXIT_CODE -lt 2 ]] && EXIT_CODE=1 ;;
        critical) printf "${RED}✗${NC} %-25s %s\n" "$repo_name" "$issues"; EXIT_CODE=2 ;;
    esac
done

echo ""
case $EXIT_CODE in
    0) echo "All backups are current and pushed." ;;
    1) echo "Some repositories have warnings." ;;
    2) echo "CRITICAL: Some repositories need attention!" ;;
esac

exit $EXIT_CODE
