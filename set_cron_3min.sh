#!/bin/bash
# Set cron job to run every 3 minutes (for testing)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up 3-minute cron job..."

# Remove any existing cookie refresh jobs
crontab -l 2>/dev/null | grep -v "playwright_cookie_extractor.py" | crontab - 2>/dev/null || true

# Add new 3-minute job
(crontab -l 2>/dev/null; echo "*/3 * * * * cd $SCRIPT_DIR && python3 playwright_cookie_extractor.py >> logs/cookie_refresh.log 2>&1") | crontab -

echo "✅ Done!"
echo
echo "Current crontab:"
crontab -l

# Made with Bob
