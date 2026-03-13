"""
Defect Checker Module
Fetches and processes defects from IBM Build Break Report and SOE Triage
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DefectChecker:
    """Handles fetching and processing defects from IBM systems"""
    
    def __init__(self, authenticator):
        self.authenticator = authenticator
        self.build_break_base_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas"
        self.soe_triage_url = "https://wasrtc.hursley.ibm.com:9443/jazz/oslc/workitems.json"
    
    def fetch_defects_for_component(self, component: str) -> Optional[List[Dict]]:
        """
        Fetch defects for a specific component from Build Break Report
        Returns list of defects or None on error
        """
        try:
            session = self.authenticator.get_session()
            if not session:
                logger.error(f"No valid session for fetching {component} defects")
                return None
            
            logger.info(f"Fetching defects for component: {component}")
            
            # Build URL with component as query parameter
            api_url = f"{self.build_break_base_url}?fas={component}"
            
            response = session.get(
                api_url,
                timeout=30,
                headers={
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache'
                },
                verify=False  # Disable SSL verification for IBM self-signed certs
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch defects for {component}: HTTP {response.status_code}")
                return None
            
            defects = response.json()
            
            if not isinstance(defects, list):
                logger.error(f"Unexpected response format for {component}")
                return None
            
            logger.info(f"✅ Fetched {len(defects)} defects for {component}")
            return defects
            
        except Exception as e:
            logger.error(f"Error fetching defects for {component}: {e}")
            return None
    
    def fetch_soe_triage_defects(self) -> Optional[List[Dict]]:
        """
        Fetch overdue SOE Triage defects from Jazz/RTC
        Returns list of defects or None on error
        """
        try:
            session = self.authenticator.get_session()
            if not session:
                logger.error("No valid session for fetching SOE Triage defects")
                return None
            
            logger.info("Fetching SOE Triage defects...")
            
            # Query parameters for overdue defects
            params = {
                "oslc.where": "rtc_cm:filedAgainst=\"com.ibm.team.workitem.category/_-gOYsNqREeWlU5rCLW-Rvw\"",
                "oslc.select": "*",
                "oslc.pageSize": "100"
            }
            
            response = session.get(
                self.soe_triage_url,
                params=params,
                timeout=30,
                headers={'Cache-Control': 'no-cache'},
                verify=False  # Disable SSL verification for IBM self-signed certs
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch SOE Triage defects: HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse Jazz/RTC response
            defects = self._parse_jazz_workitems(data)
            
            logger.info(f"✅ Fetched {len(defects)} SOE Triage defects")
            return defects
            
        except Exception as e:
            logger.error(f"Error fetching SOE Triage defects: {e}")
            return None
    
    def _parse_jazz_workitems(self, data: Dict) -> List[Dict]:
        """Parse Jazz/RTC work items into standardized format"""
        defects = []
        
        try:
            results = data.get("oslc:results", [])
            
            for item in results:
                defect = {
                    "id": item.get("dcterms:identifier", "Unknown"),
                    "summary": item.get("dcterms:title", "No summary"),
                    "owner": item.get("rtc_cm:ownedBy", {}).get("rdf:resource", "Unassigned"),
                    "state": item.get("rtc_cm:state", {}).get("rdf:resource", "Unknown"),
                    "creationDate": item.get("dcterms:created", ""),
                    "filedAgainst": item.get("rtc_cm:filedAgainst", {}).get("rdf:resource", ""),
                    "functionalArea": item.get("rtc_cm:com.ibm.team.apt.attribute.complexity", ""),
                    "description": item.get("dcterms:description", ""),
                    "source": "SOE_TRIAGE"
                }
                defects.append(defect)
                
        except Exception as e:
            logger.error(f"Error parsing Jazz work items: {e}")
        
        return defects
    
    def parse_defects(self, defects: List[Dict], component: str) -> Dict:
        """
        Parse and categorize defects
        Returns dict with categorized defects
        """
        result = {
            "component": component,
            "total": len(defects),
            "untriaged": 0,
            "test_bugs": 0,
            "product_bugs": 0,
            "infra_bugs": 0,
            "defects": []
        }
        
        for defect in defects:
            # Determine if untriaged
            state = defect.get("state", "").lower()
            triage_tags = defect.get("triageTags", [])
            
            is_untriaged = (
                state in ["new", "open", ""] or
                not triage_tags or
                "untriaged" in str(triage_tags).lower()
            )
            
            if is_untriaged:
                result["untriaged"] += 1
            
            # Categorize by functional area
            functional_area = defect.get("functionalArea", "").lower()
            
            if "test" in functional_area or "automation" in functional_area:
                result["test_bugs"] += 1
            elif "infra" in functional_area or "infrastructure" in functional_area:
                result["infra_bugs"] += 1
            else:
                result["product_bugs"] += 1
            
            # Add to defects list
            result["defects"].append({
                "id": defect.get("id", "Unknown"),
                "summary": defect.get("summary", "No summary"),
                "owner": defect.get("owner", "Unassigned"),
                "state": defect.get("state", "Unknown"),
                "functionalArea": defect.get("functionalArea", "Unknown"),
                "buildsReported": defect.get("buildsReported", []),
                "triageTags": defect.get("triageTags", []),
                "is_untriaged": is_untriaged
            })
        
        return result
    
    def check_all_components(self, components: List[str]) -> Dict:
        """
        Check defects for all configured components
        Returns dict with results for each component
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "soe_triage": None,
            "total_defects": 0,
            "total_untriaged": 0
        }
        
        # Fetch defects for each component
        for component in components:
            defects = self.fetch_defects_for_component(component)
            
            if defects is not None:
                parsed = self.parse_defects(defects, component)
                results["components"][component] = parsed
                results["total_defects"] += parsed["total"]
                results["total_untriaged"] += parsed["untriaged"]
            else:
                logger.warning(f"Skipping {component} due to fetch error")
        
        # Fetch SOE Triage defects
        soe_defects = self.fetch_soe_triage_defects()
        if soe_defects is not None:
            results["soe_triage"] = {
                "total": len(soe_defects),
                "defects": soe_defects
            }
            results["total_defects"] += len(soe_defects)
        
        logger.info(f"✅ Check complete: {results['total_defects']} total defects, {results['total_untriaged']} untriaged")
        
        return results
    
    def fetch_all_components_background(self, all_components: List[str], database) -> Dict:
        """
        Fetch defects for ALL 51 components in background (for component explorer)
        Stores data in database but doesn't send notifications
        Returns summary of fetch operation
        """
        logger.info(f"🔄 Starting background fetch for {len(all_components)} components...")
        
        fetch_summary = {
            "timestamp": datetime.now().isoformat(),
            "total_components": len(all_components),
            "successful": 0,
            "failed": 0,
            "components_data": {}
        }
        
        for component in all_components:
            try:
                defects = self.fetch_defects_for_component(component)
                
                if defects is not None:
                    parsed = self.parse_defects(defects, component)
                    
                    # Store in database
                    database.store_all_components_snapshot(component, parsed, is_monitored=False)
                    
                    fetch_summary["successful"] += 1
                    fetch_summary["components_data"][component] = {
                        "total": parsed["total"],
                        "untriaged": parsed["untriaged"]
                    }
                    
                    logger.info(f"✅ Fetched {component}: {parsed['total']} defects ({parsed['untriaged']} untriaged)")
                else:
                    fetch_summary["failed"] += 1
                    logger.warning(f"❌ Failed to fetch {component}")
                    
            except Exception as e:
                fetch_summary["failed"] += 1
                logger.error(f"❌ Error fetching {component}: {e}")
        
        logger.info(f"✅ Background fetch complete: {fetch_summary['successful']}/{fetch_summary['total_components']} successful")
        
        return fetch_summary
    
    def check_monitored_components(self, monitored_components: List[Dict], database) -> Dict:
        """
        Check defects for monitored components only (these will send notifications)
        Also stores in all_components_snapshots with is_monitored=True flag
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "soe_triage": None,
            "total_defects": 0,
            "total_untriaged": 0,
            "monitored_components": []
        }
        
        # Extract component names from monitored_components config
        component_names = [comp.get("name") for comp in monitored_components if comp.get("notify", True)]
        
        logger.info(f"🔍 Checking {len(component_names)} monitored components...")
        
        # Fetch defects for each monitored component
        for comp_config in monitored_components:
            component = comp_config.get("name")
            should_notify = comp_config.get("notify", True)
            
            if not component:
                logger.warning("⚠️  Skipping component with no name")
                continue
            
            if not should_notify:
                logger.info(f"⏭️  Skipping {component} (notify=false)")
                continue
            
            defects = self.fetch_defects_for_component(component)
            
            if defects is not None:
                parsed = self.parse_defects(defects, component)
                parsed["slack_channel"] = comp_config.get("slack_channel", "#defect-notifications")
                parsed["notify"] = should_notify
                
                results["components"][component] = parsed
                results["total_defects"] += parsed["total"]
                results["total_untriaged"] += parsed["untriaged"]
                results["monitored_components"].append(component)
                
                # Store in both tables
                database.store_daily_snapshot({"components": {component: parsed}})
                database.store_all_components_snapshot(component, parsed, is_monitored=True)
                
                logger.info(f"✅ {component}: {parsed['total']} defects ({parsed['untriaged']} untriaged)")
            else:
                logger.warning(f"❌ Failed to fetch {component}")
        
        # Fetch SOE Triage defects
        soe_defects = self.fetch_soe_triage_defects()
        if soe_defects is not None:
            results["soe_triage"] = {
                "total": len(soe_defects),
                "defects": soe_defects
            }
            results["total_defects"] += len(soe_defects)
            logger.info(f"✅ SOE Triage: {len(soe_defects)} overdue defects")
        
        logger.info(f"✅ Monitored check complete: {results['total_defects']} total defects, {results['total_untriaged']} untriaged")
        
        return results

# Made with Bob
