"""
Slack Notification Module
Sends formatted notifications to Slack channels
Matches Chrome extension format for Workflow Builder compatibility
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Handles sending notifications to Slack (Workflow Builder compatible)"""
    
    def __init__(self, webhook_url: str, default_channel: str = "#defect-notifications"):
        self.webhook_url = webhook_url
        self.default_channel = default_channel
    
    def send_defect_notification(self, results: Dict, component_channels: Optional[Dict] = None) -> bool:
        """
        Send defect notification to Slack
        Uses simple text format compatible with Workflow Builder (matches Chrome extension)
        """
        try:
            if component_channels is None:
                component_channels = {}
            
            # Send notification for each component with untriaged defects
            for component, data in results.get("components", {}).items():
                if data["untriaged"] > 0:
                    self._send_component_notification(component, data)
            
            # Send summary if no defects
            if results["total_untriaged"] == 0:
                self._send_no_defects_notification(results)
            
            logger.info("✅ Slack notifications sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _send_component_notification(self, component: str, data: Dict):
        """Send notification for a specific component (Chrome extension format)"""
        untriaged_defects = [d for d in data["defects"] if d.get("is_untriaged", True)]
        defect_count = len(untriaged_defects)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        
        # Build message in Chrome extension format
        defect_word = "defect" if defect_count == 1 else "defects"
        message = f"⚠️ {defect_count} Untriaged {defect_word.capitalize()}\n\n"
        message += f"There {'is' if defect_count == 1 else 'are'} {defect_count} untriaged {defect_word} for the {component} component that need{'s' if defect_count == 1 else ''} attention.\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Add details for each defect (limit to first 10)
        defects_to_show = untriaged_defects[:10]
        
        for index, defect in enumerate(defects_to_show):
            defect_id = defect.get('id', 'N/A')
            defect_link = f"https://wasrtc.hursley.ibm.com:9443/jazz/web/projects/WS-CD#action=com.ibm.team.workitem.viewWorkItem&id={defect_id}"
            
            message += f"{index + 1}. Defect ID: {defect_id}\n"
            message += f"   Link: {defect_link}\n"
            message += f"   Summary: {defect.get('summary', 'N/A')}\n"
            message += f"   Triage Tags: {defect.get('triage_tags', '[]')}\n"
            message += f"   State: {defect.get('state', 'Open')}\n"
            message += f"   Owner: {defect.get('owner', 'Unassigned')}\n"
            
            if index < len(defects_to_show) - 1:
                message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if defect_count > 10:
            message += f"\n\n... and {defect_count - 10} more defect(s)"
        
        message += f"\n\nLast checked: {timestamp}"
        
        # Send to Slack using simple format (Workflow Builder compatible)
        payload = {"message": message}
        
        response = requests.post(self.webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Sent notification for {component}: {defect_count} defects")
    
    def _send_no_defects_notification(self, results: Dict):
        """Send notification when no untriaged defects found (Chrome extension format)"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        
        # Get list of components checked
        components = list(results.get("components", {}).keys())
        component_list = ", ".join(components) if components else "all components"
        
        message = f"✅ No Untriaged Defects\n\n"
        message += f"Great job! There are currently no untriaged defects for {component_list}.\n\n"
        message += f"Last checked: {timestamp}"
        
        payload = {"message": message}
        
        response = requests.post(self.webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("✅ Sent 'no defects' notification")
    
    def send_dashboard_notification(self, dashboard_url: str, summary: Dict):
        """Send weekly dashboard notification"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
            
            message = "📊 Weekly Defect Dashboard\n\n"
            message += "Weekly Summary:\n"
            message += f"• Total Defects: {summary.get('total', 0)}\n"
            message += f"• Untriaged: {summary.get('untriaged', 0)}\n"
            message += f"• Week-over-Week Change: {summary.get('trend', 'N/A')}\n\n"
            message += f"📊 View Full Dashboard: {dashboard_url}\n\n"
            message += f"Generated: {timestamp}"
            
            payload = {"message": message}
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("✅ Dashboard notification sent to Slack")
            return True
            
        except Exception as e:
            logger.error(f"Error sending dashboard notification: {e}")
            return False
    
    def send_error_notification(self, error_message: str):
        """Send error notification to Slack"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
            
            message = f"🚨 Defect Monitor Error\n\n"
            message += f"An error occurred while checking for defects:\n\n"
            message += f"{error_message}\n\n"
            message += f"Time: {timestamp}"
            
            payload = {"message": message}
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("✅ Error notification sent to Slack")
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")

# Made with Bob
