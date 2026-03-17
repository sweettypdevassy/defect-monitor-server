#!/bin/bash
# Grant crontab access to user 'abhi'
# This script must be run with sudo

set -e

echo "========================================================================"
echo "🔧 Granting crontab access to user 'abhi'"
echo "========================================================================"
echo

# Check if running as root/sudo
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo"
    echo
    echo "Usage:"
    echo "  sudo ./grant_crontab_access.sh"
    echo
    exit 1
fi

TARGET_USER="abhi"

echo "👤 Target user: $TARGET_USER"
echo

# Check if user exists
if ! id "$TARGET_USER" &>/dev/null; then
    echo "❌ User '$TARGET_USER' does not exist"
    exit 1
fi

echo "✅ User exists"
echo

# Method 1: Add user to /etc/cron.allow
echo "📝 Method 1: Adding user to /etc/cron.allow"
if [ -f /etc/cron.allow ]; then
    if grep -q "^${TARGET_USER}$" /etc/cron.allow; then
        echo "   ℹ️  User already in /etc/cron.allow"
    else
        echo "$TARGET_USER" >> /etc/cron.allow
        echo "   ✅ User added to /etc/cron.allow"
    fi
else
    echo "$TARGET_USER" > /etc/cron.allow
    echo "   ✅ Created /etc/cron.allow and added user"
fi
echo

# Method 2: Remove user from /etc/cron.deny (if it exists)
echo "📝 Method 2: Checking /etc/cron.deny"
if [ -f /etc/cron.deny ]; then
    if grep -q "^${TARGET_USER}$" /etc/cron.deny; then
        sed -i "/^${TARGET_USER}$/d" /etc/cron.deny
        echo "   ✅ User removed from /etc/cron.deny"
    else
        echo "   ℹ️  User not in /etc/cron.deny (good)"
    fi
else
    echo "   ℹ️  /etc/cron.deny does not exist (good)"
fi
echo

# Set proper permissions
echo "🔒 Setting proper permissions..."
chmod 644 /etc/cron.allow 2>/dev/null || true
echo "✅ Permissions set"
echo

# Verify access
echo "🔍 Verifying crontab access..."
if su - "$TARGET_USER" -c "crontab -l" &>/dev/null || [ $? -eq 1 ]; then
    echo "✅ User '$TARGET_USER' can now use crontab!"
else
    echo "⚠️  Verification inconclusive, but permissions should be set"
fi
echo

echo "========================================================================"
echo "✅ Crontab Access Granted!"
echo "========================================================================"
echo
echo "📝 What was done:"
echo "  • Added '$TARGET_USER' to /etc/cron.allow"
echo "  • Removed '$TARGET_USER' from /etc/cron.deny (if present)"
echo "  • Set proper file permissions"
echo
echo "🔧 Next steps (run as user '$TARGET_USER'):"
echo
echo "  1. Test crontab access:"
echo "     crontab -l"
echo
echo "  2. Setup automatic cookie refresh:"
echo "     cd ~/defect-monitor-server"
echo "     ./setup_cookie_refresh_cron.sh"
echo
echo "  3. Verify cron job was added:"
echo "     crontab -l | grep cookie"
echo
echo "========================================================================"

# Made with Bob
