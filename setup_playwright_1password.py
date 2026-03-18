#!/usr/bin/env python3
"""
One-Time Setup Script for Playwright + 1Password
This script opens Chrome with Playwright's profile so you can:
1. Install 1Password extension
2. Login to 1Password
3. Login to IBM with passkey
4. After this, all future runs will work automatically!
"""

import os
import sys
import asyncio
from playwright.async_api import async_playwright

# Color codes for terminal output
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

def print_colored(message, color):
    """Print colored message to terminal"""
    print(f"{color}{message}{Colors.NC}")

def print_step(step_num, message):
    """Print step header"""
    print()
    print_colored("=" * 70, Colors.CYAN)
    print_colored(f"STEP {step_num}: {message}", Colors.BOLD)
    print_colored("=" * 70, Colors.CYAN)
    print()

async def setup_playwright_with_1password():
    """
    Open Playwright Chrome browser for one-time setup
    """
    user_data_dir = os.path.expanduser("~/.playwright-chrome-profile")
    
    print_colored("=" * 70, Colors.BLUE)
    print_colored("🎭 Playwright + 1Password One-Time Setup", Colors.BOLD)
    print_colored("=" * 70, Colors.BLUE)
    print()
    print_colored("This script will help you set up 1Password in Playwright's Chrome.", Colors.YELLOW)
    print_colored("You only need to do this ONCE!", Colors.GREEN)
    print()
    
    print_colored(f"📂 Chrome Profile Location: {user_data_dir}", Colors.BLUE)
    print()
    
    # Check if DISPLAY is set
    display = os.environ.get('DISPLAY')
    if not display:
        print_colored("❌ ERROR: No DISPLAY environment variable found!", Colors.RED)
        print()
        print_colored("💡 Solution:", Colors.YELLOW)
        print("   export DISPLAY=:1")
        print("   # Or whatever display number you're using")
        print()
        sys.exit(1)
    
    print_colored(f"✅ Display found: {display}", Colors.GREEN)
    print()
    
    async with async_playwright() as p:
        try:
            print_colored("🚀 Launching Chrome browser...", Colors.BLUE)
            print_colored("   (This may take a few seconds)", Colors.YELLOW)
            print()
            
            # Launch browser with persistent context
            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,  # Must be visible for setup
                ignore_https_errors=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--ignore-certificate-errors',
                    '--disable-blink-features=AutomationControlled',  # Hide automation
                ],
                channel='chrome'  # Use system Chrome
            )
            
            print_colored("✅ Chrome browser opened!", Colors.GREEN)
            print()
            
            # Create new page
            page = await context.new_page()
            
            # Step 1: Install 1Password Extension
            print_step(1, "Install 1Password Extension")
            
            print_colored("📋 Instructions:", Colors.YELLOW)
            print("   1. In the Chrome window that just opened:")
            print("   2. Go to Chrome Web Store")
            print("   3. Search for '1Password'")
            print("   4. Click 'Add to Chrome' to install the extension")
            print("   5. Pin the extension to toolbar (optional but recommended)")
            print()
            
            # Navigate to Chrome Web Store
            print_colored("🌐 Opening Chrome Web Store...", Colors.BLUE)
            await page.goto('https://chrome.google.com/webstore/category/extensions', wait_until='networkidle')
            print()
            
            print_colored("⏸️  Press Enter after you've installed 1Password extension...", Colors.CYAN)
            input()
            
            # Step 2: Login to 1Password
            print_step(2, "Login to 1Password")
            
            print_colored("📋 Instructions:", Colors.YELLOW)
            print("   1. Click the 1Password extension icon in Chrome toolbar")
            print("   2. Login to your 1Password account")
            print("   3. Make sure it's unlocked and ready")
            print()
            
            print_colored("⏸️  Press Enter after you've logged into 1Password...", Colors.CYAN)
            input()
            
            # Step 3: Login to IBM with Passkey
            print_step(3, "Login to IBM with Passkey")
            
            print_colored("📋 Instructions:", Colors.YELLOW)
            print("   1. The browser will now navigate to IBM site")
            print("   2. Complete the passkey authentication using 1Password")
            print("   3. Wait for the page to fully load")
            print("   4. Verify you can see the Build Break Report page")
            print()
            
            print_colored("🌐 Navigating to IBM site...", Colors.BLUE)
            await page.goto('https://libh-proxy1.fyre.ibm.com/buildBreakReport/', wait_until='networkidle', timeout=60000)
            print()
            
            # Wait for user to complete login
            print_colored("⏳ Complete the login in the browser window...", Colors.YELLOW)
            print_colored("   (Use 1Password passkey authentication)", Colors.YELLOW)
            print()
            print_colored("⏸️  Press Enter after you've successfully logged in...", Colors.CYAN)
            input()
            
            # Verify cookies
            print()
            print_colored("🔍 Verifying cookies...", Colors.BLUE)
            cookies = await context.cookies()
            
            ltpa_found = False
            session_found = False
            
            for cookie in cookies:
                if cookie['name'] == 'LtpaToken2':
                    ltpa_found = True
                    print_colored(f"✅ Found LtpaToken2: {cookie['value'][:50]}...", Colors.GREEN)
                elif cookie['name'] == 'mod_auth_openidc_session':
                    session_found = True
                    print_colored(f"✅ Found mod_auth_openidc_session: {cookie['value']}", Colors.GREEN)
            
            print()
            
            if ltpa_found and session_found:
                print_colored("=" * 70, Colors.GREEN)
                print_colored("🎉 SUCCESS! Setup Complete!", Colors.GREEN)
                print_colored("=" * 70, Colors.GREEN)
                print()
                print_colored("✅ 1Password extension installed", Colors.GREEN)
                print_colored("✅ Logged into 1Password", Colors.GREEN)
                print_colored("✅ Logged into IBM with passkey", Colors.GREEN)
                print_colored("✅ Cookies saved to Playwright profile", Colors.GREEN)
                print()
                print_colored("📝 Next Steps:", Colors.YELLOW)
                print("   1. Close this browser window (or press Ctrl+C)")
                print("   2. Run: python3 playwright_cookie_extractor.py")
                print("   3. It should now work automatically without manual login!")
                print()
                print_colored("💡 The browser session is saved, so future runs will be automatic!", Colors.CYAN)
                print()
            else:
                print_colored("⚠️  Warning: Some cookies not found", Colors.YELLOW)
                if not ltpa_found:
                    print_colored("   ❌ LtpaToken2 not found", Colors.RED)
                if not session_found:
                    print_colored("   ❌ mod_auth_openidc_session not found", Colors.RED)
                print()
                print_colored("💡 This might be okay if you're still on the login page.", Colors.YELLOW)
                print_colored("   Try completing the login and running the setup again.", Colors.YELLOW)
                print()
            
            # Keep browser open for verification
            print_colored("🔍 Browser will stay open for verification...", Colors.BLUE)
            print_colored("   Check that you can access the IBM site", Colors.YELLOW)
            print_colored("   Press Ctrl+C when done to close the browser", Colors.YELLOW)
            print()
            
            # Wait indefinitely until user closes
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print()
                print_colored("👋 Closing browser...", Colors.BLUE)
                await context.close()
                print_colored("✅ Browser closed", Colors.GREEN)
                print()
                
        except Exception as e:
            print_colored(f"❌ Error: {e}", Colors.RED)
            import traceback
            print(traceback.format_exc())
            sys.exit(1)

async def main():
    """Main function"""
    await setup_playwright_with_1password()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        print_colored("👋 Setup interrupted by user", Colors.YELLOW)
        print()
        sys.exit(0)

# Made with Bob
