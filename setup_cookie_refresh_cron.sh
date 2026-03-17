#!/bin/bash
# Setup automatic cookie refresh cron job
# This prevents cookies from expiring by refreshing them every 30 minutes

set -e

echo "========================================================================"
echo "🔧 Setting up automatic cookie refresh cron job"
echo "========================================================================"
echo

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📂 Project directory: $SCRIPT_DIR"
echo

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"
echo "✅ Logs directory ready"
echo

# Create the cron job entry
CRON_JOB="*/30 * * * * cd $SCRIPT_DIR && python3 playwright_cookie_extractor.py >> logs/cookie_refresh.log 2>&1"

echo "📝 Cron job to be added:"
echo "   $CRON_JOB"
echo

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "playwright_cookie_extractor.py"; then
    echo "⚠️  Cron job already exists. Removing old one..."
    crontab -l 2>/dev/null | grep -v "playwright_cookie_extractor.py" | crontab -
    echo "✅ Old cron job removed"
fi

# Add the new cron job
echo "➕ Adding new cron job..."
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
echo "✅ Cron job added successfully!"
echo

# Verify the cron job was added
echo "🔍 Current crontab entries:"
echo "----------------------------------------------------------------------"
crontab -l | grep "playwright_cookie_extractor.py" || echo "No cookie refresh jobs found"
echo "----------------------------------------------------------------------"
echo

# Create a manual refresh script for testing
cat > "$SCRIPT_DIR/refresh_cookies_now.sh" << 'REFRESH_EOF'
#!/bin/bash
# Manually refresh cookies and restart the application

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "🔄 Manually refreshing cookies"
echo "========================================================================"
echo

# Run the cookie extractor
echo "Step 1: Extracting fresh cookies..."
python3 playwright_cookie_extractor.py

if [ $? -eq 0 ]; then
    echo
    echo "✅ Cookies extracted successfully!"
    echo
    
    # Restart the application
    echo "Step 2: Restarting application..."
    docker-compose restart
    
    echo
    echo "✅ Application restarted!"
    echo
    
    # Show logs
    echo "Step 3: Checking authentication..."
    echo "----------------------------------------------------------------------"
    docker-compose logs --tail=20 | grep -i "auth\|cookie" || true
    echo "----------------------------------------------------------------------"
    echo
    
    echo "✅ Cookie refresh complete!"
else
    echo
    echo "❌ Cookie extraction failed!"
    exit 1
fi
REFRESH_EOF

chmod +x "$SCRIPT_DIR/refresh_cookies_now.sh"
echo "✅ Created manual refresh script: refresh_cookies_now.sh"
echo

# Create a script to check cookie refresh logs
cat > "$SCRIPT_DIR/check_cookie_refresh_logs.sh" << 'LOGS_EOF'
#!/bin/bash
# Check cookie refresh logs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/cookie_refresh.log"

echo "========================================================================"
echo "📋 Cookie Refresh Logs"
echo "========================================================================"
echo

if [ -f "$LOG_FILE" ]; then
    echo "Last 50 lines of cookie refresh log:"
    echo "----------------------------------------------------------------------"
    tail -n 50 "$LOG_FILE"
    echo "----------------------------------------------------------------------"
    echo
    
    # Show summary
    echo "📊 Summary:"
    echo "  Total refresh attempts: $(grep -c "Playwright Cookie Extractor" "$LOG_FILE" 2>/dev/null || echo "0")"
    echo "  Successful refreshes: $(grep -c "Successfully extracted" "$LOG_FILE" 2>/dev/null || echo "0")"
    echo "  Failed refreshes: $(grep -c "Failed to extract" "$LOG_FILE" 2>/dev/null || echo "0")"
    echo
else
    echo "⚠️  No log file found yet: $LOG_FILE"
    echo "   The cron job hasn't run yet or logging is not working."
fi
LOGS_EOF

chmod +x "$SCRIPT_DIR/check_cookie_refresh_logs.sh"
echo "✅ Created log checker script: check_cookie_refresh_logs.sh"
echo

# Summary
echo "========================================================================"
echo "✅ Setup Complete!"
echo "========================================================================"
echo
echo "📝 What was configured:"
echo "  • Cron job runs every 30 minutes"
echo "  • Cookies are automatically refreshed"
echo "  • Logs saved to: logs/cookie_refresh.log"
echo
echo "🔧 Available commands:"
echo
echo "  1. Manually refresh cookies now:"
echo "     ./refresh_cookies_now.sh"
echo
echo "  2. Check cookie refresh logs:"
echo "     ./check_cookie_refresh_logs.sh"
echo
echo "  3. View cron jobs:"
echo "     crontab -l"
echo
echo "  4. Remove cron job:"
echo "     crontab -l | grep -v 'playwright_cookie_extractor.py' | crontab -"
echo
echo "  5. Test cron job manually:"
echo "     cd $SCRIPT_DIR && python3 playwright_cookie_extractor.py"
echo
echo "⏰ Next automatic refresh: $(date -d '+30 minutes' '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -v+30M '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'In 30 minutes')"
echo
echo "💡 Tips:"
echo "  • First cron run requires manual login (passkey)"
echo "  • After first run, subsequent runs are automatic"
echo "  • Check logs regularly: ./check_cookie_refresh_logs.sh"
echo "  • If cookies expire, run: ./refresh_cookies_now.sh"
echo
echo "========================================================================"

# Made with Bob
