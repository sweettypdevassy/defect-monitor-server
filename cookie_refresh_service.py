#!/usr/bin/env python3
"""
Cookie Refresh Service
Runs on host, provides HTTP endpoint for Docker to trigger cookie refresh
"""

from flask import Flask, jsonify
import subprocess
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REFRESH_SCRIPT = os.path.join(SCRIPT_DIR, "refresh_cookies_auto.sh")

@app.route('/refresh-cookies', methods=['POST'])
def refresh_cookies():
    """Endpoint to trigger cookie refresh"""
    try:
        logger.info("🔄 Cookie refresh requested")
        
        # Run the refresh script
        result = subprocess.run(
            [REFRESH_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=SCRIPT_DIR
        )
        
        if result.returncode == 0:
            logger.info("✅ Cookies refreshed successfully")
            return jsonify({
                "success": True,
                "message": "Cookies refreshed successfully"
            }), 200
        else:
            logger.error(f"❌ Cookie refresh failed: {result.stderr}")
            return jsonify({
                "success": False,
                "message": f"Refresh failed: {result.stderr}"
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Cookie refresh timed out")
        return jsonify({
            "success": False,
            "message": "Refresh timed out"
        }), 500
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    logger.info("🚀 Starting Cookie Refresh Service on port 5002")
    logger.info(f"📁 Script directory: {SCRIPT_DIR}")
    logger.info(f"📝 Refresh script: {REFRESH_SCRIPT}")
    app.run(host='0.0.0.0', port=5002)

# Made with Bob
