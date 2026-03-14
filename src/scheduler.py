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
            # Schedule daily defect check (monitored components only)
            daily_time = self.config.get("schedule", {}).get("daily_check_time", "10:00")
            hour, minute = map(int, daily_time.split(":"))
            
            self.scheduler.add_job(
                self.run_daily_check,
                CronTrigger(hour=hour, minute=minute, timezone=self.timezone),
                id="daily_check",
                name="Daily Defect Check",
                replace_existing=True
            )
            
            logger.info(f"✅ Scheduled daily check at {daily_time} {self.timezone}")
            
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
            
            # Schedule session refresh every 2 hours
            self.scheduler.add_job(
                self.refresh_session,
                'interval',
                hours=2,
                id="session_refresh",
                name="Session Refresh",
                replace_existing=True
            )
            
            logger.info("✅ Scheduled session refresh every 2 hours")
            
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
        """Fetch ALL 51 components in background (no notifications)"""
        try:
            logger.info("=" * 60)
            logger.info("🔄 Starting background fetch for all components")
            logger.info("=" * 60)
            
            # Get all components list
            all_components = self.config.get("all_components", [])
            
            if not all_components:
                logger.warning("No components configured for background fetch")
                return
            
            # Fetch all components
            summary = self.defect_checker.fetch_all_components_background(all_components, self.database)
            
            logger.info("=" * 60)
            logger.info("✅ Background fetch completed")
            logger.info(f"   Total Components: {summary['total_components']}")
            logger.info(f"   Successful: {summary['successful']}")
            logger.info(f"   Failed: {summary['failed']}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error in background fetch: {e}")
    
    def run_weekly_dashboard(self):
        """Generate and send weekly dashboard"""
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
                
                # Send dashboard notification with public URL
                dashboard_url = self.config.get('dashboard', {}).get('public_url', 'http://9.60.246.74:5001/dashboard')
                self.slack_notifier.send_dashboard_notification(dashboard_url, summary)
                
                logger.info("✅ Weekly dashboard notification sent")
            
        except Exception as e:
            logger.error(f"❌ Error generating weekly dashboard: {e}")
            self.slack_notifier.send_error_notification(f"Weekly dashboard failed: {str(e)}")
    
    def refresh_session(self):
        """Refresh IBM session"""
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
                    # Only send error if we truly can't authenticate
                    logger.error("❌ Session refresh and re-authentication both failed")
                    self.slack_notifier.send_error_notification("IBM session refresh failed - unable to authenticate")
                
        except Exception as e:
            logger.error(f"Error refreshing session: {e}")
            self.slack_notifier.send_error_notification(f"IBM session refresh error: {str(e)}")
    
    def cleanup_old_data(self):
        """Clean up old data from database"""
        try:
            logger.info("🧹 Cleaning up old data...")
            
            retention_days = self.config.get("dashboard", {}).get("retention_days", 90)
            self.database.cleanup_old_data(retention_days)
            
            logger.info("✅ Data cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning up data: {e}")
    
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
