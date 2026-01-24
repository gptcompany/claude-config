#!/bin/bash
# Safe SOPS edit script with automatic backup and protection
# Usage: sops-edit.sh
# SSOT: /media/sam/1TB/.env.enc

SOPS_FILE="/media/sam/1TB/.env.enc"
BACKUP_DIR="/media/sam/1TB"
AGE_KEY="age14erzqqnt9h4zlv6v003gw3dznh0970euwt7fhtugfc92sfw7lyysn7s65f"

# Check if file exists
if [ ! -f "$SOPS_FILE" ]; then
    echo "ERROR: SOPS file not found at $SOPS_FILE" >&2
    exit 1
fi

# Create timestamped backup
BACKUP_FILE="${BACKUP_DIR}/.env.enc.bak.$(date +%Y%m%d%H%M%S)"
cp "$SOPS_FILE" "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"

# Remove immutable flag
echo "Removing immutable flag..."
sudo chattr -i "$SOPS_FILE"

# Edit with SOPS
echo "Opening SOPS editor..."
sops --input-type dotenv --output-type dotenv "$SOPS_FILE"
EDIT_STATUS=$?

# Verify file is not empty after edit
if [ ! -s "$SOPS_FILE" ]; then
    echo "ERROR: File is empty after edit! Restoring backup..." >&2
    cp "$BACKUP_FILE" "$SOPS_FILE"
    echo "Backup restored."
fi

# Restore immutable flag
echo "Restoring immutable flag..."
sudo chattr +i "$SOPS_FILE"

# Show key count
KEY_COUNT=$(sops --input-type dotenv --output-type dotenv -d "$SOPS_FILE" 2>/dev/null | grep -c "=")
echo "Current key count: $KEY_COUNT"

exit $EDIT_STATUS
