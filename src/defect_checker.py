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
    
    def fetch_defects_for_component(self, component: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """
        Fetch defects for a specific component from Build Break Report
        Implements retry logic with exponential backoff for network resilience
        Returns list of defects or None on error
        """
        import time
        
        for attempt in range(max_retries):
            try:
                session = self.authenticator.get_session()
                if not session:
                    logger.error(f"No valid session for fetching {component} defects")
                    return None
                
                if attempt > 0:
                    logger.info(f"🔄 Retry {attempt}/{max_retries-1} for {component}...")
                else:
                    logger.info(f"Fetching defects for component: {component}")
                
                # Build URL with component as query parameter
                api_url = f"{self.build_break_base_url}?fas={component}"
                
                # Increase timeout for retries
                timeout = 30 + (attempt * 15)  # 30s, 45s, 60s
                
                response = session.get(
                    api_url,
                    timeout=timeout,
                    headers={
                        'Accept': 'application/json',
                        'Cache-Control': 'no-cache'
                    },
                    verify=False  # Disable SSL verification for IBM self-signed certs
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch defects for {component}: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    return None
                
                defects = response.json()
                
                if not isinstance(defects, list):
                    logger.error(f"Unexpected response format for {component}")
                    return None
                
                # Debug: Log first defect structure to understand the data
                if defects and len(defects) > 0:
                    logger.info(f"DEBUG - Sample defect for {component}: {defects[0]}")
                
                logger.info(f"✅ Fetched {len(defects)} defects for {component}")
                return defects
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"⏱️ Timeout fetching {component} (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ All {max_retries} retries exhausted for {component}")
                    return None
            except Exception as e:
                logger.error(f"Error fetching defects for {component}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                return None
        
        return None
    
    def fetch_soe_triage_defects(self, monitored_components: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """
        Fetch overdue SOE Triage defects from Jazz/RTC
        Matches Chrome extension implementation
        Returns list of defects or None on error
        """
        try:
            session = self.authenticator.get_session()
            if not session:
                logger.error("No valid session for fetching SOE Triage defects")
                return None
            
            logger.info("Fetching SOE Triage defects from Jazz/RTC...")
            
            # Jazz/RTC saved query URL (matches Chrome extension)
            jazz_base_url = 'https://wasrtc.hursley.ibm.com:9443/jazz'
            query_id = '_fJ834OXIEemRB5enIPF1MQ'  # SOE Triage: Overdue Defects
            
            # Use OSLC Query API with inline properties
            query_url = f"{jazz_base_url}/oslc/queries/{query_id}/rtc_cm:results?oslc.select=*,rtc_cm:filedAgainst{{dcterms:title}}"
            
            logger.info(f"Fetching from: {query_url}")
            
            response = session.get(
                query_url,
                timeout=30,
                headers={
                    'Accept': 'application/json',
                    'OSLC-Core-Version': '2.0',
                    'Cache-Control': 'no-cache'
                },
                verify=False  # Disable SSL verification for IBM self-signed certs
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch SOE Triage defects: HTTP {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                return None
            
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                logger.error(f'Jazz/RTC returned non-JSON response (content-type: {content_type})')
                logger.error(f'Response preview: {response.text[:500]}')
                logger.warning('⚠️ Jazz/RTC authentication may have failed - returning empty list')
                return []  # Return empty list instead of None to continue with Build Break defects
            
            try:
                data = response.json()
            except Exception as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}")
                logger.error(f"Response preview: {response.text[:500]}")
                return []  # Return empty list to continue
            logger.info('✅ Jazz/RTC FRESH data received (cache: no-cache)')
            
            # Parse Jazz/RTC response
            defects = self._parse_jazz_workitems(data, monitored_components)
            
            logger.info(f"✅ Fetched {len(defects)} SOE Triage defects")
            return defects
            
        except Exception as e:
            logger.error(f"Error fetching SOE Triage defects: {e}")
            return None
    
    def _parse_jazz_workitems(self, data: Dict, monitored_components: Optional[List[str]] = None) -> List[Dict]:
        """
        Parse Jazz/RTC work items into standardized format
        Matches Chrome extension implementation with functional area resolution
        """
        defects = []
        
        try:
            # Jazz/RTC OSLC response structure
            results = data.get("oslc:results", data.get("results", []))
            if isinstance(data, list):
                results = data
            
            logger.info(f"Parsing {len(results)} Jazz/RTC work items...")
            
            # First pass: collect all functional area URLs that need to be resolved
            functional_area_urls = set()
            for item in results:
                functional_area_raw = item.get('rtc_ext:functional_area')
                if functional_area_raw and isinstance(functional_area_raw, dict):
                    resource_url = functional_area_raw.get('rdf:resource')
                    if resource_url:
                        functional_area_urls.add(resource_url)
            
            # Fetch all functional area labels
            logger.info(f"Resolving {len(functional_area_urls)} functional area URLs...")
            functional_area_map = {}
            session = self.authenticator.get_session()
            
            for url in functional_area_urls:
                try:
                    response = session.get(
                        url,
                        timeout=10,
                        headers={'Accept': 'application/json'},
                        verify=False
                    )
                    
                    if response.ok:
                        fa_data = response.json()
                        # The label is in dc:title (Dublin Core title)
                        label = (fa_data.get('dc:title') or
                                fa_data.get('dcterms:title') or
                                fa_data.get('rdfs:label') or
                                fa_data.get('oslc:label') or
                                fa_data.get('title') or
                                fa_data.get('label') or
                                fa_data.get('name') or
                                'Unknown')
                        functional_area_map[url] = label
                        logger.debug(f"✓ Resolved: {label}")
                except Exception as e:
                    logger.warning(f"Failed to resolve functional area {url}: {e}")
            
            # Second pass: process all work items with resolved functional areas
            for item in results:
                defect_id = item.get('dcterms:identifier', item.get('identifier', item.get('id', 'N/A')))
                summary = item.get('dcterms:title', item.get('title', item.get('summary', 'N/A')))
                description = item.get('dcterms:description', item.get('description', ''))
                
                # Functional Area - resolve from rdf:resource URL
                functional_area = 'N/A'
                functional_area_raw = item.get('rtc_ext:functional_area')
                if functional_area_raw:
                    if isinstance(functional_area_raw, dict) and functional_area_raw.get('rdf:resource'):
                        # Look up the resolved label
                        functional_area = functional_area_map.get(functional_area_raw['rdf:resource'], 'N/A')
                    elif isinstance(functional_area_raw, str):
                        functional_area = functional_area_raw
                
                # Filed Against (category/component) - with inline dcterms:title
                filed_against_raw = (item.get('rtc_cm:filedAgainst') or
                                    item.get('filedAgainst') or
                                    item.get('category'))
                filed_against = 'N/A'
                if isinstance(filed_against_raw, dict):
                    filed_against = (filed_against_raw.get('dcterms:title') or
                                   filed_against_raw.get('title') or
                                   filed_against_raw.get('name') or
                                   filed_against_raw.get('label') or
                                   'N/A')
                elif isinstance(filed_against_raw, str):
                    filed_against = filed_against_raw
                
                # Creation Date
                creation_date = item.get('dcterms:created', item.get('created', item.get('creationDate')))
                formatted_date = 'N/A'
                if creation_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
                        formatted_date = dt.strftime('%b %d, %Y')
                    except:
                        formatted_date = creation_date
                
                # Owner - can be object or string
                owner_raw = (item.get('rtc_cm:ownedBy') or
                           item.get('ownedBy') or
                           item.get('owner') or
                           item.get('dcterms:creator'))
                owned_by = 'Unassigned'
                if isinstance(owner_raw, dict):
                    owned_by = (owner_raw.get('title') or
                              owner_raw.get('name') or
                              owner_raw.get('label') or
                              'Unassigned')
                elif isinstance(owner_raw, str):
                    owned_by = owner_raw
                
                # Filter by monitored components if provided (matches Chrome extension logic)
                if monitored_components:
                    # Match by functionalArea field (case-insensitive)
                    matches_monitored = any(
                        monitored.lower() in functional_area.lower() or
                        functional_area.lower() in monitored.lower()
                        for monitored in monitored_components
                    )
                    
                    if not matches_monitored:
                        logger.debug(f"Skipping defect {defect_id}: functionalArea '{functional_area}' not in monitored components")
                        continue
                
                logger.debug(f"Defect {defect_id}: functionalArea='{functional_area}', filedAgainst='{filed_against}'")
                
                defects.append({
                    "id": defect_id,
                    "summary": summary,
                    "functionalArea": functional_area,
                    "filedAgainst": filed_against,
                    "creationDate": formatted_date,
                    "ownedBy": owned_by,
                    "description": description,
                    "source": "SOE_TRIAGE"
                })
                
        except Exception as e:
            logger.error(f"Error parsing Jazz work items: {e}")
        
        return defects
    
    def parse_defects(self, defects: List[Dict], component: str) -> Dict:
        """
        Parse and categorize defects - ONLY returns untriaged defects
        Matches the logic from defect-triaging-extension and IBM Build Break Report
        """
        untriaged_defects = []
        untriaged_count = 0
        test_bugs_count = 0
        product_bugs_count = 0
        infra_bugs_count = 0
        
        for defect in defects:
            # Get triage tags
            triage_tags = defect.get("triageTags", defect.get("tags", []))
            
            # Ensure it's an array
            if not isinstance(triage_tags, list):
                triage_tags = []
            
            # Convert all tags to lowercase strings for comparison
            tags_lower = [str(tag).lower().strip() for tag in triage_tags]
            
            # Check for specific triage tags with flexible matching
            # Match exact tags or tags containing the keywords
            has_test_bug = any(
                tag == 'test_bug' or tag == 'test' or
                'test_bug' in tag or 'testbug' in tag
                for tag in tags_lower
            )
            
            has_product_bug = any(
                tag == 'product_bug' or tag == 'product' or
                'product_bug' in tag or 'productbug' in tag
                for tag in tags_lower
            )
            
            has_infra_bug = any(
                tag == 'infrastructure_bug' or tag == 'infrastructure' or tag == 'infra' or
                'infrastructure_bug' in tag or 'infrastructurebug' in tag or
                'infra_bug' in tag or 'infrabug' in tag
                for tag in tags_lower
            )
            
            # A defect is untriaged if it does NOT have any of these specific tags
            has_triaged_tag = has_test_bug or has_product_bug or has_infra_bug
            
            is_untriaged = not has_triaged_tag
            
            if is_untriaged:
                # This is an untriaged defect - add it to our list
                untriaged_count += 1
                untriaged_defects.append({
                    "id": defect.get("id", "Unknown"),
                    "summary": defect.get("summary", "No summary"),
                    "owner": defect.get("owner", "Unassigned"),
                    "state": defect.get("state", "Unknown"),
                    "functionalArea": defect.get("functionalArea", "Unknown"),
                    "buildsReported": defect.get("buildsReported", []),
                    "triageTags": triage_tags,
                    "is_untriaged": True
                })
            else:
                # Categorize triaged defects by their tags (for statistics)
                # Priority order: infra_bug > test_bug > product_bug
                # This matches IBM Build Break Report categorization
                if has_infra_bug:
                    infra_bugs_count += 1
                elif has_test_bug:
                    test_bugs_count += 1
                elif has_product_bug:
                    product_bugs_count += 1
        
        result = {
            "component": component,
            "total": len(defects),  # Total defects from API
            "untriaged": untriaged_count,  # Count of untriaged
            "test_bugs": test_bugs_count,  # Count of triaged test bugs
            "product_bugs": product_bugs_count,  # Count of triaged product bugs
            "infra_bugs": infra_bugs_count,  # Count of triaged infra bugs
            "defects": untriaged_defects  # ONLY untriaged defects
        }
        
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
        Also fetches ALL SOE Triage defects (not filtered)
        Stores data in database but doesn't send notifications
        Returns summary of fetch operation
        """
        logger.info(f"🔄 Starting background fetch for {len(all_components)} components...")
        
        fetch_summary = {
            "timestamp": datetime.now().isoformat(),
            "total_components": len(all_components),
            "successful": 0,
            "failed": 0,
            "components_data": {},
            "soe_defects_count": 0
        }
        
        # Fetch Build Break Report defects for all components
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
        
        # Fetch ALL SOE Triage defects (not filtered by components) for dashboard
        logger.info("📋 Fetching ALL SOE Triage defects for dashboard...")
        try:
            # Authenticate with Jazz/RTC first
            if self.authenticator.authenticate_jazz_rtc():
                # Fetch without filtering (pass None for monitored_components)
                all_soe_defects = self.fetch_soe_triage_defects(monitored_components=None)
                if all_soe_defects:
                    fetch_summary["soe_defects_count"] = len(all_soe_defects)
                    
                    # Store SOE defects in database for dashboard
                    soe_data = {
                        "total": len(all_soe_defects),
                        "defects": all_soe_defects
                    }
                    
                    # Store in soe_snapshots table
                    date = datetime.now().strftime("%Y-%m-%d")
                    created_at = datetime.now().isoformat()
                    
                    import sqlite3
                    import json
                    conn = sqlite3.connect(database.db_path)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO soe_snapshots
                        (date, total, data, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (date, len(all_soe_defects), json.dumps(soe_data), created_at))
                    conn.commit()
                    conn.close()
                    
                    logger.info(f"✅ Fetched {len(all_soe_defects)} SOE Triage defects for dashboard")
                else:
                    logger.info("No SOE Triage defects found")
            else:
                logger.warning("⚠️ Jazz/RTC authentication failed, skipping SOE defects for dashboard")
        except Exception as e:
            logger.error(f"❌ Error fetching SOE defects for dashboard: {e}")
        
        logger.info(f"✅ Background fetch complete: {fetch_summary['successful']}/{fetch_summary['total_components']} successful")
        
        return fetch_summary
    
    def check_monitored_components(self, monitored_components: List[Dict], database) -> Dict:
        """
        Check defects for monitored components only (these will send notifications)
        Matches Chrome extension workflow:
        1. Fetch Build Break Report defects for monitored components
        2. Fetch SOE Triage defects (filtered by monitored components)
        3. Send single grouped Slack notification
        4. Store data for dashboard
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
        component_names = [comp.get("name") for comp in monitored_components if comp.get("notify", True) and comp.get("name")]
        
        logger.info(f"🔍 Checking {len(component_names)} monitored components...")
        
        # Step 1: Fetch defects for each monitored component from Build Break Report
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
        
        # Step 2: Authenticate with Jazz/RTC and fetch SOE Triage defects
        logger.info("📋 Authenticating with Jazz/RTC...")
        if self.authenticator.authenticate_jazz_rtc():
            logger.info("📋 Fetching SOE Triage defects...")
            soe_defects = self.fetch_soe_triage_defects(monitored_components=component_names)
        else:
            logger.warning("⚠️ Jazz/RTC authentication failed, skipping SOE defects")
            soe_defects = []
        
        if soe_defects is not None:
            # Filter SOE defects to only include monitored components (double-check)
            filtered_soe = [
                defect for defect in soe_defects
                if any(
                    (monitored and monitored.lower() in defect.get('functionalArea', '').lower()) or
                    (monitored and defect.get('functionalArea', '').lower() in monitored.lower())
                    for monitored in component_names
                )
            ]
            
            results["soe_triage"] = {
                "total": len(filtered_soe),
                "defects": filtered_soe,
                "all_defects": len(soe_defects)  # Total before filtering
            }
            results["total_defects"] += len(filtered_soe)
            
            logger.info(f"✅ SOE Triage: {len(filtered_soe)} overdue defects (filtered from {len(soe_defects)} total)")
        else:
            logger.warning("⚠️ Failed to fetch SOE Triage defects")
        
        logger.info(f"✅ Monitored check complete: {results['total_defects']} total defects, {results['total_untriaged']} untriaged")
        
        return results

# Made with Bob
