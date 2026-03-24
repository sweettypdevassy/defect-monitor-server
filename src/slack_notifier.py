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
        Send SINGLE grouped defect notification to Slack
        Matches Chrome extension format exactly - one notification with all components and SOE defects
        """
        try:
            if component_channels is None:
                component_channels = {}
            
            # Send single grouped notification (matches Chrome extension)
            self._send_grouped_notification(results)
            
            logger.info("✅ Slack notification sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _send_grouped_notification(self, results: Dict):
        """
        Send SINGLE grouped notification with all components and SOE defects
        Matches Chrome extension format exactly
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        
        # Get components with untriaged defects
        components_data = results.get("components", {})
        total_untriaged = results.get("total_untriaged", 0)
        
        # Get SOE defects
        soe_data = results.get("soe_triage", {})
        soe_defects = soe_data.get("defects", []) if soe_data else []
        
        # Build message
        if total_untriaged == 0 and len(soe_defects) == 0:
            # No defects at all
            self._send_no_defects_notification(results)
            return
        
        # Calculate total defects to show
        total_defects = total_untriaged + len(soe_defects)
        defect_word = "Defect" if total_defects == 1 else "Defects"
        
        message = f"⚠️ {total_defects} Untriaged {defect_word}\n\n"
        message += f"Found {total_defects} untriaged {defect_word.lower()} across {len(components_data)} component(s).\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Add defects grouped by component
        for component_index, (component_name, component_data) in enumerate(components_data.items()):
            untriaged_defects = [d for d in component_data.get("defects", []) if d.get("is_untriaged", True)]
            component_defect_count = len(untriaged_defects)
            
            if component_defect_count == 0:
                continue
            
            message += f"📦 {component_name} ({component_defect_count} {('defect' if component_defect_count == 1 else 'defects')})\n\n"
            
            # Show up to 5 defects per component
            defects_to_show = untriaged_defects[:5]
            
            for index, defect in enumerate(defects_to_show):
                defect_id = defect.get('id', 'N/A')
                defect_link = f"https://wasrtc.hursley.ibm.com:9443/jazz/web/projects/WS-CD#action=com.ibm.team.workitem.viewWorkItem&id={defect_id}"
                
                message += f"{index + 1}. Defect ID: {defect_id}\n"
                message += f"   Link: {defect_link}\n"
                message += f"   Summary: {defect.get('summary', 'N/A')}\n"
                
                # Add duplicate detection info if available
                duplicate_info = defect.get('duplicate_info')
                if duplicate_info and duplicate_info.get('is_duplicate'):
                    dup_id = duplicate_info.get('duplicate_id')
                    dup_tags = duplicate_info.get('duplicate_tags', [])
                    similarity = duplicate_info.get('similarity', 0.0)
                    similarity_pct = int(similarity * 100)
                    
                    dup_link = f"https://wasrtc.hursley.ibm.com:9443/jazz/web/projects/WS-CD#action=com.ibm.team.workitem.viewWorkItem&id={dup_id}"
                    
                    message += f"   🔄 Possible Duplicate: Defect #{dup_id} ({similarity_pct}% similar)\n"
                    message += f"   🔗 Duplicate Link: {dup_link}\n"
                    if dup_tags:
                        message += f"   📋 Previous Tags: {dup_tags}\n"
                
                # Add AI-suggested tag if available
                suggested_tag = defect.get('suggested_tag')
                if suggested_tag and suggested_tag != 'unknown':
                    confidence = defect.get('suggestion_confidence', 0.0)
                    reasoning = defect.get('suggestion_reasoning', '')
                    confidence_pct = int(confidence * 100)
                    
                    # Format tag name nicely
                    tag_display = suggested_tag.replace('_', ' ').title()
                    
                    message += f"   🤖 Suggested Tag: {tag_display} ({confidence_pct}% confidence)\n"
                    if reasoning:
                        message += f"   💡 Reason: {reasoning}\n"
                
                message += f"   Triage Tags: {defect.get('triageTags', '[]')}\n"
                message += f"   State: {defect.get('state', 'Open')}\n"
                message += f"   Owner: {defect.get('owner', 'Unassigned')}\n"
                
                if index < len(defects_to_show) - 1:
                    message += "\n"
            
            if component_defect_count > 5:
                message += f"\n... and {component_defect_count - 5} more defect(s) for {component_name}\n"
            
            # Add separator between components
            if component_index < len(components_data) - 1 or len(soe_defects) > 0:
                message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Add SOE Triage overdue defects section if available
        if soe_defects and len(soe_defects) > 0:
            message += f"📋 SOE Triage Overdue Defects ({len(soe_defects)})\n\n"
            
            # Show up to 5 SOE defects
            soe_defects_to_show = soe_defects[:5]
            
            for index, defect in enumerate(soe_defects_to_show):
                defect_id = defect.get('id', 'N/A')
                defect_link = f"https://wasrtc.hursley.ibm.com:9443/jazz/web/projects/WS-CD#action=com.ibm.team.workitem.viewWorkItem&id={defect_id}"
                
                message += f"{index + 1}. Defect ID: {defect_id}\n"
                message += f"   Link: {defect_link}\n"
                message += f"   Summary: {defect.get('summary', 'N/A')}\n"
                message += f"   Functional Area: {defect.get('functionalArea', 'N/A')}\n"
                message += f"   Filed Against: {defect.get('filedAgainst', 'N/A')}\n"
                message += f"   Owner: {defect.get('ownedBy', 'Unassigned')}\n"
                message += f"   Created: {defect.get('creationDate', 'N/A')}\n"
                
                if index < len(soe_defects_to_show) - 1:
                    message += "\n"
            
            if len(soe_defects) > 5:
                message += f"\n... and {len(soe_defects) - 5} more SOE overdue defect(s)\n"
        
        message += f"\n\nLast checked: {timestamp}"
        
        # Send to Slack using simple format (Workflow Builder compatible)
        payload = {"message": message}
        
        response = requests.post(self.webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Sent grouped notification: {total_defects} total defects")
    
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
    
    def send_dashboard_notification(self, dashboard_url: str, summary: Dict, insights: Optional[Dict] = None):
        """Send weekly dashboard notification with optional insights"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
            
            message = "📊 Weekly Defect Dashboard\n\n"
            message += "Weekly Summary:\n"
            message += f"• Total Defects: {summary.get('total', 0)}\n"
            message += f"• Untriaged: {summary.get('untriaged', 0)}\n"
            message += f"• Week-over-Week Change: {summary.get('trend', 'N/A')}\n\n"
            
            # Add insights if provided
            if insights:
                message += self._format_insights(insights)
            
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
    
    def send_team_dashboard_notification(self, dashboard_url: str, summary: Dict, insights: Dict, team_name: str, components: list):
        """Send team-specific weekly dashboard notification with insights"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
            
            message = f"📊 Weekly Defect Dashboard - {team_name}\n\n"
            message += f"Components: {', '.join(components)}\n\n"
            message += "Weekly Summary:\n"
            message += f"• Total Defects: {summary.get('total', 0)}\n"
            message += f"• Untriaged: {summary.get('untriaged', 0)}\n"
            message += f"• Week-over-Week Change: {summary.get('trend', 'N/A')}\n\n"
            
            # Add insights
            message += self._format_insights(insights)
            
            message += f"📊 View Full Dashboard: {dashboard_url}\n\n"
            message += f"Generated: {timestamp}"
            
            payload = {"message": message}
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"✅ Team dashboard notification sent for {team_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending team dashboard notification: {e}")
            return False
    
    def _format_insights(self, insights: Dict) -> str:
        """Format insights for Slack message"""
        message = "💡 Best Practices & Insights:\n"
        
        # Duplicate defects
        if insights.get("duplicates") and len(insights["duplicates"]) > 0:
            for group in insights["duplicates"][:10]:  # Show up to 10 duplicate groups
                defect_ids = [group["main_defect"]["id"]]
                if group.get("similar_defects"):
                    defect_ids.extend([d["id"] for d in group["similar_defects"]])
                
                defect_links = ", ".join([f"#{id}" for id in defect_ids])
                message += f"• Defects {defect_links} are duplicates\n"
        
        # Rare/old defects
        if insights.get("rare_defects") and len(insights["rare_defects"]) > 0:
            for defect in insights["rare_defects"][:15]:  # Show up to 15 rare defects
                age_info = defect.get("age_info", "old defect")
                creation_date = defect.get("creation_date", "")
                build_count = defect.get("build_count", 1)
                
                creation_info = f" - Created: {creation_date}" if creation_date else ""
                build_info = f" - {build_count} build{'s' if build_count > 1 else ''}"
                
                message += f"• Defect #{defect['id']} ({age_info}{creation_info}{build_info})\n"
        
        # If no insights
        if not insights.get("duplicates") and not insights.get("rare_defects"):
            message += "• No specific insights available\n"
        
        message += "\n"
        return message
    
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
