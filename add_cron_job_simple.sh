#!/bin/bash
# Simple script to add cron job for cookie refresh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================================================"
echo "➕ Adding cron job for cookie refresh"
echo "========================================================================"
echo

# Create a temporary file with the cron job
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Check if job already exists
if grep -q "playwright_cookie_extractor.py" "$TEMP_CRON"; then
    echo "⚠️  Cron job already exists. Removing old one..."
    grep -v "playwright_cookie_extractor.py" "$TEMP_CRON" > "${TEMP_CRON}.new"
    mv "${TEMP_CRON}.new" "$TEMP_CRON"
fi

# Add the new cron job
echo "*/30 * * * * cd $SCRIPT_DIR && python3 playwright_cookie_extractor.py >> logs/cookie_refresh.log 2>&1" >> "$TEMP_CRON"

# Install the new crontab
crontab "$TEMP_CRON"

# Clean up
rm "$TEMP_CRON"

echo "✅ Cron job added successfully!"
echo

# Verify
echo "🔍 Current crontab:"
echo "----------------------------------------------------------------------"
crontab -l
echo "----------------------------------------------------------------------"
echo

echo "✅ Done! Cookie refresh will run every 30 minutes."

# Made with Bob
