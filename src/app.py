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
# Set template folder and static folder to parent directory
template_dir = Path(__file__).parent.parent / 'templates'
static_dir = Path(__file__).parent.parent / 'static'
app = Flask(__name__,
            template_folder=str(template_dir),
            static_folder=str(static_dir),
            static_url_path='/static')

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
        auth_method = ibm_config.get("auth_method", "password")
        cookies = ibm_config.get("cookies", {})
        
        authenticator = IBMAuthenticator(
            username=ibm_config.get("username", ""),
            password=ibm_config.get("password", ""),
            session_timeout=ibm_config.get("session_timeout", 7200),
            auth_method=auth_method,
            cookies=cookies
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
    """Dashboard page matching Chrome extension design"""
    return render_template('dashboard.html')

@app.route('/dashboard-old')
def dashboard_old():
    """Old dashboard page"""
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


@app.route('/api/dashboard/data')
def api_dashboard_data():
    """Get dashboard data in the format expected by the new dashboard"""
    try:
        # Get latest snapshot
        snapshot = database.get_latest_snapshot()
        
        if not snapshot or not snapshot.get("components"):
            return jsonify({"error": "No data available"}), 404
        
        # Get weekly data for trend
        weekly_data = database.get_weekly_data(days=7)
        
        # Calculate totals from components
        components = snapshot.get("components", {})
        total_defects = sum(c.get("total", 0) for c in components.values())
        total_untriaged = sum(c.get("untriaged", 0) for c in components.values())
        total_test_bugs = sum(c.get("test_bugs", 0) for c in components.values())
        total_product_bugs = sum(c.get("product_bugs", 0) for c in components.values())
        total_infra_bugs = sum(c.get("infra_bugs", 0) for c in components.values())
        
        # Build component breakdown arrays
        component_names = list(components.keys())
        component_totals = [components[c].get("total", 0) for c in component_names]
        component_untriaged = [components[c].get("untriaged", 0) for c in component_names]
        component_test_bugs = [components[c].get("test_bugs", 0) for c in component_names]
        component_product_bugs = [components[c].get("product_bugs", 0) for c in component_names]
        component_infra_bugs = [components[c].get("infra_bugs", 0) for c in component_names]
        
        # Build daily trend from weekly data
        dates = weekly_data.get("dates", [])
        daily_totals = []
        daily_untriaged = []
        
        for date in dates:
            date_total = 0
            date_untriaged = 0
            for comp_data in weekly_data.get("components", {}).values():
                for entry in comp_data:
                    if entry.get("date") == date:
                        date_total += entry.get("total", 0)
                        date_untriaged += entry.get("untriaged", 0)
            daily_totals.append(date_total)
            daily_untriaged.append(date_untriaged)
        
        # Format dates as day names
        from datetime import datetime
        labels = []
        for date_str in dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                labels.append(date_obj.strftime("%a"))  # Mon, Tue, etc.
            except:
                labels.append(date_str)
        
        # Build dashboard data structure
        dashboard_data = {
            "summary": {
                "totalDefects": total_defects,
                "untriaged": total_untriaged,
                "testBugs": total_test_bugs,
                "productBugs": total_product_bugs,
                "infraBugs": total_infra_bugs,
                "trendPercentage": 0  # Calculate if we have historical data
            },
            "dailyTrend": {
                "labels": labels,
                "total": daily_totals,
                "untriaged": daily_untriaged
            },
            "componentBreakdown": {
                "labels": component_names,
                "total": component_totals,
                "untriaged": component_untriaged,
                "testBugs": component_test_bugs,
                "productBugs": component_product_bugs,
                "infraBugs": component_infra_bugs
            },
            "weekComparison": {
                "lastWeek": {"total": 0, "untriaged": 0},
                "thisWeek": {
                    "total": total_defects,
                    "untriaged": total_untriaged
                },
                "lastWeekDate": None
            },
            "weekStart": dates[0] if dates else None,
            "weekEnd": dates[-1] if dates else None,
            "generatedAt": datetime.now().isoformat()
        }
        
        return jsonify(dashboard_data)
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/soe-defects')
def api_soe_defects():
    """Get SOE Triage defects"""
    try:
        # Get SOE defects from database
        soe_defects = database.get_soe_defects()
        
        return jsonify({
            "defects": soe_defects.get("defects", []),
            "last_fetch": soe_defects.get("last_fetch"),
            "count": len(soe_defects.get("defects", []))
        })
    except Exception as e:
        logger.error(f"Error getting SOE defects: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/components')
def api_components():
    """Get list of all components"""
    try:
        all_components = config.get("all_components", [])
        monitored_components = [c.get("name") for c in config.get("monitored_components", [])]
        
        return jsonify({
            "all_components": all_components,
            "monitored_components": monitored_components
        })
    except Exception as e:
        logger.error(f"Error getting components: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/explorer/data', methods=['POST'])
def api_explorer_data():
    """Get dashboard data for selected components from defect_snapshots table"""
    try:
        data = request.get_json()
        selected_components = data.get('components', [])
        
        if not selected_components:
            return jsonify({"error": "No components selected"}), 400
        
        # Get data from defect_snapshots table (same as main dashboard)
        days = 7
        weekly_data = database.get_weekly_data(days=days)
        
        # Filter data for selected components only
        if weekly_data and 'component_breakdown' in weekly_data:
            # Filter component breakdown
            filtered_breakdown = {}
            for comp in selected_components:
                if comp in weekly_data['component_breakdown']:
                    filtered_breakdown[comp] = weekly_data['component_breakdown'][comp]
            
            # Recalculate summary for selected components only
            total_defects = sum(comp['total'] for comp in filtered_breakdown.values())
            untriaged_defects = sum(comp['untriaged'] for comp in filtered_breakdown.values())
            test_bugs = sum(comp['test_bugs'] for comp in filtered_breakdown.values())
            product_bugs = sum(comp['product_bugs'] for comp in filtered_breakdown.values())
            infra_bugs = sum(comp['infra_bugs'] for comp in filtered_breakdown.values())
            
            dashboard_data = {
                "summary": {
                    "total": total_defects,
                    "untriaged": untriaged_defects,
                    "test_bugs": test_bugs,
                    "product_bugs": product_bugs,
                    "infra_bugs": infra_bugs,
                    "triage_rate": round((total_defects - untriaged_defects) / total_defects * 100, 1) if total_defects > 0 else 0
                },
                "dailyTrend": weekly_data.get("daily_trend", {}),
                "componentBreakdown": {
                    "labels": list(filtered_breakdown.keys()),
                    "total": [comp['total'] for comp in filtered_breakdown.values()],
                    "untriaged": [comp['untriaged'] for comp in filtered_breakdown.values()]
                },
                "weekComparison": weekly_data.get("week_comparison", {}),
                "soeTriageDefects": weekly_data.get("soe_triage_defects", [])
            }
        else:
            dashboard_data = {
                "summary": {},
                "dailyTrend": {},
                "componentBreakdown": {},
                "weekComparison": {},
                "soeTriageDefects": []
            }
        
        return jsonify(dashboard_data)
    except Exception as e:
        logger.error(f"Error getting explorer data: {e}")
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
