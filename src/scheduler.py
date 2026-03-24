"""
Scheduler Module
Handles automated scheduling of defect checks and dashboard generation
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

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
            # Check ML model status (but don't train on startup to avoid worker timeout)
            logger.info("")
            logger.info("🤖 ML Tag Suggestion System Status...")
            
            if self.defect_checker.suggester_trained:
                logger.info("✅ ML model loaded and ready")
            else:
                logger.info("⚠️  ML model not trained yet")
                logger.info("   Run 'docker-compose exec defect-monitor python3 retrain_model.sh' to train")
            logger.info("")
            
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
            
            # Session refresh disabled - cookies are long-lived (8 hours)
            # Manual refresh can be done via ./refresh_cookies_auto.sh when needed
            
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
    
    def run_all_components_fetch(self):
        """Fetch components in background (no notifications)"""
        try:
            logger.info("=" * 60)
            logger.info("🔄 Starting background fetch for components")
            logger.info("=" * 60)
            
            # Check if test_components is configured (for testing)
            test_components = self.config.get("schedule", {}).get("test_components", [])
            
            if test_components:
                # Use test components for testing
                components_to_fetch = test_components
                logger.info(f"📝 Using test_components: {len(components_to_fetch)} components")
                logger.info(f"   Components: {', '.join(components_to_fetch)}")
            else:
                # Use all components for production
                components_to_fetch = self.config.get("all_components", [])
                logger.info(f"📋 Using all_components: {len(components_to_fetch)} components")
            
            if not components_to_fetch:
                logger.warning("No components configured for background fetch")
                return
            
            # Fetch components
            summary = self.defect_checker.fetch_all_components_background(components_to_fetch, self.database)
            
            logger.info("=" * 60)
            logger.info("✅ Background fetch completed")
            logger.info(f"   Total Components: {summary['total_components']}")
            logger.info(f"   Successful: {summary['successful']}")
            logger.info(f"   Failed: {summary['failed']}")
            logger.info("=" * 60)
            
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
                
                summary = {
                    "total": total,
                    "untriaged": untriaged,
                    "trend": "N/A"
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
        """Fetch and aggregate insights for team components"""
        all_insights = {
            "duplicates": [],
            "rare_defects": []
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
                    
                    # Aggregate duplicates
                    if insights.get("duplicates"):
                        all_insights["duplicates"].extend(insights["duplicates"])
                    
                    # Aggregate rare defects
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
        """Retrain ML model weekly"""
        try:
            logger.info("=" * 60)
            logger.info("🤖 Starting weekly ML model retraining")
            logger.info("=" * 60)
            
            # Get training components from config
            ml_config = self.config.get("ml_training", {})
            training_components = ml_config.get("training_components", [])
            
            # If no training components specified, use all components
            if not training_components:
                training_components = self.config.get("all_components", [])
            
            if training_components:
                # Delete old model to force retraining
                import os
                model_path = "data/tag_model.pkl"
                if os.path.exists(model_path):
                    os.remove(model_path)
                    logger.info(f"🗑️  Deleted old model: {model_path}")
                
                # Retrain
                logger.info(f"🎓 Retraining ML model on {len(training_components)} components...")
                success = self.defect_checker.train_ml_model_on_all_components(training_components)
                
                if success:
                    logger.info("✅ ML model retrained successfully")
                else:
                    logger.error("❌ ML model retraining failed")
            else:
                logger.warning("⚠️  No components configured for ML training")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error retraining ML model: {e}")
    
    def run_team_check(self, team: dict):
        """
        Run defect check for a specific team
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
            
            # Check defects for team's components (with team-specific checkpoint)
            results = self.defect_checker.check_monitored_components(team_components, self.database, team_name=team_name)
            
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
                team_notifier.send_defect_notification(results)
                logger.info(f"✅ Notification sent to {team_name} ({team_channel})")
            else:
                # Use default notifier
                self.slack_notifier.send_defect_notification(results)
                logger.info(f"✅ Notification sent using default webhook")
            
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
