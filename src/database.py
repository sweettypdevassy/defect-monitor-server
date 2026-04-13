"""
Database Module
Handles storage and retrieval of defect data for historical tracking
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DefectDatabase:
    """Handles database operations for defect tracking"""
    
    def __init__(self, db_path: str = "data/defects.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Daily snapshots table (for monitored components)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    component TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    untriaged INTEGER NOT NULL,
                    test_bugs INTEGER NOT NULL,
                    product_bugs INTEGER NOT NULL,
                    infra_bugs INTEGER NOT NULL,
                    data JSON NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(date, component)
                )
            """)
            
            # All components snapshots table (for all 51 components)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS all_components_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    component TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    untriaged INTEGER NOT NULL,
                    test_bugs INTEGER NOT NULL,
                    product_bugs INTEGER NOT NULL,
                    infra_bugs INTEGER NOT NULL,
                    data JSON NOT NULL,
                    created_at TEXT NOT NULL,
                    is_monitored INTEGER DEFAULT 0,
                    UNIQUE(date, component)
                )
            """)
            
            # SOE Triage snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS soe_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    data JSON NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(date)
                )
            """)
            
            # Check history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS check_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_defects INTEGER NOT NULL,
                    total_untriaged INTEGER NOT NULL,
                    components_checked INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_message TEXT,
                    data JSON NOT NULL
                )
            """)
            
            # Defect descriptions cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS defect_descriptions (
                    defect_id TEXT PRIMARY KEY,
                    description TEXT,
                    summary TEXT,
                    component TEXT,
                    functional_area TEXT,
                    state TEXT,
                    tags TEXT,
                    creation_date TEXT,
                    number_builds INTEGER,
                    fetched_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Add creation_date column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE defect_descriptions ADD COLUMN creation_date TEXT")
                logger.info("Added creation_date column to defect_descriptions table")
            except Exception:
                pass  # Column already exists
            
            # Add number_builds column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE defect_descriptions ADD COLUMN number_builds INTEGER")
                logger.info("Added number_builds column to defect_descriptions table")
            except Exception:
                pass  # Column already exists
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_defect_component
                ON defect_descriptions(component)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_defect_state
                ON defect_descriptions(state)
            """)
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def store_daily_snapshot(self, results: Dict):
        """Store daily snapshot of defect data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            date = datetime.now().strftime("%Y-%m-%d")
            created_at = datetime.now().isoformat()
            
            # Store component data
            for component, data in results.get("components", {}).items():
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_snapshots 
                    (date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    component,
                    data["total"],
                    data["untriaged"],
                    data["test_bugs"],
                    data["product_bugs"],
                    data["infra_bugs"],
                    json.dumps(data),
                    created_at
                ))
            
            # Store SOE Triage data
            soe_data = results.get("soe_triage")
            if soe_data:
                cursor.execute("""
                    INSERT OR REPLACE INTO soe_snapshots 
                    (date, total, data, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    date,
                    soe_data["total"],
                    json.dumps(soe_data),
                    created_at
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Daily snapshot stored for {date}")
            
        except Exception as e:
            logger.error(f"Error storing daily snapshot: {e}")
    
    def cache_defect_descriptions(self, defects: List[Dict]):
        """Cache defect descriptions in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            
            logger.debug(f"🔍 Caching {len(defects)} defects")
            
            for defect in defects:
                # Debug log the first defect
                if defect.get('id') == 308598:
                    logger.debug(f"🔍 Defect 308598 data: component={defect.get('component')}, functional_area={defect.get('functional_area')}, functionalArea={defect.get('functionalArea')}")
                defect_id = str(defect.get('id', ''))
                if not defect_id:
                    continue
                
                # Convert tags list to JSON string
                tags = defect.get('triageTags', defect.get('tags', []))
                tags_str = json.dumps(tags) if tags else '[]'
                
                # Get creation date if available
                creation_date = defect.get('created') or defect.get('creationDate') or defect.get('creation_date')
                
                # Get number_builds if available
                number_builds = defect.get('number_builds', defect.get('numberBuilds', 0))
                
                cursor.execute("""
                    INSERT OR REPLACE INTO defect_descriptions
                    (defect_id, description, summary, component, functional_area, state, tags, creation_date, number_builds, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    defect_id,
                    defect.get('description', ''),
                    defect.get('summary', ''),
                    defect.get('component', ''),
                    defect.get('functionalArea', defect.get('functional_area', '')),
                    defect.get('state', ''),
                    tags_str,
                    creation_date,
                    number_builds,
                    timestamp,
                    timestamp
                ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"✅ Cached descriptions for {len(defects)} defects")
            
        except Exception as e:
            logger.error(f"Error caching defect descriptions: {e}")
    
    def get_cached_descriptions(self, defect_ids: List[str]) -> Dict[str, Dict]:
        """Get cached descriptions for defect IDs"""
        try:
            if not defect_ids:
                return {}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create placeholders for SQL IN clause
            placeholders = ','.join('?' * len(defect_ids))
            
            cursor.execute(f"""
                SELECT defect_id, description, summary, component, functional_area, state, tags
                FROM defect_descriptions
                WHERE defect_id IN ({placeholders})
            """, defect_ids)
            
            results = {}
            for row in cursor.fetchall():
                defect_id, description, summary, component, functional_area, state, tags_str = row
                results[defect_id] = {
                    'id': defect_id,
                    'description': description or '',
                    'summary': summary or '',
                    'component': component or '',
                    'functionalArea': functional_area or '',
                    'state': state or '',
                    'triageTags': json.loads(tags_str) if tags_str else []
                }
            
            conn.close()
            
            logger.debug(f"✅ Retrieved {len(results)}/{len(defect_ids)} cached descriptions")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving cached descriptions: {e}")
            return {}
    
    def get_all_cached_descriptions_for_component(self, component: str) -> List[Dict]:
        """Get all cached descriptions for a component, filtering out cancelled/closed defects"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT defect_id, description, summary, component, functional_area, state, tags, creation_date, number_builds
                FROM defect_descriptions
                WHERE component = ?
            """, (component,))
            
            results = []
            filtered_count = 0
            for row in cursor.fetchall():
                defect_id, description, summary, component, functional_area, state, tags_str, creation_date, number_builds = row
                
                # Filter out cancelled/closed/resolved defects
                if state and isinstance(state, str):
                    state_lower = state.lower()
                    if any(keyword in state_lower for keyword in ['canceled', 'cancelled', 'closed', 'resolved']):
                        if 'jazz/oslc/workflows' in state_lower:  # Only filter if it's a valid RTC state URL
                            filtered_count += 1
                            logger.debug(f"Filtering cached cancelled defect {defect_id}")
                            continue
                
                results.append({
                    'id': defect_id,
                    'description': description or '',
                    'summary': summary or '',
                    'component': component or '',
                    'functionalArea': functional_area or '',
                    'state': state or '',
                    'triageTags': json.loads(tags_str) if tags_str else [],
                    'creation_date': creation_date or '',
                    'number_builds': number_builds or 0
                })
            
            conn.close()
            
            if filtered_count > 0:
                logger.info(f"✅ Retrieved {len(results)} cached descriptions for {component} (filtered {filtered_count} cancelled)")
            else:
                logger.debug(f"✅ Retrieved {len(results)} cached descriptions for {component}")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving cached descriptions for component: {e}")
            return []
    
    def delete_cached_descriptions(self, defect_ids: List[str]) -> bool:
        """
        Delete cached descriptions for specific defect IDs
        Used to remove stale defects that no longer appear in Build Break Report
        
        Args:
            defect_ids: List of defect IDs to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not defect_ids:
            return True
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete defects
            placeholders = ','.join('?' * len(defect_ids))
            cursor.execute(f"""
                DELETE FROM defect_descriptions
                WHERE defect_id IN ({placeholders})
            """, defect_ids)
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"🗑️  Deleted {deleted_count} defects from cache: {defect_ids}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting cached descriptions: {e}")
            return False
    
    def update_defect_state(self, defect_id: str, state: str) -> bool:
        """
        Update the state field for a specific defect in cache
        Used to mark triaged cancelled defects so they're filtered from insights
        
        Args:
            defect_id: The defect ID to update
            state: The new state value (typically a Jazz/RTC state URL)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE defect_descriptions
                SET state = ?
                WHERE defect_id = ?
            """, (state, str(defect_id)))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating defect state for {defect_id}: {e}")
            return False
    
    def get_all_triaged_defects_from_cache(self, component_names: Optional[List[str]] = None) -> List[Dict]:
        """
        Get all TRIAGED defects from cache for ML training
        This eliminates the need to re-fetch from IBM APIs every week
        
        Args:
            component_names: Optional list of components to filter by
            
        Returns:
            List of triaged defects with descriptions and tags
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all defects that have valid ML tags (test_bug, product_bug, infrastructure_bug)
            if component_names:
                placeholders = ','.join('?' * len(component_names))
                query = f"""
                    SELECT defect_id, description, summary, component, functional_area, state, tags, creation_date, number_builds
                    FROM defect_descriptions
                    WHERE component IN ({placeholders})
                    AND tags IS NOT NULL
                    AND tags != '[]'
                    ORDER BY component, defect_id
                """
                cursor.execute(query, component_names)
            else:
                cursor.execute("""
                    SELECT defect_id, description, summary, component, functional_area, state, tags, creation_date, number_builds
                    FROM defect_descriptions
                    WHERE tags IS NOT NULL
                    AND tags != '[]'
                    ORDER BY component, defect_id
                """)
            
            rows = cursor.fetchall()
            conn.close()
            
            triaged_defects = []
            for row in rows:
                defect_id, description, summary, component, functional_area, state, tags_str, creation_date, number_builds = row
                
                # Parse tags
                tags = json.loads(tags_str) if tags_str else []
                
                # Only include defects with valid ML tags
                tags_lower = [str(tag).lower().strip() for tag in tags]
                has_ml_tag = any(
                    'test' in tag or 'product' in tag or 'infra' in tag or 'infrastructure' in tag
                    for tag in tags_lower
                )
                
                if has_ml_tag:
                    triaged_defects.append({
                        'id': defect_id,
                        'description': description or '',
                        'summary': summary or '',
                        'component': component or '',
                        'functionalArea': functional_area or '',
                        'state': state or '',
                        'triageTags': tags,
                        'creation_date': creation_date or '',
                        'number_builds': number_builds or 0
                    })
            
            logger.info(f"✅ Retrieved {len(triaged_defects)} triaged defects from cache")
            if component_names:
                logger.info(f"   Filtered by {len(component_names)} components")
            
            return triaged_defects
            
        except Exception as e:
            logger.error(f"Error retrieving triaged defects from cache: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def get_all_untriaged_defects(self, component_names: Optional[List[str]] = None) -> List[Dict]:
        """Get all untriaged defects from latest snapshot with full details"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Try daily_snapshots first (has full details from monitored component checks)
            cursor.execute("SELECT MAX(date) FROM daily_snapshots")
            latest_date_daily = cursor.fetchone()[0]
            
            # Also check all_components_snapshots
            cursor.execute("SELECT MAX(date) FROM all_components_snapshots")
            latest_date_all = cursor.fetchone()[0]
            
            all_untriaged = []
            
            # Get from daily_snapshots (monitored components with full details)
            if latest_date_daily:
                if component_names:
                    placeholders = ','.join('?' * len(component_names))
                    query = f"""
                        SELECT component, data
                        FROM daily_snapshots
                        WHERE date = ? AND untriaged > 0 AND component IN ({placeholders})
                        ORDER BY untriaged DESC, component ASC
                    """
                    cursor.execute(query, (latest_date_daily, *component_names))
                else:
                    cursor.execute("""
                        SELECT component, data
                        FROM daily_snapshots
                        WHERE date = ? AND untriaged > 0
                        ORDER BY untriaged DESC, component ASC
                    """, (latest_date_daily,))
                
                rows = cursor.fetchall()
                for component, data_json in rows:
                    data = json.loads(data_json)
                    # The key is 'defects' not 'untriaged_defects' in daily_snapshots
                    untriaged_defects = data.get('defects', [])
                    
                    # Add component name to each defect
                    for defect in untriaged_defects:
                        defect['component'] = component
                        all_untriaged.append(defect)
                
                logger.info(f"✅ Retrieved {len(all_untriaged)} untriaged defects from daily_snapshots ({len(rows)} components)")
            
            # Also check all_components_snapshots for any additional components
            if latest_date_all and component_names:
                # Only check components not already in daily_snapshots
                components_already_fetched = set(d['component'] for d in all_untriaged)
                remaining_components = [c for c in component_names if c not in components_already_fetched]
                
                if remaining_components:
                    placeholders = ','.join('?' * len(remaining_components))
                    query = f"""
                        SELECT component, data
                        FROM all_components_snapshots
                        WHERE date = ? AND untriaged > 0 AND component IN ({placeholders})
                        ORDER BY untriaged DESC, component ASC
                    """
                    cursor.execute(query, (latest_date_all, *remaining_components))
                    
                    rows = cursor.fetchall()
                    for component, data_json in rows:
                        data = json.loads(data_json)
                        # Try both keys for compatibility
                        untriaged_defects = data.get('defects', data.get('untriaged_defects', []))
                        
                        for defect in untriaged_defects:
                            defect['component'] = component
                            all_untriaged.append(defect)
                    
                    if rows:
                        logger.info(f"✅ Retrieved {len(rows)} additional components from all_components_snapshots")
            
            conn.close()
            
            logger.info(f"✅ Total: {len(all_untriaged)} untriaged defects")
            return all_untriaged
            
        except Exception as e:
            logger.error(f"Error retrieving all untriaged defects: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    def get_all_triaged_defects_by_category(self, component_names: Optional[List[str]] = None) -> Dict:
        """
        Get triaged defects from defect_descriptions cache, categorized by tag type
        Returns defects that HAVE triage tags (product_bug, test_bug, infrastructure_bug)
        
        Args:
            component_names: Optional list of component names to filter by
            
        Returns:
            Dict with three lists: product_bugs, infra_bugs, test_bugs
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query defect_descriptions table for defects with triage tags
            # Filter out cancelled/closed/resolved defects (state URLs contain these keywords)
            if component_names:
                placeholders = ','.join('?' * len(component_names))
                query = f"""
                    SELECT defect_id, component, summary, state, tags, functional_area
                    FROM defect_descriptions
                    WHERE component IN ({placeholders})
                    AND (state NOT LIKE '%cancel%' AND state NOT LIKE '%closed%' AND state NOT LIKE '%resolved%')
                    AND (tags LIKE '%test_bug%' OR tags LIKE '%test%' OR tags LIKE '%product_bug%' OR tags LIKE '%product%' OR tags LIKE '%infrastructure_bug%' OR tags LIKE '%infrastructure%' OR tags LIKE '%infra_bug%' OR tags LIKE '%infra%')
                    ORDER BY component ASC, defect_id DESC
                """
                cursor.execute(query, component_names)
            else:
                cursor.execute("""
                    SELECT defect_id, component, summary, state, tags, functional_area
                    FROM defect_descriptions
                    WHERE (state NOT LIKE '%cancel%' AND state NOT LIKE '%closed%' AND state NOT LIKE '%resolved%')
                    AND (tags LIKE '%test_bug%' OR tags LIKE '%test%' OR tags LIKE '%product_bug%' OR tags LIKE '%product%' OR tags LIKE '%infra structure_bug%' OR tags LIKE '%infrastructure%' OR tags LIKE '%infra_bug%' OR tags LIKE '%infra%')
                    ORDER BY component ASC, defect_id DESC
                """)
            
            rows = cursor.fetchall()
            conn.close()
            
            logger.info(f"✅ Retrieved {len(rows)} triaged defects from defect_descriptions")
            
            # Now categorize defects by their triage tags
            product_bugs = []
            infra_bugs = []
            test_bugs = []
            
            for row in rows:
                defect_id, component, summary, state, tags_json, functional_area = row
                
                # Parse tags JSON
                try:
                    tags = json.loads(tags_json) if tags_json else []
                except:
                    tags = []
                
                # Ensure it's an array
                if not isinstance(tags, list):
                    tags = []
                
                # Convert all tags to lowercase strings for comparison
                tags_lower = [str(tag).lower().strip() for tag in tags]
                
                # Check for specific triage tags (same logic as defect_checker.py)
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
                
                # Parse state if it's a URL
                parsed_state = state
                if state and 'oslc/workflows' in state:
                    # Extract state name from URL like: .../commonWorkflow.state.canceled
                    state_parts = state.split('.')
                    if len(state_parts) > 0:
                        parsed_state = state_parts[-1].capitalize()
                
                # Build defect object
                defect = {
                    'id': defect_id,
                    'component': component,
                    'summary': summary,
                    'owner': 'Unknown',  # Not stored in defect_descriptions
                    'state': parsed_state,
                    'functionalArea': functional_area or 'Unknown',
                    'triageTags': tags,
                    'tags': tags
                }
                
                # Categorize by priority: infra_bug > test_bug > product_bug
                if has_infra_bug:
                    infra_bugs.append(defect)
                elif has_test_bug:
                    test_bugs.append(defect)
                elif has_product_bug:
                    product_bugs.append(defect)
            
            logger.info(f"✅ Categorized triaged defects: {len(product_bugs)} product, {len(infra_bugs)} infra, {len(test_bugs)} test")
            
            return {
                "product_bugs": product_bugs,
                "infra_bugs": infra_bugs,
                "test_bugs": test_bugs,
                "total_triaged": len(product_bugs) + len(infra_bugs) + len(test_bugs)
            }
            
        except Exception as e:
            logger.error(f"Error retrieving triaged defects by category: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "product_bugs": [],
                "infra_bugs": [],
                "test_bugs": [],
                "total_triaged": 0
            }
    
    
    def get_component_from_daily_snapshot(self, component: str) -> Optional[Dict]:
        """Get pre-processed component data from daily_snapshots"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest date
            cursor.execute("SELECT MAX(date) FROM daily_snapshots WHERE component = ?", (component,))
            latest_date = cursor.fetchone()[0]
            
            if not latest_date:
                conn.close()
                return None
            
            # Get component data
            cursor.execute("""
                SELECT data
                FROM daily_snapshots
                WHERE date = ? AND component = ?
            """, (latest_date, component))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                data = json.loads(row[0])
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving component from daily snapshot: {e}")
            return None
    
    def get_latest_soe_snapshot(self) -> Optional[Dict]:
        """Get latest SOE Triage snapshot"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest date
            cursor.execute("SELECT MAX(date) FROM soe_snapshots")
            latest_date = cursor.fetchone()[0]
            
            if not latest_date:
                conn.close()
                return None
            
            # Get SOE data
            cursor.execute("""
                SELECT data
                FROM soe_snapshots
                WHERE date = ?
            """, (latest_date,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                data = json.loads(row[0])
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving latest SOE snapshot: {e}")
            return None
    
    def store_component_snapshot_single(self, component: str, data: Dict):
        """
        Store snapshot for a single component refresh
        Updates both all_components_snapshots and daily_snapshots if monitored
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            date = datetime.now().strftime("%Y-%m-%d")
            created_at = datetime.now().isoformat()
            
            # Store in all_components_snapshots
            cursor.execute("""
                INSERT OR REPLACE INTO all_components_snapshots
                (date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data, created_at, is_monitored)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date,
                component,
                data.get("total", 0),
                data.get("untriaged", 0),
                data.get("test_bugs", 0),
                data.get("product_bugs", 0),
                data.get("infra_bugs", 0),
                json.dumps(data),
                created_at,
                0  # Not necessarily monitored
            ))
            
            # Also update daily_snapshots if it exists (for monitored components)
            cursor.execute("""
                SELECT COUNT(*) FROM daily_snapshots WHERE date = ? AND component = ?
            """, (date, component))
            
            if cursor.fetchone()[0] > 0:
                # Component exists in daily_snapshots, update it
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_snapshots
                    (date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date,
                    component,
                    data.get("total", 0),
                    data.get("untriaged", 0),
                    data.get("test_bugs", 0),
                    data.get("product_bugs", 0),
                    data.get("infra_bugs", 0),
                    json.dumps(data),
                    created_at
                ))
                logger.info(f"✅ Updated both all_components_snapshots and daily_snapshots for {component}")
            else:
                logger.info(f"✅ Updated all_components_snapshots for {component}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing component snapshot: {e}")
    
    def store_all_components_snapshot(self, component: str, data: Dict, is_monitored: bool = False):
        """Store snapshot for any component (all 51 components)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            date = datetime.now().strftime("%Y-%m-%d")
            created_at = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT OR REPLACE INTO all_components_snapshots
                (date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data, created_at, is_monitored)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date,
                component,
                data.get("total", 0),
                data.get("untriaged", 0),
                data.get("test_bugs", 0),
                data.get("product_bugs", 0),
                data.get("infra_bugs", 0),
                json.dumps(data),
                created_at,
                1 if is_monitored else 0
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing all components snapshot: {e}")
    
    def get_all_components_data(self, component_names: Optional[List[str]] = None, days: int = 7) -> Dict:
        """Get data for all components or specific components"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            if component_names:
                placeholders = ','.join('?' * len(component_names))
                query = f"""
                    SELECT date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data, is_monitored
                    FROM all_components_snapshots
                    WHERE date >= ? AND component IN ({placeholders})
                    ORDER BY date ASC, component ASC
                """
                cursor.execute(query, (start_date, *component_names))
            else:
                cursor.execute("""
                    SELECT date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data, is_monitored
                    FROM all_components_snapshots
                    WHERE date >= ?
                    ORDER BY date ASC, component ASC
                """, (start_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Format data
            components_data = {
                "dates": [],
                "components": {}
            }
            
            for row in rows:
                date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data_json, is_monitored = row
                
                if date not in components_data["dates"]:
                    components_data["dates"].append(date)
                
                if component not in components_data["components"]:
                    components_data["components"][component] = []
                
                components_data["components"][component].append({
                    "date": date,
                    "total": total,
                    "untriaged": untriaged,
                    "test_bugs": test_bugs,
                    "product_bugs": product_bugs,
                    "infra_bugs": infra_bugs,
                    "is_monitored": bool(is_monitored),
                    "data": json.loads(data_json)
                })
            
            return components_data
            
        except Exception as e:
            logger.error(f"Error getting all components data: {e}")
            return {"dates": [], "components": {}}
    
    def get_latest_all_components_snapshot(self, component_names: Optional[List[str]] = None) -> Optional[Dict]:
        """Get the most recent snapshot for all or specific components"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if component_names:
                placeholders = ','.join('?' * len(component_names))
                query = f"""
                    SELECT date, component, total, untriaged, test_bugs, product_bugs, infra_bugs
                    FROM all_components_snapshots
                    WHERE date = (SELECT MAX(date) FROM all_components_snapshots)
                    AND component IN ({placeholders})
                """
                cursor.execute(query, component_names)
            else:
                cursor.execute("""
                    SELECT date, component, total, untriaged, test_bugs, product_bugs, infra_bugs
                    FROM all_components_snapshots
                    WHERE date = (SELECT MAX(date) FROM all_components_snapshots)
                """)
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
            
            snapshot = {
                "date": rows[0][0],
                "components": {}
            }
            
            for row in rows:
                date, component, total, untriaged, test_bugs, product_bugs, infra_bugs = row
                snapshot["components"][component] = {
                    "total": total,
                    "untriaged": untriaged,
                    "test_bugs": test_bugs,
                    "product_bugs": product_bugs,
                    "infra_bugs": infra_bugs
                }
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error getting latest all components snapshot: {e}")
            return None
    
    def get_team_snapshot_from_cache(self, component_names: List[str]) -> Optional[Dict]:
        """
        Get the most recent snapshot data for team components from all_components_snapshots
        Returns full data including defects with ML predictions and duplicate info
        This is used by team notifications to avoid re-fetching from Build Break Report
        Returns data in format compatible with slack_notifier (components as dict, not list)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if not component_names:
                return None
            
            placeholders = ','.join('?' * len(component_names))
            query = f"""
                SELECT component, data
                FROM all_components_snapshots
                WHERE date = (SELECT MAX(date) FROM all_components_snapshots)
                AND component IN ({placeholders})
            """
            cursor.execute(query, component_names)
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                logger.warning(f"No cached snapshot found for components: {component_names}")
                return None
            
            # Build results structure compatible with slack_notifier
            # Components should be a DICT with component names as keys
            components_dict = {}
            monitored_components = []
            total_defects = 0
            total_untriaged = 0
            
            for component, data_json in rows:
                data = json.loads(data_json)
                
                # Add to components dict (for slack_notifier)
                components_dict[component] = {
                    "component": component,
                    "total": data.get("total", 0),
                    "untriaged": data.get("untriaged", 0),
                    "test_bugs": data.get("test_bugs", 0),
                    "product_bugs": data.get("product_bugs", 0),
                    "infra_bugs": data.get("infra_bugs", 0),
                    "defects": data.get("defects", [])  # Includes ML predictions and duplicate info
                }
                
                # Also add to monitored_components list (for compatibility)
                monitored_components.append(components_dict[component])
                
                total_defects += data.get("total", 0)
                total_untriaged += data.get("untriaged", 0)
            
            results = {
                "components": components_dict,  # Dict format for slack_notifier
                "monitored_components": monitored_components,  # List format for compatibility
                "total_defects": total_defects,
                "total_untriaged": total_untriaged,
                "timestamp": datetime.now().isoformat(),
                "from_cache": True  # Flag to indicate this is from cache
            }
            
            logger.info(f"✅ Retrieved cached snapshot for {len(components_dict)} components")
            return results
            
        except Exception as e:
            logger.error(f"Error getting team snapshot from cache: {e}")
            return None
    
    def store_check_history(self, results: Dict, success: bool, error_message: Optional[str] = None):
        """Store check history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO check_history
                (timestamp, total_defects, total_untriaged, components_checked, success, error_message, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                results.get("total_defects", 0),
                results.get("total_untriaged", 0),
                len(results.get("components", {})),
                1 if success else 0,
                error_message,
                json.dumps(results)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing check history: {e}")
    
    def get_weekly_data(self, days: int = 7) -> Dict:
        """Get data for the last N days from all_components_snapshots (for dashboard)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            # Get component data from all_components_snapshots (background fetch data)
            cursor.execute("""
                SELECT date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data
                FROM all_components_snapshots
                WHERE date >= ?
                ORDER BY date ASC
            """, (start_date,))
            
            component_rows = cursor.fetchall()
            
            # Get SOE data
            cursor.execute("""
                SELECT date, total, data
                FROM soe_snapshots
                WHERE date >= ?
                ORDER BY date ASC
            """, (start_date,))
            
            soe_rows = cursor.fetchall()
            
            conn.close()
            
            # Format data
            weekly_data = {
                "dates": [],
                "components": {},
                "soe_triage": []
            }
            
            # Process component data
            for row in component_rows:
                date, component, total, untriaged, test_bugs, product_bugs, infra_bugs, data_json = row
                
                if date not in weekly_data["dates"]:
                    weekly_data["dates"].append(date)
                
                if component not in weekly_data["components"]:
                    weekly_data["components"][component] = []
                
                weekly_data["components"][component].append({
                    "date": date,
                    "total": total,
                    "untriaged": untriaged,
                    "test_bugs": test_bugs,
                    "product_bugs": product_bugs,
                    "infra_bugs": infra_bugs,
                    "data": json.loads(data_json)
                })
            
            # Process SOE data
            for row in soe_rows:
                date, total, data_json = row
                weekly_data["soe_triage"].append({
                    "date": date,
                    "total": total,
                    "data": json.loads(data_json)
                })
            
            return weekly_data
            
        except Exception as e:
            logger.error(f"Error getting weekly data: {e}")
            return {"dates": [], "components": {}, "soe_triage": []}
    
    def get_latest_snapshot(self) -> Optional[Dict]:
        """Get the most recent snapshot from all_components_snapshots (for dashboard)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use all_components_snapshots table for dashboard (background fetch data)
            cursor.execute("""
                SELECT date, component, total, untriaged, test_bugs, product_bugs, infra_bugs
                FROM all_components_snapshots
                WHERE date = (SELECT MAX(date) FROM all_components_snapshots)
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
            
            snapshot = {
                "date": rows[0][0],
                "components": {}
            }
            
            for row in rows:
                date, component, total, untriaged, test_bugs, product_bugs, infra_bugs = row
                snapshot["components"][component] = {
                    "total": total,
                    "untriaged": untriaged,
                    "test_bugs": test_bugs,
                    "product_bugs": product_bugs,
                    "infra_bugs": infra_bugs
                }
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error getting latest snapshot: {e}")
            return None
    def get_component_history(self, component_name: str, start_date: Optional[str] = None, days: int = 30) -> List[Dict]:
        """Get historical data for a specific component"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if not start_date:
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            cursor.execute("""
                SELECT date, total, untriaged, test_bugs, product_bugs, infra_bugs, data
                FROM all_components_snapshots
                WHERE component = ? AND date >= ?
                ORDER BY date DESC
            """, (component_name, start_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            history = []
            for row in rows:
                date, total, untriaged, test_bugs, product_bugs, infra_bugs, data_json = row
                
                # Parse the JSON data to get individual defects
                defects = []
                if data_json:
                    try:
                        data = json.loads(data_json)
                        defects = data.get('defects', [])
                    except:
                        pass
                
                history.append({
                    'date': date,
                    'total': total,
                    'untriaged': untriaged,
                    'test_bugs': test_bugs,
                    'product_bugs': product_bugs,
                    'infra_bugs': infra_bugs,
                    'defects': defects
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting component history: {e}")
            return []
    
    
    def cleanup_old_data(self, retention_days: int = 90):
        """Remove data older than retention period"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
            
            cursor.execute("DELETE FROM daily_snapshots WHERE date < ?", (cutoff_date,))
            cursor.execute("DELETE FROM soe_snapshots WHERE date < ?", (cutoff_date,))
            cursor.execute("DELETE FROM check_history WHERE timestamp < ?", (cutoff_date,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cleaned up {deleted} old records")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def get_soe_defects(self) -> Dict:
        """Get latest SOE Triage defects"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest SOE snapshot
            cursor.execute("""
                SELECT data, created_at
                FROM soe_snapshots
                ORDER BY date DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                data = json.loads(row[0])
                return {
                    "defects": data.get("defects", []),
                    "last_fetch": row[1],
                    "total": data.get("total", 0)
                }
            else:
                return {
                    "defects": [],
                    "last_fetch": None,
                    "total": 0
                }
                
        except Exception as e:
            logger.error(f"Error getting SOE defects: {e}")
            return {
                "defects": [],
                "last_fetch": None,
                "total": 0
            }

# Made with Bob
