"""
Main Flask Application
Web dashboard for defect monitoring
"""

from flask import Flask, render_template, jsonify, request
import yaml
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from ibm_auth import IBMAuthenticator
from defect_checker import DefectChecker
from slack_notifier import SlackNotifier
from database import DefectDatabase
from scheduler import DefectScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/defect_monitor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
# Set template folder to parent directory's templates
template_dir = Path(__file__).parent.parent / 'templates'
app = Flask(__name__, template_folder=str(template_dir))

# Global variables
config = None
authenticator = None
defect_checker = None
slack_notifier = None
database = None
scheduler = None


def load_config():
    """Load configuration from YAML file"""
    global config
    
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info("✅ Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def initialize_services():
    """Initialize all services"""
    global authenticator, defect_checker, slack_notifier, database, scheduler
    
    try:
        # Load configuration
        load_config()
        
        # Set Flask secret key
        app.secret_key = config.get("dashboard", {}).get("secret_key", "change-me")
        
        # Initialize authenticator
        ibm_config = config.get("ibm", {})
        authenticator = IBMAuthenticator(
            username=ibm_config.get("username"),
            password=ibm_config.get("password"),
            session_timeout=ibm_config.get("session_timeout", 7200)
        )
        
        # Initialize defect checker
        defect_checker = DefectChecker(authenticator)
        
        # Initialize Slack notifier
        slack_config = config.get("slack", {})
        slack_notifier = SlackNotifier(
            webhook_url=slack_config.get("webhook_url"),
            default_channel=slack_config.get("channel", "#defect-notifications")
        )
        
        # Initialize database
        db_config = config.get("database", {})
        database = DefectDatabase(db_path=db_config.get("path", "data/defects.db"))
        
        # Initialize scheduler
        scheduler = DefectScheduler(config, defect_checker, slack_notifier, database)
        scheduler.start()
        
        logger.info("✅ All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        raise


# Routes

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Get system status"""
    try:
        session_info = authenticator.get_session_info()
        next_runs = scheduler.get_next_run_times()
        latest_snapshot = database.get_latest_snapshot()
        
        return jsonify({
            "status": "running",
            "session": session_info,
            "scheduled_jobs": next_runs,
            "latest_snapshot": latest_snapshot
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/weekly-data')
def api_weekly_data():
    """Get weekly data for dashboard"""
    try:
        days = request.args.get('days', 7, type=int)
        weekly_data = database.get_weekly_data(days=days)
        
        return jsonify(weekly_data)
    except Exception as e:
        logger.error(f"Error getting weekly data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/latest-snapshot')
def api_latest_snapshot():
    """Get latest snapshot"""
    try:
        snapshot = database.get_latest_snapshot()
        
        if snapshot:
            return jsonify(snapshot)
        else:
            return jsonify({"message": "No data available"}), 404
    except Exception as e:
        logger.error(f"Error getting latest snapshot: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/check-now', methods=['POST'])
def api_check_now():
    """Trigger manual defect check"""
    try:
        logger.info("Manual check triggered via API")
        scheduler.run_manual_check()
        
        return jsonify({"message": "Check started successfully"})
    except Exception as e:
        logger.error(f"Error triggering manual check: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/refresh-session', methods=['POST'])
def api_refresh_session():
    """Refresh IBM session"""
    try:
        logger.info("Session refresh triggered via API")
        
        if authenticator.refresh_session():
            return jsonify({"message": "Session refreshed successfully"})
        else:
            return jsonify({"error": "Session refresh failed"}), 500
    except Exception as e:
        logger.error(f"Error refreshing session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/all-components')
def api_all_components():
    """Get list of all available components"""
    try:
        all_components = config.get("all_components", [])
        monitored_components = [c.get("name") for c in config.get("monitored_components", [])]
        
        return jsonify({
            "all_components": all_components,
            "monitored_components": monitored_components,
            "total": len(all_components)
        })
    except Exception as e:
        logger.error(f"Error getting all components: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/all-components-data')
def api_all_components_data():
    """Get data for all components or specific components"""
    try:
        # Get component names from query parameter (comma-separated)
        components_param = request.args.get('components')
        days = request.args.get('days', 7, type=int)
        
        if components_param:
            component_names = [c.strip() for c in components_param.split(',')]
        else:
            component_names = None
        
        data = database.get_all_components_data(component_names, days)
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting all components data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/fetch-all-components', methods=['POST'])
def api_fetch_all_components():
    """Trigger background fetch for all 51 components"""
    try:
        logger.info("Background fetch for all components triggered via API")
        
        all_components = config.get("all_components", [])
        
        if not all_components:
            return jsonify({"error": "No components configured"}), 400
        
        # Run fetch in background
        summary = defect_checker.fetch_all_components_background(all_components, database)
        
        return jsonify({
            "message": "Background fetch completed",
            "summary": summary
        })
    except Exception as e:
        logger.error(f"Error fetching all components: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/fetch-components', methods=['POST'])
def api_fetch_components():
    """Fetch specific components on-demand"""
    try:
        data = request.get_json()
        component_names = data.get('components', [])
        
        if not component_names:
            return jsonify({"error": "No components specified"}), 400
        
        logger.info(f"Fetching {len(component_names)} components on-demand")
        
        results = {}
        for component in component_names:
            defects = defect_checker.fetch_defects_for_component(component)
            if defects is not None:
                parsed = defect_checker.parse_defects(defects, component)
                database.store_all_components_snapshot(component, parsed, is_monitored=False)
                results[component] = {
                    "total": parsed["total"],
                    "untriaged": parsed["untriaged"],
                    "test_bugs": parsed["test_bugs"],
                    "product_bugs": parsed["product_bugs"],
                    "infra_bugs": parsed["infra_bugs"]
                }
        
        return jsonify({
            "message": f"Fetched {len(results)} components",
            "results": results
        })
    except Exception as e:
        logger.error(f"Error fetching components: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": str(Path(__file__).stat().st_mtime)})


def main():
    """Main entry point"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 Starting Defect Monitor Server")
        logger.info("=" * 60)
        
        # Initialize services
        initialize_services()
        
        # Get dashboard config
        dashboard_config = config.get("dashboard", {})
        host = dashboard_config.get("host", "0.0.0.0")
        port = dashboard_config.get("port", 5000)
        
        logger.info(f"🌐 Dashboard will be available at http://{host}:{port}")
        logger.info("=" * 60)
        
        # Run Flask app
        app.run(
            host=host,
            port=port,
            debug=False
        )
        
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down gracefully...")
        if scheduler:
            scheduler.stop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()

# Made with Bob
