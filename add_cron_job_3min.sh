#!/bin/bash
# Add cron job for cookie refresh - EVERY 3 MINUTES (for testing)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================================================"
echo "➕ Adding cron job for cookie refresh (EVERY 3 MINUTES - TESTING)"
echo "========================================================================"
echo

# Create a temporary file with the cron job
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Check if job already exists and remove it
if grep -q "playwright_cookie_extractor.py" "$TEMP_CRON"; then
    echo "⚠️  Cron job already exists. Removing old one..."
    grep -v "playwright_cookie_extractor.py" "$TEMP_CRON" > "${TEMP_CRON}.tmp"
    cat "${TEMP_CRON}.tmp" > "$TEMP_CRON"
    rm "${TEMP_CRON}.tmp"
    echo "✅ Old cron job removed"
fi

# Add the new cron job - EVERY 3 MINUTES
echo "*/3 * * * * cd $SCRIPT_DIR && python3 playwright_cookie_extractor.py >> logs/cookie_refresh.log 2>&1" >> "$TEMP_CRON"
echo "✅ New cron job added (every 3 minutes)"

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

echo "⏰ Schedule: Every 3 minutes (for testing)"
echo "📝 Next run: Within 3 minutes"
echo
echo "💡 To monitor:"
echo "   tail -f logs/cookie_refresh.log"
echo
echo "⚠️  Remember to change back to 30 minutes after testing:"
echo "   ./add_cron_job_simple.sh"
echo

# Made with Bob
