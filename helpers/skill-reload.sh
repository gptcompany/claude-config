#!/bin/bash
# Skill Reload Helper - Persists active skills across context compaction
# Usage: source this file and call track_skill / reload_all

ACTIVE_SKILLS="${HOME}/.claude/.active-skills"

# Track a skill as active (deduplicates automatically)
track_skill() {
    local skill_name="$1"
    if [ -z "$skill_name" ]; then
        echo "Usage: track_skill <skill_name>" >&2
        return 1
    fi
    echo "$skill_name" >> "$ACTIVE_SKILLS"
    sort -u "$ACTIVE_SKILLS" -o "$ACTIVE_SKILLS"
    echo "[SKILL] Tracked: $skill_name"
}

# Reload all tracked skills (call after context compaction)
reload_all() {
    if [ ! -f "$ACTIVE_SKILLS" ]; then
        echo "[SKILL] No active skills to reload"
        return 0
    fi

    local count=0
    while IFS= read -r skill; do
        if [ -n "$skill" ]; then
            echo "[RELOAD] $skill"
            count=$((count + 1))
        fi
    done < "$ACTIVE_SKILLS"

    echo "[SKILL] Reloaded $count skills"
    return 0
}

# List tracked skills
list_skills() {
    if [ ! -f "$ACTIVE_SKILLS" ]; then
        echo "No active skills"
        return 0
    fi
    echo "Active skills:"
    cat "$ACTIVE_SKILLS"
}

# Clear all tracked skills
clear_skills() {
    rm -f "$ACTIVE_SKILLS"
    echo "[SKILL] Cleared all tracked skills"
}

# Export functions for subshells
export -f track_skill reload_all list_skills clear_skills
export ACTIVE_SKILLS
