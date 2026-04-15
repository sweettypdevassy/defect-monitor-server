"""
Main Flask Application
Web dashboard for defect monitoring
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
import yaml
import json
import logging
from pathlib import Path
import sys
from datetime import datetime
import threading
from typing import Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from ibm_auth import IBMAuthenticator
from defect_checker import DefectChecker
from slack_notifier import SlackNotifier
from database import DefectDatabase
from scheduler import DefectScheduler
from insights_analyzer import InsightsAnalyzer

# Configure logging (only if not already configured)
if not logging.getLogger().handlers:
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
insights_analyzer = None

# Track ongoing refresh operations
refresh_status = {}
refresh_lock = threading.Lock()

# Initialize services when module is imported (for Gunicorn)
def init_app():
    """Initialize application - called at module level for Gunicorn"""
    global config, authenticator, defect_checker, slack_notifier, database, scheduler, insights_analyzer
    if database is None:  # Only initialize once
        logger.info("=" * 60)
        logger.info("🚀 Initializing Defect Monitor Server")
        logger.info("=" * 60)
        initialize_services()
        logger.info("✅ All services initialized")
        logger.info("=" * 60)


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
    global authenticator, defect_checker, slack_notifier, database, scheduler, insights_analyzer
    
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
            auth_method=auth_method,
            cookies=cookies
        )
        
        # Initialize database first (needed by defect_checker)
        db_config = config.get("database", {})
        database = DefectDatabase(db_path=db_config.get("path", "data/defects.db"))
        logger.info("✅ Database initialized")
        
        # Initialize defect checker with database
        defect_checker = DefectChecker(authenticator, database)
        
        # Initialize Slack notifier
        slack_config = config.get("slack", {})
        slack_notifier = SlackNotifier(
            webhook_url=slack_config.get("webhook_url"),
            default_channel=slack_config.get("channel", "#defect-notifications"),
            config=config
        )
        
        # Initialize scheduler
        scheduler = DefectScheduler(config, defect_checker, slack_notifier, database)
        scheduler.start()
        
        # Initialize insights analyzer with defect_checker for Jazz/RTC access
        insights_analyzer = InsightsAnalyzer(database, defect_checker)
        insights_analyzer.set_duplicate_detector(defect_checker.duplicate_detector)
        insights_analyzer.set_defect_checker(defect_checker)
        logger.info("✅ Insights analyzer initialized")
        
        logger.info("✅ All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        raise


# Routes

@app.after_request
def add_header(response):
    """Add headers to prevent caching during development"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def index():
    """Redirect to dashboard"""
    return redirect(url_for('dashboard'))


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
        
        response = jsonify(weekly_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error getting weekly data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/latest-snapshot')
def api_latest_snapshot():
    """Get latest snapshot"""
    try:
        snapshot = database.get_latest_snapshot()
        
        if snapshot:
            logger.info(f"API returning snapshot with date: {snapshot.get('date')}, components: {len(snapshot.get('components', {}))}")
            return jsonify(snapshot)
        else:
            return jsonify({"message": "No data available"}), 404
    except Exception as e:
        logger.error(f"Error getting latest snapshot: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/test-direct-query')
def api_test_direct_query():
    """Direct database query test - bypasses everything"""
    try:
        import sqlite3
        conn = sqlite3.connect('data/defects.db')
        cursor = conn.cursor()
        
        # Query all_components_snapshots directly
        cursor.execute("SELECT MAX(date) FROM all_components_snapshots")
        max_date = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT component, total, untriaged
            FROM all_components_snapshots
            WHERE date = ?
            LIMIT 10
        """, (max_date,))
        
        results = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "max_date": max_date,
            "sample_components": [
                {"component": r[0], "total": r[1], "untriaged": r[2]}
                for r in results
            ],
            "count": len(results)
        })
    except Exception as e:
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


# OLD ENDPOINT REMOVED - Now using async version below at line 529
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


def _do_refresh_components(component_names: List[str], refresh_id: str, include_soe: bool = False):
    """Background task to refresh components"""
    try:
        with refresh_lock:
            refresh_status[refresh_id] = {
                "status": "running",
                "progress": 0,
                "total": len(component_names),
                "results": [],
                "errors": [],
                "include_soe": include_soe,
                "started_at": datetime.now().isoformat()
            }
        
        results = []
        errors = []
        
        for idx, component_name in enumerate(component_names):
            try:
                # Fetch fresh data from IBM (SAME as scheduled fetch)
                defects = defect_checker.fetch_defects_for_component(component_name)
                
                if defects is None:
                    errors.append({"component": component_name, "error": "Failed to fetch defects"})
                    with refresh_lock:
                        refresh_status[refresh_id]["errors"] = errors
                        refresh_status[refresh_id]["progress"] = idx + 1
                    continue
                
                # Add component field to each defect for caching
                for defect in defects:
                    defect['component'] = component_name
                
                # Use LIGHTWEIGHT parsing for manual refresh (NO ML, NO duplicate detection)
                # This makes refresh FAST (5-10 seconds instead of 1+ minute)
                result = defect_checker.parse_defects_simple(defects, component_name)
                
                # Store in database for dashboard display
                database.store_all_components_snapshot(component_name, result, is_monitored=False)
                database.store_daily_snapshot({"components": {component_name: result}})
                
                results.append({
                    "component": component_name,
                    "total": result.get('total', 0),
                    "untriaged": result.get('untriaged', 0),
                    "test_bugs": result.get('test_bugs', 0),
                    "product_bugs": result.get('product_bugs', 0),
                    "infra_bugs": result.get('infra_bugs', 0)
                })
                
                logger.info(f"✅ {component_name}: Total={result['total']}, Untriaged={result['untriaged']}")
                
                # Update progress
                with refresh_lock:
                    refresh_status[refresh_id]["results"] = results
                    refresh_status[refresh_id]["progress"] = idx + 1
                
            except Exception as e:
                logger.error(f"❌ Error refreshing {component_name}: {e}")
                errors.append({"component": component_name, "error": str(e)})
                with refresh_lock:
                    refresh_status[refresh_id]["errors"] = errors
                    refresh_status[refresh_id]["progress"] = idx + 1
        
        logger.info(f"✅ Batch refresh completed: {len(results)} successful, {len(errors)} failed")
        
        # Optionally refresh SOE Triage if requested
        soe_result = None
        if include_soe:
            try:
                logger.info("🔄 Refreshing SOE Triage: Overdue Defects...")
                
                # Authenticate with Jazz/RTC (same as scheduled checks)
                if not authenticator.authenticate_jazz_rtc():
                    logger.error("❌ Jazz/RTC authentication failed, skipping SOE Triage refresh")
                else:
                    soe_defects = defect_checker.fetch_soe_triage_defects()
                    
                    if soe_defects is not None:
                        soe_result = {
                            "total": len(soe_defects),
                            "defects": soe_defects
                        }
                        
                        # Store SOE Triage data in database
                        date = datetime.now().strftime("%Y-%m-%d")
                        created_at = datetime.now().isoformat()
                        
                        import sqlite3
                        conn = sqlite3.connect(database.db_path)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO soe_snapshots
                            (date, total, data, created_at)
                            VALUES (?, ?, ?, ?)
                        """, (
                            date,
                            soe_result["total"],
                            json.dumps(soe_result),
                            created_at
                        ))
                        conn.commit()
                        conn.close()
                        
                        logger.info(f"✅ SOE Triage: {len(soe_defects)} overdue defects refreshed")
                    else:
                        logger.warning("⚠️ Failed to fetch SOE Triage defects")
                        
            except Exception as e:
                logger.error(f"❌ Error refreshing SOE Triage: {e}")
        else:
            logger.info("ℹ️  Skipping SOE Triage refresh (not requested)")
        
        # Mark as completed
        with refresh_lock:
            refresh_status[refresh_id]["status"] = "completed"
            refresh_status[refresh_id]["completed_at"] = datetime.now().isoformat()
            refresh_status[refresh_id]["results"] = results
            refresh_status[refresh_id]["errors"] = errors
            if soe_result:
                refresh_status[refresh_id]["soe_result"] = soe_result
            
    except Exception as e:
        logger.error(f"❌ Background refresh failed: {e}")
        with refresh_lock:
            refresh_status[refresh_id]["status"] = "failed"
            refresh_status[refresh_id]["error"] = str(e)
            refresh_status[refresh_id]["completed_at"] = datetime.now().isoformat()


@app.route('/api/refresh-components', methods=['POST'])
def api_refresh_components():
    """
    Trigger background refresh for multiple components
    Returns immediately with a refresh_id to track progress
    """
    try:
        data = request.get_json()
        component_names = data.get('components', [])
        include_soe = data.get('include_soe', False)  # Optional SOE refresh
        
        if not component_names:
            return jsonify({"error": "No components specified"}), 400
        
        # Generate unique refresh ID
        refresh_id = f"refresh_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        soe_msg = " + SOE Triage" if include_soe else ""
        logger.info(f"🔄 Batch refresh triggered for {len(component_names)} components{soe_msg} (ID: {refresh_id})")
        
        # Start background thread
        thread = threading.Thread(
            target=_do_refresh_components,
            args=(component_names, refresh_id, include_soe),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "message": "Refresh started in background",
            "refresh_id": refresh_id,
            "components": component_names,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error starting refresh: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/refresh-status/<refresh_id>', methods=['GET'])
def api_refresh_status(refresh_id):
    """Get status of a background refresh operation"""
    with refresh_lock:
        if refresh_id not in refresh_status:
            return jsonify({"error": "Refresh ID not found"}), 404
        
        status = refresh_status[refresh_id].copy()
    
    return jsonify(status)


@app.route('/api/refresh-status', methods=['GET'])
def api_all_refresh_status():
    """Get status of all refresh operations"""
    with refresh_lock:
        all_status = refresh_status.copy()
    
    return jsonify(all_status)


# Keep old endpoint for backward compatibility but make it async too
@app.route('/api/refresh-component/<component_name>', methods=['POST'])
def api_refresh_component(component_name):
    """Refresh a single component (async)"""
    try:
        # Use the batch refresh with single component
        refresh_id = f"refresh_{component_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"🔄 Single component refresh triggered: {component_name} (ID: {refresh_id})")
        
        thread = threading.Thread(
            target=_do_refresh_components,
            args=([component_name], refresh_id),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "message": f"Refresh started for {component_name}",
            "refresh_id": refresh_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error refreshing {component_name}: {e}")
        return jsonify({"error": str(e)}), 500


# Old synchronous endpoint - DEPRECATED but kept for compatibility
@app.route('/api/refresh-components-sync', methods=['POST'])
def api_refresh_components_sync():
    """
    DEPRECATED: Synchronous refresh (blocks until complete)
    Use /api/refresh-components instead for async operation
    """
    try:
        data = request.get_json()
        component_names = data.get('components', [])
        
        if not component_names:
            return jsonify({"error": "No components specified"}), 400
        
        logger.info(f"🔄 SYNC Batch refresh triggered for {len(component_names)} components")
        
        results = []
        errors = []
        
        for component_name in component_names:
            try:
                # Fetch fresh data from IBM
                defects = defect_checker.fetch_defects_for_component(component_name)
                
                if defects is None:
                    errors.append({"component": component_name, "error": "Failed to fetch defects"})
                    continue
                
                # Process defects
                result = defect_checker.parse_defects(defects, component_name, collect_triaged=False)
                
                # Update database
                database.store_component_snapshot_single(component_name, result)
                
                results.append({
                    "component": component_name,
                    "total": result.get('total', 0),
                    "untriaged": result.get('untriaged', 0),
                    "test_bugs": result.get('test_bugs', 0),
                    "product_bugs": result.get('product_bugs', 0),
                    "infra_bugs": result.get('infra_bugs', 0)
                })
                
                logger.info(f"✅ {component_name}: Total={result['total']}, Untriaged={result['untriaged']}")
                
            except Exception as e:
                logger.error(f"❌ Error refreshing {component_name}: {e}")
                errors.append({"component": component_name, "error": str(e)})
        
        # Also refresh SOE Triage: Overdue Defects
        soe_result = None
        try:
            logger.info("🔄 Refreshing SOE Triage: Overdue Defects...")
            
            # Authenticate with Jazz/RTC (same as scheduled checks)
            if not authenticator.authenticate_jazz_rtc():
                logger.error("❌ Jazz/RTC authentication failed, skipping SOE Triage refresh")
                raise Exception("Jazz/RTC authentication failed")
            
            soe_defects = defect_checker.fetch_soe_triage_defects()
            
            if soe_defects is not None:
                soe_result = {
                    "total": len(soe_defects),
                    "defects": soe_defects
                }
                
                # Store SOE Triage data in database
                date = datetime.now().strftime("%Y-%m-%d")
                created_at = datetime.now().isoformat()
                
                import sqlite3
                conn = sqlite3.connect(database.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO soe_snapshots
                    (date, total, data, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    date,
                    soe_result["total"],
                    json.dumps(soe_result),
                    created_at
                ))
                conn.commit()
                conn.close()
                
                logger.info(f"✅ SOE Triage: {len(soe_defects)} overdue defects refreshed")
            else:
                logger.warning("⚠️ Failed to fetch SOE Triage defects")
                
        except Exception as e:
            logger.error(f"❌ Error refreshing SOE Triage: {e}")
        
        logger.info(f"✅ Batch refresh completed: {len(results)} successful, {len(errors)} failed")
        
        response_data = {
            "message": f"Refreshed {len(results)} components",
            "results": results,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add SOE Triage info to response
        if soe_result:
            response_data["soe_triage"] = {
                "total": soe_result["total"],
                "refreshed": True
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ Error in batch refresh: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/insights/<component_name>')
def api_component_insights(component_name):
    """Get insights and recommendations for a specific component"""
    try:
        # Get the component's defects from the latest snapshot
        snapshot = database.get_latest_snapshot()
        if not snapshot or component_name not in snapshot.get('components', {}):
            return jsonify({"error": "Component not found"}), 404
        
        component_data = snapshot['components'][component_name]
        
        # Get defects with descriptions from cache
        defects = []
        
        # Try to get cached descriptions for this component
        cached_defects = database.get_all_cached_descriptions_for_component(component_name)
        
        if cached_defects:
            # Merge current number_builds from snapshot with cached defect data
            # This ensures we have up-to-date build counts for rare defect detection
            # all_defects is now directly in component_data (added by get_latest_snapshot)
            current_defects_map = {}
            all_defects_list = component_data.get('all_defects', [])
            
            logger.info(f"📊 Found {len(all_defects_list)} defects in snapshot for number_builds update")
            for defect in all_defects_list:
                current_defects_map[str(defect['id'])] = defect.get('number_builds', 0)
            
            # Update number_builds in cached defects with current values
            updated_count = 0
            for defect in cached_defects:
                defect_id = str(defect['id'])
                if defect_id in current_defects_map:
                    defect['number_builds'] = current_defects_map[defect_id]
                    updated_count += 1
                    logger.debug(f"Updated number_builds for {defect_id}: {defect['number_builds']}")
            
            defects = cached_defects
            logger.info(f"✅ Using {len(defects)} cached defects for insights ({updated_count} with updated build counts)")
        else:
            # Try to get from historical data
            history = database.get_component_history(component_name, days=30)
            if history:
                for hist in history:
                    if hist.get('defects'):
                        defects = hist['defects']
                        break
        
        # If still no defects, return empty insights
        if not defects:
            logger.warning(f"No defects found for {component_name} - returning empty insights")
            return jsonify({
                'component': component_name,
                'duplicates': [],
                'rare_defects': [],
                'recurring_patterns': [],
                'recommendations': [],
                'summary': {
                    'total_defects': component_data.get('total', 0),
                    'untriaged': component_data.get('untriaged', 0),
                    'test_bugs': component_data.get('test_bugs', 0),
                    'product_bugs': component_data.get('product_bugs', 0),
                    'infra_bugs': component_data.get('infra_bugs', 0)
                }
            })
        
        # Analyze the component with real defect data
        insights = insights_analyzer.analyze_component(component_name, defects)
        
        # Add component summary
        insights['component'] = component_name
        insights['summary'] = {
            'total_defects': component_data.get('total', 0),
            'untriaged': component_data.get('untriaged', 0),
            'test_bugs': component_data.get('test_bugs', 0),
            'product_bugs': component_data.get('product_bugs', 0),
            'infra_bugs': component_data.get('infra_bugs', 0)
        }
        
        return jsonify(insights)
        
    except Exception as e:
        logger.error(f"Error getting insights for {component_name}: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/api/dashboard/data')
def api_dashboard_data():
    """Get dashboard data in the format expected by the new dashboard"""
    try:
        # Get latest snapshot
        logger.info(f"DEBUG: Calling database.get_latest_snapshot()")
        snapshot = database.get_latest_snapshot()
        logger.info(f"DEBUG: Snapshot returned: date={snapshot.get('date') if snapshot else None}, components={len(snapshot.get('components', {})) if snapshot else 0}")
        
        if not snapshot or not snapshot.get("components"):
            response = jsonify({"error": "No data available"})
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 404
        
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
        
        # Add cache-control headers to prevent browser caching
        response = jsonify(dashboard_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
        
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
        raw_defects = soe_defects.get("defects", [])
        
        # Normalize field names to camelCase for frontend
        normalized_defects = []
        for defect in raw_defects:
            normalized_defects.append({
                "id": defect.get("id"),
                "summary": defect.get("summary", ""),
                "functionalArea": defect.get("functionalArea") or defect.get("functional_area", ""),
                "filedAgainst": defect.get("filedAgainst") or defect.get("filed_against", ""),
                "creationDate": defect.get("creationDate") or defect.get("creation_date", ""),
                "ownedBy": defect.get("ownedBy") or defect.get("owned_by", "Unassigned")
            })
        
        return jsonify({
            "defects": normalized_defects,
            "last_fetch": soe_defects.get("last_fetch"),
            "count": len(normalized_defects)
        })
    except Exception as e:
        logger.error(f"Error getting SOE defects: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/untriaged-defects')
def api_untriaged_defects():
    """Get all untriaged defects with full details including duplicates and suggested tags"""
    try:
        # Get component filter from query parameter
        components_param = request.args.get('components')
        component_names = None
        if components_param:
            component_names = [c.strip() for c in components_param.split(',')]
        
        # Get all untriaged defects from database
        untriaged_defects = database.get_all_untriaged_defects(component_names)
        
        # Group by component for better organization
        defects_by_component = {}
        for defect in untriaged_defects:
            component = defect.get('component', 'Unknown')
            if component not in defects_by_component:
                defects_by_component[component] = []
            defects_by_component[component].append(defect)
        
        return jsonify({
            "defects": untriaged_defects,
            "defects_by_component": defects_by_component,
            "total_count": len(untriaged_defects),
            "component_count": len(defects_by_component)
        })
    except Exception as e:
        logger.error(f"Error getting untriaged defects: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/triaged-defects')
def api_triaged_defects():
    """Get all triaged defects categorized by tag type (product, infra, test)"""
    try:
        # Get component filter from query parameter
        components_param = request.args.get('components')
        component_names = None
        if components_param:
            component_names = [c.strip() for c in components_param.split(',')]
        
        # Get triaged defects categorized by type from database
        triaged_data = database.get_all_triaged_defects_by_category(component_names)
        
        # Add cache-control headers to prevent browser caching
        response = jsonify(triaged_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error getting triaged defects: {e}")
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
    """Get dashboard data for selected components from all_components_snapshots table"""
    try:
        data = request.get_json()
        selected_components = data.get('components', [])
        
        if not selected_components:
            return jsonify({"error": "No components selected"}), 400
        
        # Get data from all_components_snapshots table (data from Check Now)
        days = 7
        components_data = database.get_all_components_data(selected_components, days)
        
        if not components_data or not components_data.get("components"):
            return jsonify({"error": "No data available for selected components"}), 404
        
        # Get latest data for each component to calculate summary
        latest_data = {}
        for comp_name, comp_history in components_data["components"].items():
            if comp_history:
                # Get the most recent entry
                latest_data[comp_name] = comp_history[-1]
        
        # Calculate summary statistics
        total_defects = sum(comp['total'] for comp in latest_data.values())
        untriaged_defects = sum(comp['untriaged'] for comp in latest_data.values())
        test_bugs = sum(comp['test_bugs'] for comp in latest_data.values())
        product_bugs = sum(comp['product_bugs'] for comp in latest_data.values())
        infra_bugs = sum(comp['infra_bugs'] for comp in latest_data.values())
        
        # Build daily trend data
        dates = components_data.get("dates", [])
        
        # Format dates as labels (e.g., "Mon", "Tue", etc.)
        from datetime import datetime
        labels = []
        for date_str in dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                labels.append(date_obj.strftime("%a"))  # Mon, Tue, etc.
            except:
                labels.append(date_str)
        
        daily_trend = {
            "labels": labels,
            "total": [],
            "untriaged": []
        }
        
        for date in dates:
            date_total = 0
            date_untriaged = 0
            for comp_name, comp_history in components_data["components"].items():
                for entry in comp_history:
                    if entry["date"] == date:
                        date_total += entry["total"]
                        date_untriaged += entry["untriaged"]
                        break
            daily_trend["total"].append(date_total)
            daily_trend["untriaged"].append(date_untriaged)
        
        # Get SOE defects filtered by selected components
        soe_data = database.get_soe_defects()
        all_soe_defects = soe_data.get("defects", [])
        filtered_soe = []
        for defect in all_soe_defects:
            functional_area = defect.get("functionalArea", "") or defect.get("functional_area", "")
            filed_against = defect.get("filedAgainst", "") or defect.get("filed_against", "")
            
            # Check if defect matches any selected component
            for comp in selected_components:
                if (comp.lower() in functional_area.lower() or
                    comp.lower() in filed_against.lower()):
                    filtered_soe.append({
                        "id": defect.get("id"),
                        "summary": defect.get("summary", ""),
                        "functionalArea": functional_area,
                        "filedAgainst": filed_against,
                        "creationDate": defect.get("creationDate", "") or defect.get("creation_date", "")
                    })
                    break
        
        # Build dashboard data
        logger.info(f"Latest data keys: {list(latest_data.keys())}")
        logger.info(f"Sample component data: {list(latest_data.values())[0] if latest_data else 'No data'}")
        
        dashboard_data = {
            "summary": {
                "totalDefects": total_defects,
                "untriaged": untriaged_defects,
                "testBugs": test_bugs,
                "productBugs": product_bugs,
                "infraBugs": infra_bugs,
                "triageRate": round((total_defects - untriaged_defects) / total_defects * 100, 1) if total_defects > 0 else 0
            },
            "dailyTrend": daily_trend,
            "componentBreakdown": {
                "labels": list(latest_data.keys()),
                "total": [comp.get('total', 0) for comp in latest_data.values()],
                "untriaged": [comp.get('untriaged', 0) for comp in latest_data.values()],
                "testBugs": [comp.get('test_bugs', 0) for comp in latest_data.values()],
                "productBugs": [comp.get('product_bugs', 0) for comp in latest_data.values()],
                "infraBugs": [comp.get('infra_bugs', 0) for comp in latest_data.values()]
            },
            "weekComparison": {
                "thisWeek": {
                    "total": total_defects,
                    "untriaged": untriaged_defects
                },
                "lastWeek": {
                    "total": 0,
                    "untriaged": 0
                }
            },
            "soeTriageDefects": filtered_soe
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
    """Trigger background fetch for components (respects test_components config)"""
    try:
        logger.info("Background fetch for components triggered via API")
        
        # Check if test_components is configured (for testing)
        test_components = config.get("schedule", {}).get("test_components", [])
        
        if test_components:
            # Use test components for testing
            components_to_fetch = test_components
            logger.info(f"📝 Using test_components: {len(components_to_fetch)} components")
            logger.info(f"   Components: {', '.join(components_to_fetch)}")
        else:
            # Use all components for production
            components_to_fetch = config.get("all_components", [])
            logger.info(f"📋 Using all_components: {len(components_to_fetch)} components")
        
        if not components_to_fetch:
            return jsonify({"error": "No components configured"}), 400
        
        # Run fetch in background
        summary = defect_checker.fetch_all_components_background(components_to_fetch, database)
        
        return jsonify({
            "message": "Background fetch completed",
            "summary": summary
        })
    except Exception as e:
        logger.error(f"Error fetching components: {e}")
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
                logger.info(f"📝 About to cache {len(defects)} defects for {component}")
                # Add component field to each defect for caching
                for defect in defects:
                    defect['component'] = component
                
                # Cache defect descriptions with creation_date and number_builds
                logger.info(f"📝 Calling database.cache_defect_descriptions with {len(defects)} defects")
                database.cache_defect_descriptions(defects)
                logger.info(f"📝 Finished caching defects for {component}")
                    
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




@app.route('/api/admin/reload-modules')
def admin_reload_modules():
    """Force reload of Python modules - EMERGENCY USE ONLY"""
    try:
        import importlib
        import sys
        
        # Reload database module
        if 'database' in sys.modules:
            importlib.reload(sys.modules['database'])
            logger.info("🔄 Reloaded database module")
        
        # Re-initialize database with fresh module
        global database
        from database import DefectDatabase
        db_config = config.get("database", {})
        database = DefectDatabase(db_path=db_config.get("path", "data/defects.db"))
        logger.info("🔄 Re-initialized database instance")
        
        return jsonify({"status": "success", "message": "Modules reloaded"})
    except Exception as e:
        logger.error(f"Error reloading modules: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/latest-snapshot-fixed')
def api_latest_snapshot_fixed():
    """Workaround endpoint - reads from generated JSON file"""
    try:
        import json
        with open('data/latest_snapshot.json', 'r') as f:
            snapshot = json.load(f)
        
        response = jsonify(snapshot)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except FileNotFoundError:
        return jsonify({"error": "Snapshot file not found. Run generate_dashboard_data.py first"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Auto-initialize when imported by Gunicorn (must be at end after all functions defined)
init_app()

if __name__ == '__main__':
    main()

# Made with Bob
