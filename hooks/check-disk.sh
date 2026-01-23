#!/bin/bash
# Check disk space before operations
DISK="/media/sam/1TB"
THRESHOLD=95

USAGE=$(df "$DISK" 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')

if [ -n "$USAGE" ] && [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "⚠️  WARNING: Disk $DISK at ${USAGE}% - run cleanup!"
    echo "   /media/sam/1TB/scripts/cleanup-git-temp.sh"
fi
