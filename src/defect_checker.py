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
        
        # Log ML model status on startup
        ml_stats = self.tag_suggester.get_training_stats()
        if ml_stats.get('trained'):
            logger.info("=" * 60)
            logger.info("🤖 ML Tag Suggester Status")
            logger.info("=" * 60)
            logger.info(f"✅ Model trained: Yes")
            logger.info(f"   Training accuracy: {ml_stats.get('accuracy', 'N/A')}")
            logger.info(f"   Total samples: {ml_stats.get('total_samples', 'N/A')}")
            logger.info(f"   Tag distribution: {ml_stats.get('tag_distribution', {})}")
            logger.info("=" * 60)
        else:
            logger.info("=" * 60)
            logger.info("🤖 ML Tag Suggester Status")
            logger.info("=" * 60)
            logger.info(f"⚠️  Model trained: No")
            logger.info(f"   ML available: {ml_stats.get('ml_available', False)}")
            logger.info(f"   💡 Train model with: docker-compose exec defect-monitor python3 retrain_model.sh")
            logger.info("=" * 60)
        
        # Lower threshold to 0.85 for summary-only matching (was 0.7)
        # Since we only have summaries, we need high similarity to avoid false positives
        self.duplicate_detector = DuplicateDetector(similarity_threshold=0.85)
    
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
                
                # Check for authentication failure and auto-refresh cookies
                cookie_monitor = get_cookie_monitor()
                if cookie_monitor.detect_cookie_expiration(response):
                    logger.warning(f"🔴 Cookie expiration detected for {component}")
                    if cookie_monitor.refresh_cookies_now():
                        logger.info("✅ Cookies refreshed - retrying request...")
                        # Get new session with fresh cookies
                        session = self.authenticator.get_session()
                        if session:
                            continue  # Retry with new cookies
                    else:
                        logger.error("❌ Failed to refresh cookies")
                        return None
                
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
    
    def fetch_defect_description(self, defect_id: str, max_retries: int = 2) -> str:
        """
        Fetch description for a specific defect from Jazz/RTC with retry logic
        
        Args:
            defect_id: The defect ID
            max_retries: Maximum number of retry attempts
            
        Returns:
            Description text or empty string if not found
        """
        for attempt in range(max_retries):
            try:
                session = self.authenticator.get_session()
                if not session:
                    return ""
                
                # Jazz/RTC work item URL
                jazz_url = f"https://wasrtc.hursley.ibm.com:9443/jazz/oslc/workitems/{defect_id}.json"
                
                # Increase timeout to 30 seconds
                response = session.get(
                    jazz_url,
                    timeout=30,
                    headers={'Accept': 'application/json'},
                    verify=False
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Description is in dcterms:description
                    description = data.get('dcterms:description', data.get('description', ''))
                    return str(description) if description else ""
                
                return ""
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                    logger.debug(f"Timeout fetching description for {defect_id}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.debug(f"Could not fetch description for defect {defect_id}: Timeout after {max_retries} attempts")
                    return ""
            except Exception as e:
                logger.debug(f"Could not fetch description for defect {defect_id}: {e}")
                return ""
        
        return ""
    
    def fetch_descriptions_parallel(self, defect_ids: List[str], max_workers: int = 5) -> Dict[str, str]:
        """
        Fetch descriptions for multiple defects in parallel
        
        Args:
            defect_ids: List of defect IDs
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary mapping defect_id to description
        """
        descriptions = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_id = {
                executor.submit(self.fetch_defect_description, defect_id): defect_id
                for defect_id in defect_ids
            }
            
            # Process completed tasks
            completed = 0
            total = len(defect_ids)
            for future in as_completed(future_to_id):
                defect_id = future_to_id[future]
                try:
                    description = future.result()
                    descriptions[defect_id] = description
                    completed += 1
                    
                    # Log progress every 10 defects
                    if completed % 10 == 0 or completed == total:
                        logger.info(f"📥 Fetched {completed}/{total} descriptions...")
                        
                except Exception as e:
                    logger.debug(f"Error fetching description for {defect_id}: {e}")
                    descriptions[defect_id] = ""
        
        return descriptions
    
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
    
    def parse_defects(self, defects: List[Dict], component: str, collect_triaged: bool = False) -> Dict:
        """
        Parse and categorize defects - ONLY returns untriaged defects
        Matches the logic from defect-triaging-extension and IBM Build Break Report
        Also checks for duplicates within the component
        
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
        
        for defect in defects:
            # Store all defects for duplicate checking
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
            logger.info(f"   ✓ Found {len(triaged_defects)} triaged defects")
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
        
        # Fetch descriptions for untriaged defects and all defects (for duplicate checking)
        # Use caching to avoid re-fetching descriptions
        if untriaged_defects:
            # Collect all defect IDs
            untriaged_ids = [str(d.get('id')) for d in untriaged_defects if d.get('id')]
            all_ids = [str(d.get('id')) for d in all_defects_for_dup_check if d.get('id')]
            
            # Try to get cached descriptions first
            cached_descriptions = {}
            ids_to_fetch = []
            
            if self.database:
                logger.info(f"🔍 Checking cache for {len(all_ids)} defect descriptions...")
                cached_descriptions = self.database.get_cached_descriptions(all_ids)
                
                # Determine which IDs need to be fetched
                ids_to_fetch = [id for id in all_ids if id not in cached_descriptions]
                
                if cached_descriptions:
                    logger.info(f"✅ Found {len(cached_descriptions)} cached descriptions")
                if ids_to_fetch:
                    logger.info(f"📥 Need to fetch {len(ids_to_fetch)} new descriptions...")
            else:
                # No database, fetch all
                ids_to_fetch = all_ids
            
            # Fetch missing descriptions in parallel
            newly_fetched = {}
            if ids_to_fetch:
                newly_fetched = self.fetch_descriptions_parallel(ids_to_fetch, max_workers=5)
                
                # Cache the newly fetched descriptions
                if self.database and newly_fetched:
                    defects_to_cache = []
                    for defect_id, description in newly_fetched.items():
                        # Find the defect in all_defects_for_dup_check to get full info
                        defect_info = next((d for d in all_defects_for_dup_check if str(d.get('id')) == defect_id), None)
                        if defect_info:
                            defect_info['description'] = description
                            defect_info['component'] = component
                            defects_to_cache.append(defect_info)
                    
                    if defects_to_cache:
                        self.database.cache_defect_descriptions(defects_to_cache)
            
            # Combine cached and newly fetched descriptions
            all_descriptions = {**cached_descriptions, **newly_fetched}
            
            # Apply descriptions to untriaged defects
            for defect in untriaged_defects:
                defect_id = str(defect.get('id'))
                if defect_id in all_descriptions:
                    desc_data = all_descriptions[defect_id]
                    # Handle both dict (from cache) and string (from fetch)
                    if isinstance(desc_data, dict):
                        defect['description'] = desc_data.get('description', '')
                    else:
                        defect['description'] = desc_data
                else:
                    defect['description'] = ''
            
            # Apply descriptions to all defects for duplicate checking
            for defect in all_defects_for_dup_check:
                defect_id = str(defect.get('id'))
                if defect_id in all_descriptions:
                    desc_data = all_descriptions[defect_id]
                    # Handle both dict (from cache) and string (from fetch)
                    if isinstance(desc_data, dict):
                        defect['description'] = desc_data.get('description', '')
                        # Update triageTags from cache if available (for duplicate detection)
                        if 'triageTags' in desc_data and desc_data['triageTags']:
                            # Always use cached tags if they exist (they're authoritative)
                            defect['triageTags'] = desc_data['triageTags']
                    else:
                        defect['description'] = desc_data
            
            logger.info(f"🔍 Checking {len(untriaged_defects)} untriaged defects for duplicates and suggestions...")
            
            for defect in untriaged_defects:
                # Check for duplicates FIRST
                duplicate_info = self.duplicate_detector.check_defect_for_duplicates(
                    defect,
                    all_defects_for_dup_check
                )
                
                if duplicate_info:
                    defect["duplicate_info"] = duplicate_info
                    logger.info(f"   🔄 Defect {defect.get('id')} may be duplicate of {duplicate_info['duplicate_id']} ({duplicate_info['similarity']:.0%} similar)")
                    
                    # Use duplicate's tags instead of ML prediction
                    duplicate_tags = duplicate_info.get('duplicate_tags', [])
                    if duplicate_tags:
                        # Determine primary tag from duplicate
                        tags_lower = [str(tag).lower().strip() for tag in duplicate_tags]
                        
                        # Priority: infrastructure > test > product
                        if any('infra' in tag or 'infrastructure' in tag for tag in tags_lower):
                            suggested_tag = 'infrastructure_bug'
                        elif any('test' in tag for tag in tags_lower):
                            suggested_tag = 'test_bug'
                        elif any('product' in tag for tag in tags_lower):
                            suggested_tag = 'product_bug'
                        else:
                            suggested_tag = 'unknown'
                        
                        defect["suggested_tag"] = suggested_tag
                        defect["suggestion_confidence"] = duplicate_info['similarity']
                        defect["suggestion_reasoning"] = f"Based on duplicate defect #{duplicate_info['duplicate_id']} with tags: {duplicate_tags}"
                    else:
                        # Duplicate has no tags, fall back to ML
                        if self.suggester_trained:
                            suggested_tag, confidence, reasoning = self.tag_suggester.suggest_tag(defect)
                            defect["suggested_tag"] = suggested_tag
                            defect["suggestion_confidence"] = confidence
                            defect["suggestion_reasoning"] = reasoning
                else:
                    # No duplicate found, use ML prediction
                    if self.suggester_trained:
                        suggested_tag, confidence, reasoning = self.tag_suggester.suggest_tag(defect)
                        defect["suggested_tag"] = suggested_tag
                        defect["suggestion_confidence"] = confidence
                        defect["suggestion_reasoning"] = reasoning
        
        result = {
            "component": component,
            "total": len(defects),  # Total defects from API
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
        This provides much better training data (1200+ defects) than per-component training
        
        Args:
            all_components: List of all component names to fetch
            
        Returns:
            True if training successful
        """
        try:
            logger.info("=" * 70)
            logger.info("🎓 TRAINING ML MODEL ON ALL COMPONENTS")
            logger.info("=" * 70)
            logger.info(f"Fetching triaged defects from {len(all_components)} components...")
            
            all_triaged_defects = []
            
            # Fetch defects from all components and collect triaged ones
            for i, component in enumerate(all_components, 1):
                try:
                    logger.info(f"[{i}/{len(all_components)}] Fetching {component}...")
                    defects = self.fetch_defects_for_component(component)
                    
                    if defects:
                        # Parse with collect_triaged=True to get triaged defects
                        parsed = self.parse_defects(defects, component, collect_triaged=True)
                        triaged = parsed.get("triaged_defects", [])
                        
                        if triaged:
                            all_triaged_defects.extend(triaged)
                            logger.info(f"   ✓ Found {len(triaged)} triaged defects")
                        else:
                            logger.debug(f"   - No triaged defects")
                    
                except Exception as e:
                    logger.warning(f"   ✗ Error fetching {component}: {e}")
                    continue
            
            logger.info("=" * 70)
            logger.info(f"📊 Collected {len(all_triaged_defects)} triaged defects across all components")
            logger.info("=" * 70)
            
            # Fetch descriptions for triaged defects (for better ML training)
            if all_triaged_defects:
                # Collect IDs that need descriptions (check for empty or missing descriptions)
                ids_needing_desc = [
                    str(d.get('id')) for d in all_triaged_defects
                    if d.get('id') and not d.get('description')  # Check if description is empty or missing
                ]
                
                if ids_needing_desc:
                    logger.info(f"📥 Fetching descriptions for {len(ids_needing_desc)} triaged defects in parallel...")
                    logger.info("   (Using 3 parallel workers for stable authentication...)")
                    
                    # Fetch in parallel with 3 workers for training (balanced speed vs stability)
                    descriptions = self.fetch_descriptions_parallel(ids_needing_desc, max_workers=3)
                    
                    # Apply descriptions to defects
                    for defect in all_triaged_defects:
                        defect_id = str(defect.get('id'))
                        if defect_id in descriptions:
                            defect['description'] = descriptions[defect_id]
                    
                    # Cache the fetched descriptions to database
                    if self.database and descriptions:
                        logger.info(f"   💾 Caching {len(descriptions)} descriptions to database...")
                        self.database.cache_defect_descriptions(all_triaged_defects)
                    
                    logger.info(f"   ✅ Fetched descriptions for all {len(ids_needing_desc)} defects")
                    logger.info("=" * 70)
                else:
                    logger.info("   ℹ️  All triaged defects already have descriptions (from cache or previous fetch)")
            
            if len(all_triaged_defects) < 10:
                logger.warning(f"⚠️  Not enough triaged defects for training (need at least 10, got {len(all_triaged_defects)})")
                return False
            
            # Train the ML model
            if self.tag_suggester.train_from_defects(all_triaged_defects):
                logger.info("=" * 70)
                logger.info("✅ ML MODEL TRAINING COMPLETE")
                logger.info("=" * 70)
                return True
            else:
                logger.error("❌ ML model training failed")
                return False
                
        except Exception as e:
            logger.error(f"Error training ML model: {e}")
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
        
        logger.info(f"✅ Check complete: {results['total_defects']} total defects, {results['total_untriaged']} untriaged")
        
        return results
    
    def fetch_all_components_background(self, all_components: List[str], database) -> Dict:
        """
        Fetch defects for ALL 51 components in background (for component explorer)
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
        
        logger.info(f"🔄 Starting background fetch for {len(components_to_fetch)} components...")
        
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
                
                # Save checkpoint BEFORE fetching (marks as "in progress")
                # This way if interrupted, we know to skip this component next time
                checkpoint.save_checkpoint(completed_components, all_components)
                
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
        
        # Clear checkpoint when all components are fetched
        if len(completed_components) == len(all_components):
            checkpoint.clear_checkpoint()
            logger.info(f"✅ Background fetch complete: {fetch_summary['successful']}/{fetch_summary['total_components']} successful")
        else:
            remaining = len(all_components) - len(completed_components)
            logger.info(f"✅ Partial fetch complete: {fetch_summary['successful']} successful, {remaining} remaining (checkpoint saved)")
        
        return fetch_summary
    
    def check_monitored_components(self, monitored_components: List[Dict], database) -> Dict:
        """
        Check defects for monitored components only (these will send notifications)
        Matches Chrome extension workflow:
        1. Fetch Build Break Report defects for monitored components
        2. Fetch SOE Triage defects (filtered by monitored components)
        3. Send single grouped Slack notification
        4. Store data for dashboard
        
        Now supports checkpointing - can resume if interrupted
        """
        # Initialize checkpoint manager for monitored components
        checkpoint = FetchCheckpoint(checkpoint_file="data/monitored_checkpoint.json")
        
        # Get component names
        all_component_names = [comp.get("name") for comp in monitored_components]
        
        # Get components to check (either all or remaining from checkpoint)
        components_to_check = checkpoint.get_remaining_components(all_component_names)
        completed_components = []
        
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
        
        # Filter to only check components that need checking (from checkpoint)
        components_to_check_configs = [
            comp for comp in monitored_components
            if comp.get("name") in components_to_check and comp.get("notify", True)
        ]
        
        if len(components_to_check) < len(component_names):
            logger.info(f"🔄 Resuming from checkpoint: {len(components_to_check)}/{len(component_names)} components to check")
        else:
            logger.info(f"🔍 Checking {len(component_names)} monitored components...")
        
        # Step 1: Fetch defects for each monitored component from Build Break Report
        for idx, comp_config in enumerate(components_to_check_configs, 1):
            component = comp_config.get("name")
            should_notify = comp_config.get("notify", True)
            
            if not component:
                logger.warning("⚠️  Skipping component with no name")
                continue
            
            if not should_notify:
                logger.info(f"⏭️  Skipping {component} (notify=false)")
                continue
            
            logger.info(f"📥 [{idx}/{len(components_to_check_configs)}] Checking {component}...")
            
            # Save checkpoint BEFORE fetching
            checkpoint.save_checkpoint(completed_components, component_names)
            
            defects = self.fetch_defects_for_component(component)
            
            if defects is not None:
                parsed = self.parse_defects(defects, component)
                parsed["slack_channel"] = comp_config.get("slack_channel", "#defect-notifications")
                parsed["notify"] = should_notify
                
                results["components"][component] = parsed
                results["total_defects"] += parsed["total"]
                results["total_untriaged"] += parsed["untriaged"]
                results["monitored_components"].append(component)
                
                # Mark as completed
                completed_components.append(component)
                
                # Save checkpoint after successful fetch
                checkpoint.save_checkpoint(completed_components, component_names)
                
                # Store in both tables
                database.store_daily_snapshot({"components": {component: parsed}})
                database.store_all_components_snapshot(component, parsed, is_monitored=True)
                
                logger.info(f"✅ {component}: {parsed['total']} defects ({parsed['untriaged']} untriaged)")
            else:
                logger.warning(f"❌ Failed to fetch {component}")
                # Mark as completed to skip on retry
                completed_components.append(component)
                checkpoint.save_checkpoint(completed_components, component_names)
        
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
        
        # Clear checkpoint when all components are checked
        if len(completed_components) == len(component_names):
            checkpoint.clear_checkpoint()
            logger.info(f"✅ Monitored check complete: {results['total_defects']} total defects, {results['total_untriaged']} untriaged")
        else:
            remaining = len(component_names) - len(completed_components)
            logger.info(f"✅ Partial check complete: {results['total_defects']} total defects, {remaining} components remaining (checkpoint saved)")
        
        return results

# Made with Bob
