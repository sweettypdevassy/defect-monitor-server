"""
Defect Checker Module
Fetches and processes defects from IBM Build Break Report and SOE Triage
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from ml_tag_suggester import MLTagSuggester
from cookie_monitor import get_cookie_monitor
from duplicate_detector import DuplicateDetector
from fetch_checkpoint import FetchCheckpoint

logger = logging.getLogger(__name__)


class DefectChecker:
    """Handles fetching and processing defects from IBM systems"""
    
    def __init__(self, authenticator, database=None):
        self.authenticator = authenticator
        self.database = database
        self.build_break_base_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas"
        self.soe_triage_url = "https://wasrtc.hursley.ibm.com:9443/jazz/oslc/workitems.json"
        self.tag_suggester = MLTagSuggester()
        
        # ML model status logged only if not trained
        ml_stats = self.tag_suggester.get_training_stats()
        if not ml_stats.get('trained'):
            logger.warning("⚠️  ML model not trained. Run: docker-compose exec defect-monitor python3 retrain_model.sh")
        
        # Lower threshold to 0.85 for summary-only matching (was 0.7)
        # Since we only have summaries, we need high similarity to avoid false positives
        self.duplicate_detector = DuplicateDetector(similarity_threshold=0.80)
    
    @property
    def suggester_trained(self):
        """Check if ML suggester is trained"""
        return self.tag_suggester.trained
    
    def fetch_defects_for_component(self, component: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """
        Fetch defects for a specific component from Build Break Report
        Implements retry logic with exponential backoff for network resilience
        Returns list of defects or None on error
        """
        import time
        
        # Track if we just re-authenticated to avoid immediate re-check
        just_authenticated = False
        
        for attempt in range(max_retries):
            try:
                session = self.authenticator.get_session()
                if not session:
                    logger.error(f"No valid session for fetching {component} defects")
                    return None
                
                if attempt > 0:
                    logger.warning(f"🔄 Retry {attempt}/{max_retries-1} for {component}")
                
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
                
                # Check for authentication failure and re-authenticate
                # Skip check if we just authenticated (avoid immediate re-auth loop)
                cookie_monitor = get_cookie_monitor()
                if not just_authenticated and cookie_monitor.detect_cookie_expiration(response):
                    logger.warning(f"🔴 Authentication failure for {component}, re-authenticating...")
                    
                    # Force re-authentication
                    if self.authenticator.authenticate():
                        time.sleep(3)  # Wait for cookies to propagate
                        # Get new session
                        session = self.authenticator.get_session()
                        if session:
                            just_authenticated = True  # Mark that we just authenticated
                            continue  # Retry with new session
                    else:
                        logger.error("❌ Re-authentication failed")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        return None
                elif just_authenticated and cookie_monitor.detect_cookie_expiration(response):
                    # If we just authenticated and still getting 401, it's likely a slow API response
                    # Log but don't re-authenticate immediately
                    logger.warning(f"⚠️  Got 401 right after re-auth for {component} - likely slow API, continuing...")
                    just_authenticated = False  # Reset flag
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch defects for {component}: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
                
                defects = response.json()
                
                if not isinstance(defects, list):
                    logger.error(f"Unexpected response format for {component}")
                    return None
                
                # Extract creation_date and number_builds from reported_builds for each defect
                for defect in defects:
                    reported_builds = defect.get('reported_builds', '')
                    if reported_builds:
                        creation_date = self.extract_creation_date_from_builds(reported_builds)
                        defect['creation_date'] = creation_date
                        # Count number of builds (comma-separated list)
                        defect['number_builds'] = len([b.strip() for b in reported_builds.split(',') if b.strip()])
                    else:
                        defect['creation_date'] = ''
                        defect['number_builds'] = 0
                
                # Debug: Log first defect structure to understand the data
                return defects
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"⏱️ Timeout fetching {component} (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"❌ All {max_retries} retries exhausted for {component}")
                    return None
            except Exception as e:
                logger.error(f"Error fetching defects for {component}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def extract_creation_date_from_builds(self, reported_builds: str) -> str:
        """
        Extract creation date from the first build in reported_builds string.
        Example: "[Liberty z/OS Platform Build 20231208-1940, ...]" -> "2023-12-08"
        Example: "[No longer available was:2026-02-12 22:09 ...]" -> "2026-02-12"
        """
        import re
        from datetime import datetime
        
        if not reported_builds:
            return ''
        
        # First try to match YYYY-MM-DD format (with hyphens)
        match = re.search(r'(\d{4}-\d{2}-\d{2})', reported_builds)
        if match:
            date_str = match.group(1)
            try:
                # Validate it's a real date
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                pass
        
        # Fall back to YYYYMMDD format (8 consecutive digits)
        match = re.search(r'(\d{8})', reported_builds)
        if match:
            date_str = match.group(1)
            try:
                # Parse YYYYMMDD format
                dt = datetime.strptime(date_str, '%Y%m%d')
                # Return in ISO format
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                pass
        
        return ''
    
    def is_defect_cancelled(self, state_url: str) -> bool:
        """
        Check if defect state URL indicates cancelled/closed/resolved
        
        Args:
            state_url: The state URL from Jazz/RTC API
            
        Returns:
            True if defect is cancelled/closed/resolved, False otherwise
        """
        if not state_url:
            return False
        
        # Only check if it's a valid RTC state URL
        # This prevents false positives from error messages or empty states
        if 'jazz/oslc/workflows' not in state_url:
            return False
        
        state_lower = state_url.lower()
        return any(keyword in state_lower for keyword in ['canceled', 'cancelled', 'closed', 'resolved'])
    
    def fetch_defect_details(self, defect_id: str, max_retries: int = 2) -> Dict:
        """
        Fetch complete details for a specific defect from Jazz/RTC with retry logic
        
        Args:
            defect_id: The defect ID
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with defect details including description and creation date
        """
        for attempt in range(max_retries):
            try:
                # Get session and authenticate with Jazz/RTC if needed
                session = self.authenticator.get_session()
                if not session:
                    return {}
                
                # Authenticate with Jazz/RTC (uses same session)
                if not self.authenticator.authenticate_jazz_rtc():
                    logger.warning(f"Jazz/RTC authentication failed for defect {defect_id}")
                    return {}
                
                # Jazz/RTC work item URL
                jazz_url = f"https://wasrtc.hursley.ibm.com:9443/jazz/oslc/workitems/{defect_id}.json"
                
                # Increase timeout to 30 seconds
                response = session.get(
                    jazz_url,
                    timeout=60,  # Increased to 60 seconds for slow defects
                    headers={'Accept': 'application/json'},
                    verify=False
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract fields using correct Jazz/RTC field names
                    # Based on actual API response: dc:created, dc:description, dc:modified, dc:creator
                    created = data.get('dc:created', '')
                    description = str(data.get('dc:description', ''))
                    modified = data.get('dc:modified', '')
                    
                    # Creator is a nested object with rdf:resource
                    creator_obj = data.get('dc:creator', {})
                    creator = creator_obj.get('rdf:resource', '') if isinstance(creator_obj, dict) else ''
                    
                    # State is nested under rtc_cm:state
                    state_obj = data.get('rtc_cm:state', {})
                    state = state_obj.get('rdf:resource', '') if isinstance(state_obj, dict) else ''
                    
                    # Extract tags from dc:subject field
                    # Tags are stored as a string (e.g., "infrastructure", "test", "product")
                    # Convert to list format for consistency with the rest of the system
                    tags = []
                    subject = data.get('dc:subject', '')
                    if subject:
                        # If it's already a list, use it
                        if isinstance(subject, list):
                            tags = subject
                        # If it's a string, convert to list
                        elif isinstance(subject, str):
                            tags = [subject]
                    
                    # Check if defect is cancelled
                    is_cancelled = self.is_defect_cancelled(state)
                    
                    # Log success with cancelled indicator
                    if description or created:
                        if is_cancelled:
                            logger.info(f"🚫 CANCELLED Fetched details for {defect_id}: desc={len(description)} chars, created={created[:10] if created else 'N/A'}, tags={tags}")
                        else:
                            logger.info(f"✅ Fetched details for {defect_id}: desc={len(description)} chars, created={created[:10] if created else 'N/A'}, tags={tags}")
                    else:
                        logger.warning(f"⚠️  Defect {defect_id}: API returned 200 but no description/created")
                    
                    return {
                        'description': description,
                        'created': created,
                        'modified': modified,
                        'creator': creator,
                        'state': state,
                        'is_cancelled': is_cancelled,
                        'tags': tags
                    }
                else:
                    logger.warning(f"⚠️  Failed to fetch {defect_id}: HTTP {response.status_code}")
                
                return {}
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                    logger.debug(f"Timeout fetching details for {defect_id}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.debug(f"Could not fetch details for defect {defect_id}: Timeout after {max_retries} attempts")
                    return {}
            except Exception as e:
                logger.debug(f"Could not fetch details for defect {defect_id}: {e}")
                return {}
        
        return {}
    
    def fetch_defect_description(self, defect_id: str, max_retries: int = 2) -> str:
        """
        Fetch description for a specific defect from Jazz/RTC with retry logic
        (Backward compatibility wrapper)
        
        Args:
            defect_id: The defect ID
            max_retries: Maximum number of retry attempts
            
        Returns:
            Description text or empty string if not found
        """
        details = self.fetch_defect_details(defect_id, max_retries)
        return details.get('description', '')
    
    def fetch_details_parallel(self, defect_ids: List[str], max_workers: int = 5) -> Dict[str, Dict]:
        """
        Fetch full details (description + creation date) for multiple defects in parallel
        
        Args:
            defect_ids: List of defect IDs
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary mapping defect_id to details dict
        """
        details_map = {}
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_id = {
                    executor.submit(self.fetch_defect_details, defect_id): defect_id
                    for defect_id in defect_ids
                }
                
                # Process completed tasks with timeout
                completed = 0
                total = len(defect_ids)
                
                # Use as_completed with timeout to prevent infinite waiting
                # Timeout = 600 seconds (10 minutes) to fetch all defects
                try:
                    for future in as_completed(future_to_id, timeout=600):
                        defect_id = future_to_id[future]
                        try:
                            details = future.result(timeout=5)  # Additional safety timeout
                            details_map[defect_id] = details
                            completed += 1
                            
                            # Log progress every 100 defects
                            if completed % 100 == 0 or completed == total:
                                logger.info(f"📥 Fetched {completed}/{total} defect details...")
                                
                        except Exception as e:
                            logger.debug(f"Error fetching details for {defect_id}: {e}")
                            details_map[defect_id] = {}
                            completed += 1
                            
                except TimeoutError:
                    logger.warning(f"⚠️  Timeout waiting for defect details. Fetched {completed}/{total} defects.")
                    # Cancel remaining futures
                    for future in future_to_id:
                        if not future.done():
                            future.cancel()
                            defect_id = future_to_id[future]
                            logger.debug(f"Cancelled fetch for {defect_id}")
                            details_map[defect_id] = {}
        except RuntimeError as e:
            if "cannot schedule new futures after interpreter shutdown" in str(e):
                logger.warning("⚠️  Interpreter shutting down, skipping parallel fetch")
                # Fall back to sequential fetch
                for defect_id in defect_ids:
                    try:
                        details = self.fetch_defect_details(defect_id)
                        if details:
                            details_map[defect_id] = details
                    except Exception as ex:
                        logger.warning(f"Failed to fetch details for defect {defect_id}: {ex}")
            else:
                raise
        
        return details_map
    
    def fetch_descriptions_parallel(self, defect_ids: List[str], max_workers: int = 5) -> Dict[str, str]:
        """
        Fetch descriptions for multiple defects in parallel (backward compatibility)
        
        Args:
            defect_ids: List of defect IDs
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary mapping defect_id to description
        """
        details_map = self.fetch_details_parallel(defect_ids, max_workers)
        return {defect_id: details.get('description', '') for defect_id, details in details_map.items()}
    
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
            
            
            # Jazz/RTC saved query URL (matches Chrome extension)
            jazz_base_url = 'https://wasrtc.hursley.ibm.com:9443/jazz'
            query_id = '_fJ834OXIEemRB5enIPF1MQ'  # SOE Triage: Overdue Defects
            
            # Use OSLC Query API with inline properties
            query_url = f"{jazz_base_url}/oslc/queries/{query_id}/rtc_cm:results?oslc.select=*,rtc_cm:filedAgainst{{dcterms:title}}"
            
            
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
                
                # Extract tags from dc:subject field
                tags_raw = item.get('dc:subject', item.get('dcterms:subject', item.get('tags', [])))
                tags = []
                if isinstance(tags_raw, list):
                    tags = [str(tag).strip() for tag in tags_raw if tag]
                elif isinstance(tags_raw, str):
                    # Single tag as string
                    tags = [tags_raw.strip()] if tags_raw.strip() else []
                
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
                    "tags": tags,  # Add tags for triage detection
                    "triageTags": tags,  # Also add as triageTags for compatibility
                    "source": "SOE_TRIAGE"
                })
                
        except Exception as e:
            logger.error(f"Error parsing Jazz work items: {e}")
        
        return defects
    
    def parse_defects(self, defects: List[Dict], component: str, collect_triaged: bool = False) -> Dict:
        """
        Parse and categorize defects - ONLY returns untriaged defects
        Matches the logic from defect-triaging-extension and IBM Build Break Report
        Also checks for duplicates within the component
        Filters out cancelled/closed/resolved defects
        
        Args:
            defects: List of defects from API
            component: Component name
            collect_triaged: If True, also collect triaged defects for training
        """
        untriaged_defects = []
        triaged_defects = []
        all_defects_for_dup_check = []  # All defects for duplicate detection
        untriaged_count = 0
        test_bugs_count = 0
        product_bugs_count = 0
        infra_bugs_count = 0
        cancelled_count = 0
        
        for defect in defects:
            # Check if defect is cancelled/closed/resolved
            state = defect.get("state", "")
            is_cancelled = self.is_defect_cancelled(state)
            
            if is_cancelled:
                cancelled_count += 1
                defect_id = defect.get('id', 'unknown')
                logger.info(f"🚫 Filtering cancelled defect {defect_id} from {component} (state: {state.split('.')[-1] if '.' in state else state})")
                
                # Check if cancelled defect has tags - if so, keep it for duplicate detection
                triage_tags = defect.get("triageTags", defect.get("tags", []))
                if isinstance(triage_tags, list) and triage_tags:
                    # Has tags - add to duplicate detection pool so other defects can inherit its tags
                    all_defects_for_dup_check.append(defect)
                    logger.info(f"   💾 Keeping cancelled defect {defect_id} for duplicate detection (has tags: {triage_tags})")
                
                continue  # Skip cancelled defects from counts - will reappear if reopened
            
            # Store all active defects for duplicate checking
            all_defects_for_dup_check.append(defect)
            
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
                
                # Store triaged defects for training (if requested)
                if collect_triaged:
                    triaged_defects.append({
                        "id": defect.get("id", "Unknown"),
                        "summary": defect.get("summary", "No summary"),
                        "description": defect.get("description", ""),
                        "functionalArea": defect.get("functionalArea", "Unknown"),
                        "state": defect.get("state", "Unknown"),
                        "owner": defect.get("owner", "Unassigned"),
                        "triageTags": triage_tags,
                        "component": component  # Add component for caching
                    })
        
        # If we're just collecting triaged defects for training, skip untriaged processing
        if collect_triaged:
            return {
                "untriaged_defects": [],
                "triaged_defects": triaged_defects,
                "stats": {
                    "total": len(defects),
                    "untriaged": 0,
                    "test_bugs": test_bugs_count,
                    "product_bugs": product_bugs_count,
                    "infra_bugs": infra_bugs_count
                }
            }
        
        # SMART DAILY OPERATION: Use cache + fetch only NEW defects
        # Most defects are cached from weekly ML training (Thursday 12:17 PM)
        # Only fetch descriptions for NEW defects (typically 5-10 per day)
        logger.debug(f"📋 Component {component}: {len(all_defects_for_dup_check)} total defects, {len(untriaged_defects)} untriaged")
        
        if all_defects_for_dup_check and self.database:
            # Collect all defect IDs from current API fetch
            all_ids = [str(d.get('id')) for d in all_defects_for_dup_check if d.get('id')]
            
            # Get ALL cached defects for this component INCLUDING cancelled ones
            # (we need cancelled defects to detect which ones were removed from API)
            all_cached_for_component = self.database.get_all_cached_descriptions_for_component(component, include_cancelled=True)
            all_cached_ids = {str(d.get('id')) for d in all_cached_for_component}
            
            # Find defects that are in cache but NOT in current API response
            # These are likely cancelled/closed defects that no longer appear in Build Break Report
            removed_ids = all_cached_ids - set(all_ids)
            if removed_ids:
                logger.info(f"🔍 Found {len(removed_ids)} defects in cache but not in API (likely cancelled): {removed_ids}")
                
                # Only delete UNTRIAGED defects (no ML tags)
                # Keep TRIAGED defects for ML training even if cancelled
                untriaged_to_delete = []
                triaged_to_keep = []
                
                for defect in all_cached_for_component:
                    defect_id = str(defect.get('id'))
                    if defect_id in removed_ids:
                        tags = defect.get('triageTags', [])
                        # Check if defect has ML tags (test_bug, product_bug, infrastructure_bug)
                        has_ml_tags = any(
                            any(keyword in str(tag).lower() for keyword in ['test', 'product', 'infra', 'infrastructure'])
                            for tag in tags
                        )
                        
                        if has_ml_tags:
                            triaged_to_keep.append(defect_id)
                        else:
                            untriaged_to_delete.append(defect_id)
                
                # Delete only untriaged defects
                if untriaged_to_delete:
                    self.database.delete_cached_descriptions(untriaged_to_delete)
                    logger.info(f"🗑️  Deleted {len(untriaged_to_delete)} untriaged cancelled defects from cache")
                
                # Add triaged cancelled defects to duplicate detection pool
                # This allows new defects to inherit tags from cancelled duplicates
                if triaged_to_keep:
                    logger.info(f"💾 Kept {len(triaged_to_keep)} triaged cancelled defects for ML training: {triaged_to_keep}")
                    logger.info(f"🔄 Adding {len(triaged_to_keep)} cancelled defects to duplicate detection pool...")
                    
                    # Add cancelled defects with tags to all_defects_for_dup_check
                    for defect in all_cached_for_component:
                        defect_id = str(defect.get('id'))
                        if defect_id in triaged_to_keep:
                            # Add to duplicate detection pool
                            all_defects_for_dup_check.append(defect)
                            logger.info(f"   💾 Added cancelled defect {defect_id} for duplicate detection (tags: {defect.get('triageTags', [])})")
                    
                    # Fetch current state from Jazz/RTC for these defects
                    for defect_id in triaged_to_keep:
                        try:
                            details = self.fetch_defect_details(defect_id)
                            if details:
                                state = details.get('state', '')
                                # Update the cached defect's state
                                self.database.update_defect_state(defect_id, state)
                                logger.debug(f"Updated state for defect {defect_id}")
                        except Exception as e:
                            logger.warning(f"Failed to update state for defect {defect_id}: {e}")
            
            # ALWAYS add ALL cached defects to duplicate detection pool (across ALL components)
            # This ensures defects can find duplicates even if they were filed under different components
            logger.info(f"🔄 Querying ALL cached defects across ALL components for duplicate detection...")
            all_cached_defects = self.database.get_all_cancelled_defects_with_tags()
            
            # Track defects with empty tags that need to be fetched from IBM RTC
            ids_to_fetch_tags = []
            
            if all_cached_defects:
                logger.info(f"💾 Found {len(all_cached_defects)} cached defects across all components")
                added_count = 0
                for defect in all_cached_defects:
                    defect_id = str(defect.get('id'))
                    # Skip if already in current API response
                    if defect_id in all_ids:
                        continue
                    # Only add if not already in the pool
                    if not any(str(d.get('id')) == defect_id for d in all_defects_for_dup_check):
                        all_defects_for_dup_check.append(defect)
                        added_count += 1
                        tags = defect.get('triageTags', [])
                        
                        # If defect has empty tags, fetch from IBM RTC
                        if not tags:
                            ids_to_fetch_tags.append(defect_id)
                            logger.info(f"   💾 Added cached defect {defect_id} from {defect.get('component', 'Unknown')} (will fetch tags)")
                        else:
                            logger.info(f"   💾 Added cached defect {defect_id} from {defect.get('component', 'Unknown')} (tags: {tags})")
                
                logger.info(f"✅ Added {added_count} cached defects to duplicate detection pool")
                
                # Fetch tags for defects with empty tags
                if ids_to_fetch_tags:
                    logger.info(f"📥 Fetching tags for {len(ids_to_fetch_tags)} cached defects from IBM RTC...")
                    fetched_details = self.fetch_details_parallel(ids_to_fetch_tags, max_workers=3)
                    
                    # Update defects in the pool with fresh tags AND state
                    for defect_id, details in fetched_details.items():
                        tags = details.get('tags', [])
                        state = details.get('state', '')
                        
                        # Find and update the defect in the pool
                        for defect in all_defects_for_dup_check:
                            if str(defect.get('id')) == defect_id:
                                # Update tags in the pool
                                if tags:
                                    defect['triageTags'] = tags
                                    logger.info(f"   ✅ Updated cached defect {defect_id} with tags from IBM RTC: {tags}")
                                
                                # Update state in the pool
                                if state:
                                    defect['state'] = state
                                
                                # Update in database cache (both tags and state)
                                try:
                                    if tags:
                                        self.database.update_defect_tags(defect_id, tags)
                                    if state:
                                        self.database.update_defect_state(defect_id, state)
                                    logger.info(f"   💾 Updated database for cached defect {defect_id}")
                                except Exception as e:
                                    logger.warning(f"Failed to update database for {defect_id}: {e}")
                                break
            
            # Check cache first (only for defects in current API response)
            logger.info(f"🔍 Checking cache for {len(all_ids)} defect descriptions...")
            cached_descriptions = self.database.get_cached_descriptions(all_ids)
            
            # Identify NEW defects (not in cache) OR defects with empty tags that need tag refresh
            ids_to_fetch = []
            for id in all_ids:
                if id not in cached_descriptions:
                    # New defect - fetch everything
                    logger.debug(f"   📥 Will fetch {id}: NEW defect (not in cache)")
                    ids_to_fetch.append(id)
                else:
                    # Existing defect - check if it has tags
                    cached_tags = cached_descriptions[id].get('triageTags', [])
                    if not cached_tags:
                        # No tags in cache - might have been added in IBM RTC, fetch to get tags
                        logger.info(f"   🔄 Will fetch {id}: Has empty tags in cache, checking IBM RTC for updates")
                        ids_to_fetch.append(id)
                    else:
                        logger.debug(f"   ✓ Skipping {id}: Has tags in cache: {cached_tags}")
            
            if cached_descriptions:
                logger.info(f"✅ Found {len(cached_descriptions)} cached descriptions")
            else:
                logger.warning(f"⚠️  No cached descriptions found for any of the {len(all_ids)} defects!")
            
            # Fetch descriptions for NEW defects only (fast - typically 5-10 defects)
            newly_fetched_details = {}
            if ids_to_fetch:
                logger.info(f"📥 Fetching descriptions for {len(ids_to_fetch)} NEW defects...")
                newly_fetched_details = self.fetch_details_parallel(ids_to_fetch, max_workers=3)
                
                # Cache the newly fetched details
                if newly_fetched_details:
                    defects_to_cache = []
                    cancelled_count = 0
                    for defect_id, details in newly_fetched_details.items():
                        description = details.get('description', '')
                        creation_date = details.get('created', '')
                        state = details.get('state', '')
                        is_cancelled = details.get('is_cancelled', False)
                        tags = details.get('tags', [])  # Get tags from IBM RTC API
                        
                        # Track cancelled defects
                        if is_cancelled:
                            cancelled_count += 1
                        
                        # Only cache if we got actual data
                        if description or creation_date:
                            # Find the defect to get full info
                            defect_info = next((d for d in all_defects_for_dup_check if str(d.get('id')) == defect_id), None)
                            if defect_info:
                                defect_info['description'] = description
                                defect_info['creation_date'] = creation_date
                                defect_info['state'] = state
                                defect_info['is_cancelled'] = is_cancelled
                                defect_info['component'] = component
                                # Use tags from IBM RTC API if available, otherwise keep existing tags
                                if tags:
                                    defect_info['triageTags'] = tags
                                defects_to_cache.append(defect_info)
                    
                    if defects_to_cache:
                        self.database.cache_defect_descriptions(defects_to_cache)
                        if cancelled_count > 0:
                            logger.info(f"✅ Cached {len(defects_to_cache)} new defects ({cancelled_count} cancelled)")
                        else:
                            logger.info(f"✅ Cached {len(defects_to_cache)} new defects")
            
            # Update cached defects with fresh state AND tags from IBM API
            # This ensures both state changes and tag changes are reflected
            # Tags come from IBM RTC API (fetched above), so they are authoritative
            defects_to_update_state = []
            for defect in all_defects_for_dup_check:
                defect_id = str(defect.get('id'))
                if defect_id in cached_descriptions:
                    # Defect is in cache, update its state AND tags with fresh data from API
                    cached_desc = cached_descriptions[defect_id]
                    api_tags = defect.get('triageTags', [])
                    
                    # ALWAYS use tags from API - they are authoritative from IBM RTC
                    # If API returns empty tags, the tag was removed in IBM RTC
                    defect_to_update = {
                        'id': defect_id,
                        'description': cached_desc.get('description', ''),
                        'summary': defect.get('summary', ''),
                        'component': component,
                        'functionalArea': defect.get('functionalArea', ''),
                        'state': defect.get('state', ''),  # Fresh state from API
                        'triageTags': api_tags,  # ALWAYS use fresh tags from API
                        'creation_date': cached_desc.get('creation_date', '')
                    }
                    defects_to_update_state.append(defect_to_update)
            
            if defects_to_update_state:
                self.database.cache_defect_descriptions(defects_to_update_state)
                logger.info(f"🔄 Updated state and tags for {len(defects_to_update_state)} cached defects with fresh data from API")
            
            # IMPORTANT: Update tags in all_defects_for_dup_check with freshly fetched tags
            # This ensures duplicate detection uses the most up-to-date tag information
            logger.info(f"🔄 Updating tags in duplicate detection pool with freshly fetched data...")
            for defect in all_defects_for_dup_check:
                defect_id = str(defect.get('id'))
                if defect_id in newly_fetched_details:
                    # Update with freshly fetched tags from IBM RTC (stored as 'tags' in newly_fetched_details)
                    fresh_tags = newly_fetched_details[defect_id].get('tags', [])
                    defect['triageTags'] = fresh_tags
                    logger.info(f"   ✅ Updated {defect_id} in dup pool with fresh tags: {fresh_tags}")
            
            # Combine cached and newly fetched descriptions
            all_descriptions = {**cached_descriptions}
            for defect_id, details in newly_fetched_details.items():
                all_descriptions[defect_id] = {
                    'description': details.get('description', ''),
                    'creation_date': details.get('created', '')
                }
            
            logger.info(f"📋 Total descriptions available: {len(all_descriptions)} for {len(all_ids)} defects")
            
            # Apply descriptions to untriaged defects
            for defect in untriaged_defects:
                defect_id = str(defect.get('id'))
                if defect_id in all_descriptions:
                    desc_data = all_descriptions[defect_id]
                    if isinstance(desc_data, dict):
                        defect['description'] = desc_data.get('description', '')
                        defect['creation_date'] = desc_data.get('creation_date', '')
                    else:
                        defect['description'] = desc_data
                else:
                    logger.warning(f"⚠️  No description found for untriaged defect {defect_id}")
                    defect['description'] = ''
            
            # Apply descriptions to all defects for duplicate checking
            # NOTE: We do NOT restore cached tags here - we want fresh tags from IBM API
            # Cached tags are only used for cancelled defects (added to duplicate pool above)
            for defect in all_defects_for_dup_check:
                defect_id = str(defect.get('id'))
                if defect_id in all_descriptions:
                    desc_data = all_descriptions[defect_id]
                    if isinstance(desc_data, dict):
                        defect['description'] = desc_data.get('description', '')
                        defect['creation_date'] = desc_data.get('creation_date', '')
                        # DO NOT restore cached tags - use fresh tags from API
                        # This ensures defects reflect current state in IBM RTC
                    else:
                        defect['description'] = desc_data
            
            # DON'T update cache here - it will overwrite descriptions with empty data from IBM API
            # Cache updates should only happen when we fetch NEW descriptions above
        
        # Get previous snapshot to preserve existing suggested tags
        previous_snapshot = None
        previous_defects_map = {}
        if self.database:
            try:
                previous_snapshot = self.database.get_latest_snapshot_for_component(component)
                if previous_snapshot and 'defects' in previous_snapshot:
                    for prev_defect in previous_snapshot['defects']:
                        defect_id = str(prev_defect.get('id'))
                        previous_defects_map[defect_id] = prev_defect
            except Exception as e:
                logger.debug(f"Could not load previous snapshot: {e}")
        
        # Process untriaged defects with ML suggestions and duplicate detection
        for defect in untriaged_defects:
                defect_id = str(defect.get('id'))
                
                # Check if defect already has a suggested tag from previous run
                # Preserve ONLY duplicate-based tags (not pure ML predictions)
                # This allows ML model improvements to benefit existing defects
                if defect_id in previous_defects_map:
                    prev_defect = previous_defects_map[defect_id]
                    prev_duplicate_info = prev_defect.get('duplicate_info', {})
                    prev_duplicate_id = str(prev_duplicate_info.get('duplicate_id', '')) if prev_duplicate_info else ''
                    
                    # Only preserve if tag was based on a duplicate (not pure ML prediction)
                    if prev_duplicate_id and prev_defect.get('suggested_tag') and prev_defect.get('suggested_tag') != 'unknown':
                        # Check if the previous duplicate still exists in all_defects_for_dup_check
                        duplicate_still_exists = any(str(d.get('id')) == prev_duplicate_id for d in all_defects_for_dup_check)
                        
                        if duplicate_still_exists:
                            # Preserve duplicate-based tag (stable, based on human triage)
                            defect["suggested_tag"] = prev_defect.get('suggested_tag')
                            defect["suggestion_confidence"] = prev_defect.get('suggestion_confidence', 0.0)
                            defect["suggestion_reasoning"] = prev_defect.get('suggestion_reasoning', 'Preserved from previous run')
                            defect["duplicate_info"] = prev_defect.get('duplicate_info')
                            
                            logger.info(f"   💾 Preserved duplicate-based tag for {defect_id}: {defect['suggested_tag']} (duplicate #{prev_duplicate_id})")
                            continue  # Skip recalculation
                        else:
                            logger.info(f"   🔄 Duplicate #{prev_duplicate_id} no longer exists for {defect_id}, recalculating tag...")
                    else:
                        # Pure ML prediction - allow re-prediction to benefit from model improvements
                        logger.debug(f"   🔄 Defect {defect_id} has pure ML prediction, will re-predict with updated model")
                
                # Check for duplicates FIRST
                duplicate_info = self.duplicate_detector.check_defect_for_duplicates(
                    defect,
                    all_defects_for_dup_check
                )
                
                if duplicate_info:
                    defect["duplicate_info"] = duplicate_info
                    duplicate_id = str(duplicate_info['duplicate_id'])
                    logger.info(f"   🔄 Defect {defect.get('id')} may be duplicate of {duplicate_id} ({duplicate_info['similarity']:.0%} similar)")
                    
                    # Get duplicate's tags - if empty, fetch from IBM RTC
                    duplicate_tags = duplicate_info.get('duplicate_tags', [])
                    
                    # If duplicate has empty tags, fetch from IBM RTC to get authoritative tags
                    if not duplicate_tags:
                        logger.info(f"   📥 Duplicate #{duplicate_id} has empty tags, fetching from IBM RTC...")
                        try:
                            fetched_details = self.fetch_details_parallel([duplicate_id], max_workers=1)
                            if duplicate_id in fetched_details:
                                fresh_tags = fetched_details[duplicate_id].get('tags', [])
                                duplicate_tags = fresh_tags
                                logger.info(f"   ✅ Fetched tags for duplicate #{duplicate_id}: {fresh_tags}")
                                
                                # Update the duplicate in the pool with fresh tags
                                for dup_defect in all_defects_for_dup_check:
                                    if str(dup_defect.get('id')) == duplicate_id:
                                        dup_defect['triageTags'] = fresh_tags
                                        logger.info(f"   ✅ Updated duplicate #{duplicate_id} in pool with fresh tags")
                                        break
                        except Exception as e:
                            logger.warning(f"   ⚠️  Failed to fetch tags for duplicate #{duplicate_id}: {e}")
                    
                    # Use duplicate's tags if they are valid ML tags, otherwise use ML prediction
                    has_valid_ml_tag = False
                    suggested_tag = None
                    
                    if duplicate_tags:
                        # Determine primary tag from duplicate
                        tags_lower = [str(tag).lower().strip() for tag in duplicate_tags]
                        logger.info(f"   🔍 Checking duplicate tags: {duplicate_tags} -> lowercase: {tags_lower}")
                        
                        # Priority: infrastructure > test > product
                        if any('infra' in tag or 'infrastructure' in tag for tag in tags_lower):
                            suggested_tag = 'infrastructure_bug'
                            has_valid_ml_tag = True
                            logger.info(f"   ✅ Found infrastructure tag in: {tags_lower}")
                        elif any('test' in tag for tag in tags_lower):
                            suggested_tag = 'test_bug'
                            has_valid_ml_tag = True
                            logger.info(f"   ✅ Found test tag in: {tags_lower}")
                        elif any('product' in tag for tag in tags_lower):
                            suggested_tag = 'product_bug'
                            has_valid_ml_tag = True
                            logger.info(f"   ✅ Found product tag in: {tags_lower}")
                        else:
                            logger.warning(f"   ⚠️  No ML tags found in: {tags_lower}")
                    
                    if has_valid_ml_tag:
                        # Duplicate has valid ML tag - use it
                        defect["suggested_tag"] = suggested_tag
                        defect["suggestion_confidence"] = duplicate_info['similarity']
                        defect["suggestion_reasoning"] = f"Based on duplicate defect #{duplicate_info['duplicate_id']} with tags: {duplicate_tags}"
                        logger.info(f"   ✓ Using duplicate's tag: {suggested_tag}")
                    else:
                        # Duplicate has no valid ML tags (e.g., 'triaging', 'no_logs_available') - use ML prediction
                        if self.suggester_trained:
                            suggested_tag, confidence, reasoning = self.tag_suggester.suggest_tag(defect)
                            defect["suggested_tag"] = suggested_tag
                            defect["suggestion_confidence"] = confidence
                            defect["suggestion_reasoning"] = f"ML prediction (duplicate #{duplicate_info['duplicate_id']} has non-ML tags: {duplicate_tags}): {reasoning}"
                            logger.info(f"   🤖 Using ML prediction: {suggested_tag} ({confidence:.0%}) - duplicate has non-ML tags")
                        else:
                            # ML not trained, mark as unknown
                            defect["suggested_tag"] = 'unknown'
                            defect["suggestion_confidence"] = duplicate_info['similarity']
                            defect["suggestion_reasoning"] = f"Duplicate #{duplicate_info['duplicate_id']} has non-ML tags: {duplicate_tags}, and ML model not trained"
                            logger.info(f"   ⚠️  ML not trained, marking as unknown")
                else:
                    # No duplicate found, use ML prediction
                    if self.suggester_trained:
                        suggested_tag, confidence, reasoning = self.tag_suggester.suggest_tag(defect)
                        defect["suggested_tag"] = suggested_tag
                        defect["suggestion_confidence"] = confidence
                        defect["suggestion_reasoning"] = reasoning
        
        # Log cancelled defects if any were filtered
        if cancelled_count > 0:
            logger.info(f"🚫 Filtered out {cancelled_count} cancelled/closed defects from {component}")
        
        result = {
            "component": component,
            "total": len(defects) - cancelled_count,  # Total ACTIVE defects (excluding cancelled)
            "untriaged": untriaged_count,  # Count of untriaged
            "test_bugs": test_bugs_count,  # Count of triaged test bugs
            "product_bugs": product_bugs_count,  # Count of triaged product bugs
            "infra_bugs": infra_bugs_count,  # Count of triaged infra bugs
            "defects": untriaged_defects,  # ONLY untriaged defects (with suggested tags and duplicate info)
            "triaged_defects": triaged_defects if collect_triaged else []  # Triaged defects for training
        }
        
        return result
    
    def train_ml_model_on_all_components(self, all_components: List[str]) -> bool:
        """
        Train ML model on ALL triaged defects across ALL components
        ALSO fetches and caches descriptions for ALL defects (triaged + untriaged)
        This is the COMPREHENSIVE data fetch that happens weekly (Thursday 12:17 PM)
        
        Args:
            all_components: List of all component names to fetch
            
        Returns:
            True if training successful
        """
        try:
            logger.info("=" * 70)
            logger.info("🎓 WEEKLY ML TRAINING + COMPREHENSIVE DATA FETCH")
            logger.info("=" * 70)
            
            # STEP 1: Get triaged defects from database cache (fast, includes historical data)
            logger.info("📚 Loading triaged defects from database cache...")
            cached_triaged_defects = []
            if self.database:
                cached_triaged_defects = self.database.get_all_triaged_defects_from_cache(all_components)
                logger.info(f"   ✅ Loaded {len(cached_triaged_defects)} triaged defects from cache")
            
            # STEP 2: Fetch fresh data from IBM to update cache
            logger.info(f"🔄 Fetching fresh data from {len(all_components)} components to update cache...")
            logger.info("This will take time but ensures complete data for the week")
            
            all_defects_for_caching = []  # ALL defects (triaged + untriaged)
            newly_fetched_triaged = []  # Newly fetched triaged defects
            newly_triaged_count = 0
            
            # Fetch defects from all components
            for i, component in enumerate(all_components, 1):
                try:
                    logger.info(f"[{i}/{len(all_components)}] Fetching {component}...")
                    defects = self.fetch_defects_for_component(component)
                    
                    if defects:
                        # Store ALL defects for comprehensive caching
                        for defect in defects:
                            defect['component'] = component  # Add component info
                        all_defects_for_caching.extend(defects)
                        
                        # Parse to collect newly triaged defects
                        parsed = self.parse_defects(defects, component, collect_triaged=True)
                        triaged = parsed.get("triaged_defects", [])
                        
                        if triaged:
                            newly_fetched_triaged.extend(triaged)  # ← FIX: Collect triaged defects!
                            newly_triaged_count += len(triaged)
                            logger.info(f"   ✓ Found {len(defects)} total defects ({len(triaged)} triaged)")
                        else:
                            logger.info(f"   ✓ Found {len(defects)} total defects (0 triaged)")
                
                except Exception as e:
                    logger.warning(f"   ✗ Error fetching {component}: {e}")
                    continue
            
            # Combine cached and newly fetched triaged defects (remove duplicates by ID)
            all_triaged_defects = cached_triaged_defects.copy()
            cached_ids = {str(d.get('id')) for d in cached_triaged_defects}
            
            for new_defect in newly_fetched_triaged:
                if str(new_defect.get('id')) not in cached_ids:
                    all_triaged_defects.append(new_defect)
            
            logger.info("=" * 70)
            logger.info(f"📊 Fetched {len(all_defects_for_caching)} TOTAL defects ({newly_triaged_count} newly triaged)")
            logger.info(f"📚 Using {len(all_triaged_defects)} triaged defects for training")
            logger.info(f"   ({len(cached_triaged_defects)} from cache + {len(all_triaged_defects) - len(cached_triaged_defects)} newly fetched)")
            logger.info("=" * 70)
            
            # Check which defects need descriptions BEFORE caching
            if all_defects_for_caching and self.database:
                # Get all defect IDs
                all_defect_ids = [str(d.get('id')) for d in all_defects_for_caching]
                
                # Batch check which defects have descriptions in cache
                logger.info(f"🔍 Checking which defects already have descriptions in database...")
                cached_descriptions = self.database.get_cached_descriptions(all_defect_ids)
                
                # Count defects with substantial descriptions
                defects_with_descriptions = 0
                defects_needing_descriptions = []
                defects_to_cache = []  # Only cache NEW defects or those needing updates
                
                for defect in all_defects_for_caching:
                    defect_id = str(defect.get('id'))
                    cached_data = cached_descriptions.get(defect_id, {})
                    cached_desc = cached_data.get('description', '')
                    
                    if cached_desc and len(cached_desc.strip()) >= 10:
                        # Has good description - reuse it
                        defect['description'] = cached_desc
                        defect['created'] = cached_data.get('creation_date', '')
                        defects_with_descriptions += 1
                    else:
                        # No description or too short - needs fetching
                        defects_needing_descriptions.append(defect)
                        defects_to_cache.append(defect)  # Will cache after fetching
                
                logger.info(f"   ✅ Found {defects_with_descriptions} defects with existing descriptions")
                logger.info(f"   ⚠️  Need to fetch {len(defects_needing_descriptions)} defects without descriptions")
                
                # DON'T cache yet - wait until descriptions are fetched
                # Caching happens at line 1109 after descriptions are fetched
                
                if defects_needing_descriptions:
                    logger.info(f"🔍 Fetching descriptions from Jazz/RTC API for {len(defects_needing_descriptions)} NEW defects...")
                    logger.info(f"   (Skipping {len(all_defects_for_caching) - len(defects_needing_descriptions)} defects that already have descriptions)")
                    logger.info("   This may take a few minutes...")
                else:
                    logger.info(f"✅ All {len(all_defects_for_caching)} defects already have descriptions in database!")
                    logger.info("   Skipping description fetch - using cached data")
                
                from concurrent.futures import ThreadPoolExecutor, as_completed
                import time
                from threading import Lock
                
                fetched_count = 0
                failed_count = 0
                retry_count = 0
                
                # Rate limiter to prevent overwhelming Jazz/RTC server
                rate_limit_lock = Lock()
                rate_limit_state = {'last_request_time': 0.0}  # Use dict to allow modification in nested function
                
                def fetch_with_retry_and_rate_limit(defect_id, max_retries=3):
                    """Fetch defect details with retry logic and rate limiting"""
                    nonlocal retry_count
                    
                    for attempt in range(max_retries):
                        try:
                            # Rate limiting: ensure minimum 0.2s between requests (faster but still safe)
                            with rate_limit_lock:
                                elapsed = time.time() - rate_limit_state['last_request_time']
                                if elapsed < 0.2:
                                    time.sleep(0.2 - elapsed)
                                rate_limit_state['last_request_time'] = time.time()
                            
                            # Fetch details
                            details = self.fetch_defect_details(defect_id)
                            
                            if attempt > 0:
                                retry_count += 1
                                logger.info(f"   ✓ Retry successful for defect {defect_id}")
                            
                            return details
                            
                        except Exception as e:
                            error_msg = str(e)
                            is_connection_error = "Connection refused" in error_msg or "Max retries exceeded" in error_msg
                            
                            if is_connection_error and attempt < max_retries - 1:
                                # Exponential backoff: 2s, 4s, 8s
                                wait_time = 2 ** (attempt + 1)
                                logger.warning(f"   ⚠️  Connection error for defect {defect_id}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                                time.sleep(wait_time)
                            else:
                                if attempt == max_retries - 1:
                                    logger.error(f"   ✗ Failed to fetch defect {defect_id} after {max_retries} attempts: {error_msg}")
                                raise
                    
                    return None
                
                # Fetch descriptions in batches with rate limiting and retry logic
                if defects_needing_descriptions:
                    batch_size = 100  # Process 100 defects at a time
                    num_batches = (len(defects_needing_descriptions) + batch_size - 1) // batch_size
                    
                    logger.info(f"   Processing in {num_batches} batches of up to {batch_size} defects")
                    logger.info(f"   Using 3 parallel workers with rate limiting (0.2s between requests)")
                    
                    for batch_num in range(num_batches):
                        start_idx = batch_num * batch_size
                        end_idx = min(start_idx + batch_size, len(defects_needing_descriptions))
                        batch = defects_needing_descriptions[start_idx:end_idx]
                        
                        logger.info(f"   📦 Batch {batch_num + 1}/{num_batches}: Processing defects {start_idx + 1}-{end_idx}...")
                        
                        # Process batch with 3 workers (balanced speed and reliability)
                        with ThreadPoolExecutor(max_workers=3) as executor:
                            future_to_defect = {
                                executor.submit(fetch_with_retry_and_rate_limit, str(d.get('id'))): d
                                for d in batch
                            }
                            
                            for future in as_completed(future_to_defect):
                                defect = future_to_defect[future]
                                try:
                                    details = future.result(timeout=120)
                                    if details and details.get('description'):
                                        # Update defect with fetched details
                                        defect['description'] = details['description']
                                        defect['created'] = details.get('created', '')
                                        fetched_count += 1
                                    else:
                                        failed_count += 1
                                except Exception as e:
                                    logger.debug(f"Failed to fetch details for {defect.get('id')}: {e}")
                                    failed_count += 1
                        
                        # Progress update
                        logger.info(f"   ✓ Batch {batch_num + 1}/{num_batches} complete: {fetched_count} fetched, {failed_count} failed")
                        
                        # Delay between batches (except last batch) to avoid rate limiting
                        if batch_num < num_batches - 1:
                            delay = 5  # 5 seconds between batches (reduced from 10)
                            logger.info(f"   ⏸️  Waiting {delay}s before next batch...")
                            time.sleep(delay)
                    
                    logger.info(f"   ✅ Fetched descriptions: {fetched_count}/{len(defects_needing_descriptions)}")
                    if retry_count > 0:
                        logger.info(f"   🔄 Successful retries: {retry_count}")
                    if failed_count > 0:
                        logger.warning(f"   ⚠️  Failed to fetch: {failed_count}/{len(defects_needing_descriptions)}")
                    
                    # Update database with fetched descriptions
                    if fetched_count > 0:
                        logger.info(f"💾 Updating database with fetched descriptions...")
                        self.database.cache_defect_descriptions(defects_needing_descriptions)
                        logger.info(f"   ✅ Updated {fetched_count} defects with descriptions")
                
                logger.info("=" * 70)
                
                # Apply descriptions and tags to triaged defects for ML training
                logger.info("📝 Loading descriptions for triaged defects from database...")
                
                # Get all triaged defect IDs
                triaged_defect_ids = [str(d.get('id')) for d in all_triaged_defects]
                
                # Batch load descriptions from cache
                cached_triaged_descriptions = self.database.get_cached_descriptions(triaged_defect_ids)
                
                for triaged_defect in all_triaged_defects:
                    defect_id = str(triaged_defect.get('id'))
                    
                    # First try to get from freshly fetched data
                    found = False
                    for full_defect in all_defects_for_caching:
                        if str(full_defect.get('id')) == defect_id:
                            triaged_defect['description'] = full_defect.get('description', '')
                            triaged_defect['creation_date'] = full_defect.get('created', '')
                            # Copy tags from Build Break Report if not already present
                            if not triaged_defect.get('triageTags'):
                                triaged_defect['triageTags'] = full_defect.get('tags', [])
                            found = True
                            break
                    
                    # If not in fresh data, load from database cache
                    if not found or not triaged_defect.get('description'):
                        cached_data = cached_triaged_descriptions.get(defect_id, {})
                        cached_desc = cached_data.get('description', '')
                        if cached_desc:
                            triaged_defect['description'] = cached_desc
                
                # Count how many triaged defects have descriptions
                with_desc = sum(1 for d in all_triaged_defects if d.get('description') and len(d.get('description', '')) > 10)
                logger.info(f"   ✅ {with_desc}/{len(all_triaged_defects)} triaged defects have descriptions for training")
            
            if len(all_triaged_defects) < 10:
                logger.warning(f"⚠️  Not enough triaged defects for training (need at least 10, got {len(all_triaged_defects)})")
                return False
            
            # Train the ML model with incremental learning
            logger.info("=" * 70)
            logger.info("🤖 Training ML model with incremental learning...")
            logger.info("=" * 70)
            
            if self.tag_suggester.train_from_defects(all_triaged_defects, incremental=True):
                logger.info("=" * 70)
                logger.info("✅ WEEKLY ML TRAINING + DATA CACHING COMPLETE")
                logger.info("   • ML model trained with incremental learning")
                logger.info(f"   • {len(all_defects_for_caching)} defects cached for fast daily operations")
                logger.info("=" * 70)
                return True
            else:
                logger.error("❌ ML model training failed")
                return False
                
        except Exception as e:
            logger.error(f"Error in ML training + data fetch: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
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
        
        
        return results
    
    def parse_defects_simple(self, defects: List[Dict], component: str) -> Dict:
        """
        Simple defect parsing for dashboard - NO ML, NO duplicate detection
        Just counts and basic categorization for faster processing
        """
        untriaged_count = 0
        test_bugs_count = 0
        product_bugs_count = 0
        infra_bugs_count = 0
        
        for defect in defects:
            # Get triage tags
            triage_tags = defect.get("triageTags", defect.get("tags", []))
            
            if not isinstance(triage_tags, list):
                triage_tags = []
            
            tags_lower = [str(tag).lower().strip() for tag in triage_tags]
            
            # Check for triage tags
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
            
            has_triaged_tag = has_test_bug or has_product_bug or has_infra_bug
            
            if not has_triaged_tag:
                untriaged_count += 1
            else:
                if has_infra_bug:
                    infra_bugs_count += 1
                elif has_test_bug:
                    test_bugs_count += 1
                elif has_product_bug:
                    product_bugs_count += 1
        
        return {
            "component": component,
            "total": len(defects),
            "untriaged": untriaged_count,
            "test_bugs": test_bugs_count,
            "product_bugs": product_bugs_count,
            "infra_bugs": infra_bugs_count,
            "untriaged_defects": [],  # Empty for dashboard
            "timestamp": datetime.now().isoformat()
        }
    
    def fetch_all_components_background(self, all_components: List[str], database) -> Dict:
        """
        Fetch defects for ALL components in background (for dashboard AND notifications)
        NEW OPTIMIZATION: Uses FULL parsing with ML and duplicate detection
        This runs at 9:00 AM, so team notifications at 10:00 AM+ can use pre-processed data
        Also fetches ALL SOE Triage defects (not filtered)
        Stores data in database but doesn't send notifications
        Returns summary of fetch operation
        
        Now supports checkpointing - can resume from where it stopped if interrupted
        """
        # Initialize checkpoint manager
        checkpoint = FetchCheckpoint()
        
        # Get components to fetch (either all or remaining from checkpoint)
        components_to_fetch = checkpoint.get_remaining_components(all_components)
        completed_components = []
        
        logger.info(f"🔄 Starting FULL background fetch for {len(components_to_fetch)} components...")
        logger.info(f"   (Using FULL parsing with ML & duplicate detection)")
        logger.info(f"   This pre-processes data for team notifications to eliminate lag")
        
        fetch_summary = {
            "timestamp": datetime.now().isoformat(),
            "total_components": len(all_components),
            "fetching": len(components_to_fetch),
            "successful": 0,
            "failed": 0,
            "components_data": {},
            "soe_defects_count": 0,
            "resumed_from_checkpoint": len(components_to_fetch) < len(all_components)
        }
        
        # Fetch Build Break Report defects for components
        for idx, component in enumerate(components_to_fetch, 1):
            try:
                logger.info(f"📥 [{idx}/{len(components_to_fetch)}] Fetching {component}...")
                
                # Save checkpoint BEFORE fetching
                checkpoint.save_checkpoint(completed_components, all_components)
                
                defects = self.fetch_defects_for_component(component)
                
                if defects is not None:
                    # Add component field to each defect for caching
                    for defect in defects:
                        defect['component'] = component
                    
                    # Use FULL parsing with ML and duplicate detection
                    parsed = self.parse_defects(defects, component)
                    
                    # Store in BOTH tables for dashboard and notifications
                    database.store_all_components_snapshot(component, parsed, is_monitored=False)
                    database.store_daily_snapshot({"components": {component: parsed}})
                    
                    fetch_summary["successful"] += 1
                    fetch_summary["components_data"][component] = {
                        "total": parsed["total"],
                        "untriaged": parsed["untriaged"]
                    }
                    
                    # Mark as completed
                    completed_components.append(component)
                    
                    # Save checkpoint after successful fetch
                    checkpoint.save_checkpoint(completed_components, all_components)
                    
                    logger.info(f"✅ Fetched {component}: {parsed['total']} defects ({parsed['untriaged']} untriaged)")
                else:
                    fetch_summary["failed"] += 1
                    logger.warning(f"❌ Failed to fetch {component}")
                    # Still mark as completed to avoid retrying failed components
                    completed_components.append(component)
                    checkpoint.save_checkpoint(completed_components, all_components)
                    
            except Exception as e:
                fetch_summary["failed"] += 1
                logger.error(f"❌ Error fetching {component}: {e}")
                # Mark as completed to skip on retry
                completed_components.append(component)
                checkpoint.save_checkpoint(completed_components, all_components)
        
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
        
        # Calculate aggregate totals
        total_defects = sum(comp_data.get('total', 0) for comp_data in fetch_summary['components_data'].values())
        total_untriaged = sum(comp_data.get('untriaged', 0) for comp_data in fetch_summary['components_data'].values())
        
        fetch_summary['total_defects'] = total_defects
        fetch_summary['total_untriaged'] = total_untriaged
        
        # Clear checkpoint when all components are fetched
        if len(completed_components) == len(all_components):
            checkpoint.clear_checkpoint()
            logger.info(f"✅ Background fetch complete: {fetch_summary['successful']}/{fetch_summary['total_components']} successful")
        else:
            remaining = len(all_components) - len(completed_components)
            logger.info(f"✅ Partial fetch complete: {fetch_summary['successful']} successful, {remaining} remaining (checkpoint saved)")
        
        return fetch_summary
    
    def check_monitored_components(self, monitored_components: List[Dict], database, team_name: str = None) -> Dict:
        """
        OPTIMIZED: Read pre-processed data from daily_snapshots (processed at 9:00 AM)
        Just retrieve data and prepare for notification - NO heavy processing
        
        This eliminates notification lag since all ML predictions and duplicate detection
        were already done during the 9:00 AM all_components_fetch
        
        Args:
            monitored_components: List of component configs to check
            database: Database instance
            team_name: Team name for logging (optional)
        """
        logger.info(f"📖 Reading pre-processed data from daily_snapshots...")
        
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
        
        logger.info(f"🔍 Retrieving data for {len(component_names)} monitored components...")
        
        # Step 1: Read pre-processed data from daily_snapshots
        for idx, comp_config in enumerate(monitored_components, 1):
            component = comp_config.get("name")
            should_notify = comp_config.get("notify", True)
            
            if not component:
                logger.warning("⚠️  Skipping component with no name")
                continue
            
            if not should_notify:
                logger.info(f"⏭️  Skipping {component} (notify=false)")
                continue
            
            logger.info(f"📖 [{idx}/{len(component_names)}] Reading {component} from cache...")
            
            # Get pre-processed data from daily_snapshots
            cached_data = database.get_component_from_daily_snapshot(component)
            
            if cached_data:
                # Add slack channel info
                cached_data["slack_channel"] = comp_config.get("slack_channel", "#defect-notifications")
                cached_data["notify"] = should_notify
                
                results["components"][component] = cached_data
                results["total_defects"] += cached_data.get("total", 0)
                results["total_untriaged"] += cached_data.get("untriaged", 0)
                results["monitored_components"].append(component)
                
                logger.info(f"✅ {component}: {cached_data.get('total', 0)} defects ({cached_data.get('untriaged', 0)} untriaged) [from cache]")
            else:
                logger.warning(f"⚠️  No cached data for {component} - may need to wait for 9:00 AM fetch")
        
        # Step 2: Get SOE Triage defects from cache
        logger.info("📋 Reading SOE Triage defects from cache...")
        soe_data = database.get_latest_soe_snapshot()
        
        if soe_data:
            all_soe_defects = soe_data.get("defects", [])
            
            # Filter SOE defects to only include monitored components
            filtered_soe = [
                defect for defect in all_soe_defects
                if any(
                    (monitored and monitored.lower() in defect.get('functionalArea', '').lower()) or
                    (monitored and defect.get('functionalArea', '').lower() in monitored.lower())
                    for monitored in component_names
                )
            ]
            
            results["soe_triage"] = {
                "total": len(filtered_soe),
                "defects": filtered_soe,
                "all_defects": len(all_soe_defects)  # Total before filtering
            }
            results["total_defects"] += len(filtered_soe)
            
            logger.info(f"✅ SOE Triage: {len(filtered_soe)} overdue defects (filtered from {len(all_soe_defects)} total) [from cache]")
        else:
            logger.warning("⚠️ No cached SOE data - may need to wait for 9:00 AM fetch")
        
        logger.info(f"✅ Data retrieval complete: {results['total_defects']} total defects, {results['total_untriaged']} untriaged")
        logger.info(f"   ⚡ Using pre-processed data - NO lag!")
        
        return results

# Made with Bob
