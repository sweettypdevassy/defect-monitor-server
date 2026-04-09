"""
Scheduler Module
Handles automated scheduling of defect checks and dashboard generation
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from cache_cleaner import clean_chrome_cache

logger = logging.getLogger(__name__)


class DefectScheduler:
    """Manages scheduled tasks for defect monitoring"""
    
    def __init__(self, config: dict, defect_checker, slack_notifier, database):
        self.config = config
        self.defect_checker = defect_checker
        self.slack_notifier = slack_notifier
        self.database = database
        self.scheduler = BackgroundScheduler()
        self.timezone = pytz.timezone(config.get("schedule", {}).get("timezone", "Asia/Kolkata"))
    
    def start(self):
        """Start the scheduler"""
        try:
            # Check ML model status
            if not self.defect_checker.suggester_trained:
                logger.warning("⚠️  ML model not trained. Run: docker-compose exec defect-monitor python3 retrain_model.sh")
            
            # Schedule weekly ML model retraining (Saturday 10am IST)
            ml_config = self.config.get("ml_training", {})
            ml_retrain_time = ml_config.get("retrain_time", "10:00")
            ml_retrain_day = ml_config.get("retrain_day", "saturday")
            hour, minute = map(int, ml_retrain_time.split(":"))
            
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            retrain_day_num = day_map.get(ml_retrain_day.lower(), 5)
            
            self.scheduler.add_job(
                self.retrain_ml_model,
                CronTrigger(day_of_week=retrain_day_num, hour=hour, minute=minute, timezone=self.timezone),
                id="ml_retrain",
                name="Weekly ML Model Retraining",
                replace_existing=True
            )
            
            logger.info(f"✅ Scheduled ML retraining on {ml_retrain_day} at {ml_retrain_time} {self.timezone}")
            
            # Schedule daily cache cleanup (2am IST)
            self.scheduler.add_job(
                self.clean_cache,
                CronTrigger(hour=2, minute=0, timezone=self.timezone),
                id="cache_cleanup",
                name="Daily Chrome Cache Cleanup",
                replace_existing=True
            )
            logger.info(f"✅ Scheduled daily cache cleanup at 02:00 {self.timezone}")
            
            # Schedule team-based defect checks
            teams = self.config.get("teams", [])
            if teams:
                logger.info(f"📋 Scheduling checks for {len(teams)} teams...")
                for team in teams:
                    team_name = team.get("name", "Unknown")
                    check_time = team.get("check_time", "10:00")
                    skip_weekends = team.get("skip_weekends", True)
                    
                    hour, minute = map(int, check_time.split(":"))
                    
                    # Schedule with or without weekend skip
                    if skip_weekends:
                        # Monday to Friday only (0-4)
                        self.scheduler.add_job(
                            lambda t=team: self.run_team_check(t),
                            CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute, timezone=self.timezone),
                            id=f"team_check_{team_name}",
                            name=f"Team Check: {team_name}",
                            replace_existing=True
                        )
                        logger.info(f"✅ Scheduled {team_name} check at {check_time} (Mon-Fri) {self.timezone}")
                    else:
                        # Every day
                        self.scheduler.add_job(
                            lambda t=team: self.run_team_check(t),
                            CronTrigger(hour=hour, minute=minute, timezone=self.timezone),
                            id=f"team_check_{team_name}",
                            name=f"Team Check: {team_name}",
                            replace_existing=True
                        )
                        logger.info(f"✅ Scheduled {team_name} check at {check_time} (daily) {self.timezone}")
                    
                    # Schedule team-specific weekly dashboard if configured
                    weekly_day = team.get("weekly_dashboard_day")
                    weekly_time = team.get("weekly_dashboard_time")
                    
                    if weekly_day and weekly_time:
                        hour, minute = map(int, weekly_time.split(":"))
                        day_of_week = day_map.get(weekly_day.lower(), 0)
                        
                        self.scheduler.add_job(
                            lambda t=team: self.run_team_weekly_dashboard(t),
                            CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=self.timezone),
                            id=f"team_weekly_dashboard_{team_name}",
                            name=f"Weekly Dashboard: {team_name}",
                            replace_existing=True
                        )
                        logger.info(f"✅ Scheduled {team_name} weekly dashboard on {weekly_day} at {weekly_time} {self.timezone}")
            else:
                # Fallback to old daily check if no teams configured
                daily_time = self.config.get("schedule", {}).get("daily_check_time", "10:00")
                skip_weekends = self.config.get("schedule", {}).get("skip_weekends", True)
                hour, minute = map(int, daily_time.split(":"))
                
                if skip_weekends:
                    self.scheduler.add_job(
                        self.run_daily_check,
                        CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute, timezone=self.timezone),
                        id="daily_check",
                        name="Daily Defect Check",
                        replace_existing=True
                    )
                    logger.info(f"✅ Scheduled daily check at {daily_time} (Mon-Fri) {self.timezone}")
                else:
                    self.scheduler.add_job(
                        self.run_daily_check,
                        CronTrigger(hour=hour, minute=minute, timezone=self.timezone),
                        id="daily_check",
                        name="Daily Defect Check",
                        replace_existing=True
                    )
                    logger.info(f"✅ Scheduled daily check at {daily_time} (daily) {self.timezone}")
            
            # Schedule all components fetch (background, no notifications)
            if self.config.get("features", {}).get("all_components_tracking", True):
                all_comp_time = self.config.get("schedule", {}).get("all_components_fetch_time", "09:00")
                hour, minute = map(int, all_comp_time.split(":"))
                
                self.scheduler.add_job(
                    self.run_all_components_fetch,
                    CronTrigger(hour=hour, minute=minute, timezone=self.timezone),
                    id="all_components_fetch",
                    name="All Components Background Fetch",
                    replace_existing=True
                )
                
                logger.info(f"✅ Scheduled all components fetch at {all_comp_time} {self.timezone}")
            
            # Schedule weekly dashboard
            dashboard_day = self.config.get("schedule", {}).get("weekly_dashboard_day", "monday")
            dashboard_time = self.config.get("schedule", {}).get("weekly_dashboard_time", "11:00")
            hour, minute = map(int, dashboard_time.split(":"))
            
            # Convert day name to number (0=Monday, 6=Sunday)
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            day_of_week = day_map.get(dashboard_day.lower(), 0)
            
            self.scheduler.add_job(
                self.run_weekly_dashboard,
                CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=self.timezone),
                id="weekly_dashboard",
                name="Weekly Dashboard Generation",
                replace_existing=True
            )
            
            logger.info(f"✅ Scheduled weekly dashboard on {dashboard_day} at {dashboard_time} {self.timezone}")
            
            # Schedule proactive 2FA authentication
            proactive_auth_times = self.config.get("schedule", {}).get("proactive_auth_times", [])
            if proactive_auth_times:
                logger.info(f"📋 Scheduling proactive authentication at {len(proactive_auth_times)} times...")
                for auth_time in proactive_auth_times:
                    try:
                        hour, minute = map(int, auth_time.split(":"))
                        
                        self.scheduler.add_job(
                            self.run_proactive_authentication,
                            CronTrigger(hour=hour, minute=minute, timezone=self.timezone),
                            id=f"proactive_auth_{auth_time.replace(':', '')}",
                            name=f"Proactive 2FA Authentication at {auth_time}",
                            replace_existing=True
                        )
                        
                        logger.info(f"✅ Scheduled proactive authentication at {auth_time} {self.timezone}")
                    except Exception as e:
                        logger.error(f"Error scheduling proactive auth at {auth_time}: {e}")
            else:
                logger.info("ℹ️  No proactive authentication times configured")
            
            # Schedule data cleanup weekly
            self.scheduler.add_job(
                self.cleanup_old_data,
                CronTrigger(day_of_week=6, hour=23, minute=0, timezone=self.timezone),
                id="data_cleanup",
                name="Data Cleanup",
                replace_existing=True
            )
            
            logger.info("✅ Scheduled data cleanup weekly")
            
            # Start scheduler
            self.scheduler.start()
            logger.info("🚀 Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def run_daily_check(self):
        """
        Run daily defect check:
        1. Check monitored components and send Slack notification
        2. Fetch all components in background for dashboard
        """
        try:
            logger.info("=" * 60)
            logger.info("🔍 Starting scheduled daily defect check (monitored components)")
            logger.info("=" * 60)
            
            # Get monitored components
            monitored_components = self.config.get("monitored_components", [])
            
            if not monitored_components:
                logger.warning("No monitored components configured")
                return
            
            # Step 1: Check defects for monitored components
            results = self.defect_checker.check_monitored_components(monitored_components, self.database)
            
            # Store check history
            self.database.store_check_history(results, True)
            
            # Send Slack notification (only for monitored components)
            if self.config.get("notifications", {}).get("only_notify_monitored", True):
                self.slack_notifier.send_defect_notification(results)
            
            logger.info("=" * 60)
            logger.info("✅ Daily defect check completed successfully")
            logger.info(f"   Monitored Components: {len(results['monitored_components'])}")
            logger.info(f"   Total Defects: {results['total_defects']}")
            logger.info(f"   Untriaged: {results['total_untriaged']}")
            logger.info("=" * 60)
            
            # Step 2: Fetch all components in background for dashboard
            if self.config.get("features", {}).get("all_components_tracking", True):
                logger.info("")
                logger.info("=" * 60)
                logger.info("🔄 Starting background fetch for all components (for dashboard)")
                logger.info("=" * 60)
                
                all_components = self.config.get("all_components", [])
                if all_components:
                    summary = self.defect_checker.fetch_all_components_background(all_components, self.database)
                    
                    logger.info("=" * 60)
                    logger.info("✅ Background fetch completed")
                    logger.info(f"   Total Components: {summary['total_components']}")
                    logger.info(f"   Successful: {summary['successful']}")
                    logger.info(f"   Failed: {summary['failed']}")
                    logger.info("=" * 60)
                else:
                    logger.warning("No all_components configured for background fetch")
            
        except Exception as e:
            logger.error(f"❌ Error in daily check: {e}")
            self.slack_notifier.send_error_notification(f"Daily check failed: {str(e)}")
            
            # Store failed check in history
            self.database.store_check_history({}, False, str(e))
    
    def clean_cache(self):
        """Clean Chrome profile cache to prevent unbounded growth"""
        try:
            logger.info("=" * 60)
            logger.info("🧹 Starting scheduled cache cleanup")
            logger.info("=" * 60)
            
            result = clean_chrome_cache()
            
            logger.info("=" * 60)
            logger.info("✅ Cache cleanup completed")
            logger.info(f"   Files/dirs deleted: {result['files_deleted']}")
            logger.info(f"   Space freed: {result['bytes_freed'] / 1024 / 1024:.2f} MB")
            if result['errors'] > 0:
                logger.warning(f"   Errors: {result['errors']}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error in cache cleanup: {e}")
    
    def run_all_components_fetch(self):
        """
        Fetch components in background with FULL processing (ML + duplicate detection)
        This runs at 9:00 AM to pre-process data for team notifications at 10:00 AM+
        NO notifications sent - just data preparation
        """
        try:
            logger.info("=" * 60)
            logger.info("🔄 Starting FULL background fetch for components")
            logger.info("   (Pre-processing data for team notifications)")
            logger.info("=" * 60)
            
            # Check if test_components is configured (for testing)
            test_components = self.config.get("schedule", {}).get("test_components", [])
            
            if test_components:
                # Extract component names if they're dictionaries
                component_names = []
                for comp in test_components:
                    if isinstance(comp, dict):
                        component_names.append(comp.get('name', comp))
                    else:
                        component_names.append(comp)
                
                components_to_fetch = component_names
                logger.info(f"📝 Using test_components: {len(components_to_fetch)} components")
                logger.info(f"   Components: {', '.join(components_to_fetch)}")
            else:
                # Use all components for production
                components_to_fetch = self.config.get("all_components", [])
                logger.info(f"📋 Using all_components: {len(components_to_fetch)} components")
            
            if not components_to_fetch:
                logger.warning("No components configured for background fetch")
                return
            
            # Fetch components with FULL processing
            summary = self.defect_checker.fetch_all_components_background(components_to_fetch, self.database)
            
            # Calculate total defects and untriaged from summary
            total_defects = summary.get('total_defects', 0)
            total_untriaged = summary.get('total_untriaged', 0)
            
            logger.info("=" * 60)
            logger.info("✅ Background fetch completed")
            logger.info(f"   Total Components: {summary['total_components']}")
            logger.info(f"   Successful: {summary['successful']}")
            logger.info(f"   Failed: {summary['failed']}")
            logger.info(f"   Data ready for team notifications")
            logger.info("=" * 60)
            
            # Send fetch completion notification
            try:
                self.slack_notifier.send_fetch_completion_notification(
                    num_components=summary['successful'],
                    total_defects=total_defects,
                    total_untriaged=total_untriaged
                )
            except Exception as notify_error:
                logger.error(f"Error sending fetch completion notification: {notify_error}")
            
        except Exception as e:
            logger.error(f"❌ Error in background fetch: {e}")
    
    def run_weekly_dashboard(self):
        """Generate and send weekly dashboard with insights"""
        try:
            logger.info("=" * 60)
            logger.info("📊 Generating weekly dashboard")
            logger.info("=" * 60)
            
            # Get weekly data
            weekly_data = self.database.get_weekly_data(days=7)
            
            if not weekly_data["dates"]:
                logger.warning("No data available for weekly dashboard")
                return
            
            # Calculate summary
            latest_snapshot = self.database.get_latest_snapshot()
            
            if latest_snapshot:
                total = sum(c["total"] for c in latest_snapshot["components"].values())
                untriaged = sum(c["untriaged"] for c in latest_snapshot["components"].values())
                
                summary = {
                    "total": total,
                    "untriaged": untriaged,
                    "trend": "N/A"  # Calculate trend if needed
                }
                
                # Fetch insights for all components
                all_components = list(latest_snapshot["components"].keys())
                insights_data = self._fetch_team_insights(all_components)
                
                # Send dashboard notification with public URL and insights
                dashboard_url = self.config.get('dashboard', {}).get('public_url', 'http://9.60.246.74:5001/dashboard')
                self.slack_notifier.send_dashboard_notification(dashboard_url, summary, insights_data)
                
                logger.info("✅ Weekly dashboard notification sent")
            
        except Exception as e:
            logger.error(f"❌ Error generating weekly dashboard: {e}")
            self.slack_notifier.send_error_notification(f"Weekly dashboard failed: {str(e)}")
    
    def run_team_weekly_dashboard(self, team: dict):
        """Generate and send team-specific weekly dashboard with insights"""
        try:
            team_name = team.get("name", "Unknown")
            logger.info("=" * 60)
            logger.info(f"📊 Generating weekly dashboard for {team_name}")
            logger.info("=" * 60)
            
            # Get team components
            components = [c.get("name") for c in team.get("components", [])]
            if not components:
                logger.warning(f"No components configured for {team_name}")
                return
            
            # Get weekly data for team components
            weekly_data = self.database.get_weekly_data(days=7)
            
            if not weekly_data["dates"]:
                logger.warning(f"No data available for {team_name} weekly dashboard")
                return
            
            # Calculate summary for team components
            latest_snapshot = self.database.get_latest_snapshot()
            
            if latest_snapshot:
                # Filter for team components only
                team_components_data = {
                    comp: data for comp, data in latest_snapshot["components"].items()
                    if comp in components
                }
                
                total = sum(c["total"] for c in team_components_data.values())
                untriaged = sum(c["untriaged"] for c in team_components_data.values())
                
                # Build component-wise breakdown with tag distribution
                component_breakdown = []
                for comp in components:
                    if comp in team_components_data:
                        comp_data = team_components_data[comp]
                        component_breakdown.append({
                            "name": comp,
                            "total": comp_data.get("total", 0),
                            "untriaged": comp_data.get("untriaged", 0),
                            "test_bugs": comp_data.get("test_bugs", 0),
                            "product_bugs": comp_data.get("product_bugs", 0),
                            "infra_bugs": comp_data.get("infra_bugs", 0)
                        })
                
                summary = {
                    "total": total,
                    "untriaged": untriaged,
                    "trend": "N/A",
                    "components": component_breakdown  # Component-wise stats with tags
                }
                
                # Fetch insights for team components
                insights_data = self._fetch_team_insights(components)
                
                # Send dashboard notification with insights
                dashboard_url = self.config.get('dashboard', {}).get('public_url', 'http://9.60.246.74:5001/dashboard')
                
                # Create team-specific notifier
                webhook_url = team.get("webhook_url")
                if not webhook_url:
                    logger.warning(f"No webhook URL configured for {team_name}")
                    return
                
                from src.slack_notifier import SlackNotifier
                team_notifier = SlackNotifier(
                    webhook_url=webhook_url,
                    default_channel=team.get("slack_channel", "#defect-notifications"),
                    config=self.config
                )
                
                team_notifier.send_team_dashboard_notification(
                    dashboard_url=dashboard_url,
                    summary=summary,
                    insights=insights_data,
                    team_name=team_name,
                    components=components
                )
                
                logger.info(f"✅ Weekly dashboard notification sent for {team_name}")
            
        except Exception as e:
            team_name = team.get('name', 'Unknown')
            logger.error(f"❌ Error generating weekly dashboard for {team_name}: {e}")
            # Send error notification to team's webhook
            try:
                webhook_url = team.get("webhook_url")
                if webhook_url:
                    from src.slack_notifier import SlackNotifier
                    team_notifier = SlackNotifier(
                        webhook_url=webhook_url,
                        default_channel=team.get("slack_channel", "#defect-notifications"),
                        config=self.config
                    )
                    team_notifier.send_error_notification(f"Weekly dashboard failed for {team_name}: {str(e)}")
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
    
    def _fetch_team_insights(self, components: list) -> dict:
        """Fetch and aggregate insights for team components, organized by component"""
        all_insights = {
            "duplicates": [],
            "rare_defects": [],
            "by_component": {}  # NEW: Organize insights by component
        }
        
        logger.info(f"🔍 Fetching insights for {len(components)} components: {components}")
        
        for component in components:
            try:
                # Get cached defects for the component
                cached_defects = self.database.get_all_cached_descriptions_for_component(component)
                
                logger.info(f"📊 Component '{component}': Found {len(cached_defects) if cached_defects else 0} cached defects")
                
                if cached_defects:
                    # Use insights analyzer to get insights
                    from src.insights_analyzer import InsightsAnalyzer
                    analyzer = InsightsAnalyzer(self.database, self.defect_checker)
                    # Set the duplicate detector so it can find duplicates
                    analyzer.set_duplicate_detector(self.defect_checker.duplicate_detector)
                    analyzer.set_defect_checker(self.defect_checker)
                    insights = analyzer.analyze_component(component, cached_defects)
                    
                    logger.info(f"💡 Component '{component}': Found {len(insights.get('duplicates', []))} duplicate groups, {len(insights.get('rare_defects', []))} rare defects")
                    
                    # Store component-specific insights
                    all_insights["by_component"][component] = {
                        "duplicates": insights.get("duplicates", []),
                        "rare_defects": insights.get("rare_defects", [])
                    }
                    
                    # Also aggregate for backward compatibility
                    if insights.get("duplicates"):
                        all_insights["duplicates"].extend(insights["duplicates"])
                    
                    if insights.get("rare_defects"):
                        all_insights["rare_defects"].extend(insights["rare_defects"])
            except Exception as e:
                logger.error(f"Error fetching insights for {component}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.info(f"✅ Total aggregated insights: {len(all_insights['duplicates'])} duplicate groups, {len(all_insights['rare_defects'])} rare defects")
        
        return all_insights
    
    def refresh_session(self):
        """Refresh IBM session (no error notifications)"""
        try:
            logger.info("🔄 Refreshing IBM session...")
            
            if self.defect_checker.authenticator.refresh_session():
                logger.info("✅ Session refreshed successfully")
            else:
                # Session refresh failed, but check if we can still authenticate
                logger.warning("⚠️ Session refresh returned false, verifying authentication...")
                
                # Try to get a session - this will trigger re-authentication if needed
                session = self.defect_checker.authenticator.get_session()
                
                if session:
                    logger.info("✅ Session recovered through re-authentication")
                else:
                    # Log error but don't send notification (user doesn't want spam)
                    logger.error("❌ Session refresh and re-authentication both failed")
                    logger.info("💡 Tip: Refresh your cookies using ./refresh_cookies_auto.sh")
                
        except Exception as e:
            logger.error(f"Error refreshing session: {e}")
            logger.info("💡 Tip: Refresh your cookies using ./refresh_cookies_auto.sh")
    
    def run_proactive_authentication(self):
        """
        Proactively authenticate with IBM to keep session fresh
        Forces a FRESH LOGIN with 2FA to reset session expiration timer
        This prevents mid-task authentication failures
        """
        try:
            logger.info("=" * 60)
            logger.info("🔐 Starting proactive FRESH 2FA authentication")
            logger.info("   (Forcing fresh login to reset session timer)")
            logger.info("=" * 60)
            
            # Get the browser manager
            from browser_manager import get_browser_manager
            browser_manager = get_browser_manager()
            
            # Force a fresh login with 2FA to get brand new cookies
            logger.info("🔄 Forcing fresh login to reset session expiration...")
            
            # Run the async fresh login in the browser manager's event loop
            loop = browser_manager._ensure_event_loop()
            success = loop.run_until_complete(browser_manager.force_fresh_login())
            
            if success:
                logger.info("=" * 60)
                logger.info("✅ Proactive authentication completed successfully")
                logger.info("   Session is now fresh and ready for scheduled tasks")
                logger.info("=" * 60)
            else:
                logger.error("=" * 60)
                logger.error("❌ Proactive authentication failed")
                logger.error("   Please check 2FA approval or cookie configuration")
                logger.error("=" * 60)
                
                # Send notification about authentication failure
                try:
                    self.slack_notifier.send_error_notification(
                        "⚠️ Proactive authentication failed. Please approve 2FA or check cookie configuration."
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to send authentication failure notification: {notify_error}")
            
        except Exception as e:
            logger.error(f"❌ Error in proactive authentication: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Send error notification
            try:
                self.slack_notifier.send_error_notification(
                    f"Proactive authentication error: {str(e)}"
                )
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
    
    def cleanup_old_data(self):
        """Clean up old data from database"""
        try:
            logger.info("🧹 Cleaning up old data...")
            
            retention_days = self.config.get("dashboard", {}).get("retention_days", 90)
            self.database.cleanup_old_data(retention_days)
            
            logger.info("✅ Data cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning up data: {e}")
    
    def retrain_ml_model(self):
        """Retrain ML model weekly with incremental learning (keeps existing training data)"""
        try:
            logger.info("=" * 60)
            logger.info("🤖 Starting weekly ML model incremental training")
            logger.info("=" * 60)
            
            # Get training components from config
            ml_config = self.config.get("ml_training", {})
            training_components = ml_config.get("training_components", [])
            
            # If no training components specified, use all components
            if not training_components:
                training_components = self.config.get("all_components", [])
            
            # Extract component names if they're dictionaries
            # Config format: [{'name': 'JPA'}, ...] or ['JPA', ...]
            component_names = []
            for comp in training_components:
                if isinstance(comp, dict):
                    component_names.append(comp.get('name', comp))
                else:
                    component_names.append(comp)
            
            if component_names:
                # NO DELETION - Keep existing model and training data
                # The train_ml_model_on_all_components will load old data and combine with new
                logger.info(f"🎓 Incremental training on {len(component_names)} components...")
                logger.info("   (Keeping existing training data + adding new defects)")
                
                success = self.defect_checker.train_ml_model_on_all_components(component_names)
                
                if success:
                    logger.info("✅ ML model incrementally trained successfully")
                    
                    # Extract ML stats and send notification
                    try:
                        # Get training stats from the suggester
                        stats = self.defect_checker.tag_suggester.get_training_stats()
                        
                        if stats.get('trained'):
                            # Accuracy is already formatted as string (e.g., "58.67%")
                            accuracy_str = stats.get('accuracy', '0.00%')
                            total_samples = stats.get('total_samples', 0)
                            
                            # Send Slack notification
                            self.slack_notifier.send_ml_training_notification(
                                num_components=len(training_components),
                                accuracy=accuracy_str,
                                total_defects=total_samples,
                                success=True
                            )
                        else:
                            logger.warning("ML model trained but stats not available")
                    except Exception as notify_error:
                        logger.error(f"Error sending ML training notification: {notify_error}")
                else:
                    logger.error("❌ ML model training failed")
                    # Send failure notification
                    try:
                        self.slack_notifier.send_ml_training_notification(
                            num_components=len(training_components),
                            accuracy="N/A",
                            total_defects=0,
                            success=False
                        )
                    except Exception as notify_error:
                        logger.error(f"Error sending ML training failure notification: {notify_error}")
            else:
                logger.warning("⚠️  No components configured for ML training")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error training ML model: {e}")
    
    def run_team_check(self, team: dict):
        """
        Run defect check for a specific team
        Uses cached data from daily background fetch (13:24) instead of re-fetching
        Each team has its own components, webhook, and schedule
        """
        try:
            team_name = team.get("name", "Unknown Team")
            logger.info("=" * 60)
            logger.info(f"🔍 Starting defect check for team: {team_name}")
            logger.info("=" * 60)
            
            # Get team's monitored components
            team_components = team.get("components", [])
            
            if not team_components:
                logger.warning(f"No components configured for team {team_name}")
                return
            
            # Extract component names from team config
            component_names = [c.get("name") for c in team_components if c.get("name")]
            
            if not component_names:
                logger.warning(f"No valid component names for team {team_name}")
                return
            
            # Try to get cached data from daily background fetch (13:24)
            logger.info(f"📦 Retrieving cached data for {len(component_names)} components...")
            results = self.database.get_team_snapshot_from_cache(component_names)
            
            if not results:
                # Fallback: If no cached data, fetch fresh data
                logger.warning(f"⚠️  No cached data found for {team_name}, fetching fresh data...")
                results = self.defect_checker.check_monitored_components(team_components, self.database, team_name=team_name)
            else:
                logger.info(f"✅ Using cached data from daily background fetch (13:24)")
            
            # Store check history
            self.database.store_check_history(results, True)
            
            # Send notification to team's webhook
            team_webhook = team.get("webhook_url")
            team_channel = team.get("slack_channel", f"#{team_name.lower().replace(' ', '-')}")
            
            if team_webhook:
                # Create a temporary notifier for this team
                from slack_notifier import SlackNotifier
                team_notifier = SlackNotifier(
                    webhook_url=team_webhook,
                    default_channel=team_channel,
                    config=self.config
                )
                # Send defect notification to team's webhook
                team_notifier.send_defect_notification(results)
            else:
                # Use default notifier for defect notification
                self.slack_notifier.send_defect_notification(results)
            
            # ALWAYS send confirmation to main system webhook (not team webhook)
            num_components = len(team_components)
            self.slack_notifier.send_notification_sent_confirmation(num_components, results['total_untriaged'])
            
            logger.info("=" * 60)
            logger.info(f"✅ Team check completed for {team_name}")
            logger.info(f"   Components: {len(results['monitored_components'])}")
            logger.info(f"   Total Defects: {results['total_defects']}")
            logger.info(f"   Untriaged: {results['total_untriaged']}")
            logger.info("=" * 60)
            
        except Exception as e:
            team_name = team.get("name", "Unknown Team")
            logger.error(f"❌ Error in team check for {team_name}: {e}")
            webhook_url = team.get("webhook_url")
            if webhook_url:
                from slack_notifier import SlackNotifier
                team_notifier = SlackNotifier(
                    webhook_url=webhook_url,
                    default_channel=team.get("slack_channel", "#defect-notifications"),
                    config=self.config
                )
                team_notifier.send_error_notification(f"Team check failed for {team_name}: {str(e)}")
    
    def run_manual_check(self):
        """Run manual defect check (for testing)"""
        logger.info("🔍 Running manual defect check...")
        self.run_daily_check()
    
    def get_next_run_times(self) -> dict:
        """Get next scheduled run times"""
        jobs = {}
        
        for job in self.scheduler.get_jobs():
            jobs[job.id] = {
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
        
        return jobs

# Made with Bob
