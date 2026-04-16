"""
Insights Analyzer Module
Analyzes defects and provides actionable best practices and recommendations
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import Counter
import re

logger = logging.getLogger(__name__)


class InsightsAnalyzer:
    """Analyzes defects and generates actionable insights"""
    
    def __init__(self, database, defect_checker=None):
        self.database = database
        self.duplicate_detector = None
        self.defect_checker = defect_checker
        
    def set_duplicate_detector(self, detector):
        """Set the duplicate detector instance"""
        self.duplicate_detector = detector
    
    def set_defect_checker(self, checker):
        """Set the defect checker instance for fetching Jazz/RTC data"""
        self.defect_checker = checker
    
    def analyze_component(self, component_name: str, defects: List[Dict]) -> Dict:
        """
        Analyze a component's defects and generate insights
        
        Returns:
            {
                'duplicates': [...],
                'rare_defects': [...],
                'recurring_patterns': [...],
                'recommendations': [...]
            }
        """
        insights = {
            'duplicates': [],
            'rare_defects': [],
            'recurring_patterns': [],
            'recommendations': []
        }
        
        if not defects:
            return insights
        
        logger.info(f"📊 Starting insights analysis for {component_name} with {len(defects)} defects")
        
        # Filter out cancelled defects BEFORE analysis
        # Check state field for cancelled/closed/resolved keywords
        active_defects = []
        cancelled_count = 0
        for defect in defects:
            state = defect.get('state', '')
            is_cancelled = False
            
            if state and isinstance(state, str) and 'jazz/oslc/workflows' in state:
                state_lower = state.lower()
                # Only filter if state URL explicitly contains .canceled or .closed or .resolved
                if '.canceled' in state_lower or '.cancelled' in state_lower or '.closed' in state_lower or '.resolved' in state_lower:
                    is_cancelled = True
                    cancelled_count += 1
                    logger.debug(f"Filtering out cancelled defect {defect.get('id')} (state: {state[:100]}...)")
            
            if not is_cancelled:
                active_defects.append(defect)
        
        if cancelled_count > 0:
            logger.info(f"Analyzing {len(active_defects)} active defects (filtered out {cancelled_count} cancelled)")
        
        # Use active_defects for all analysis
        defects = active_defects
        
        # Analyze duplicates
        insights['duplicates'] = self._find_duplicates(defects)
        logger.info(f"  Found {len(insights['duplicates'])} duplicate groups")
        
        # Analyze rare defects (occurred only once in last 30 days)
        insights['rare_defects'] = self._find_rare_defects(component_name, defects)
        logger.info(f"  Found {len(insights['rare_defects'])} rare defects")
        
        # Analyze recurring patterns
        insights['recurring_patterns'] = self._find_recurring_patterns(defects)
        
        # Generate recommendations
        insights['recommendations'] = self._generate_recommendations(
            component_name, defects, insights
        )
        
        return insights
    
    def _find_duplicates(self, defects: List[Dict]) -> List[Dict]:
        """Find duplicate defects using the same logic as duplicate detection (75% threshold)"""
        duplicates = []
        
        if not self.duplicate_detector:
            return duplicates
        
        # Group defects by similarity using the SAME logic as duplicate detection
        seen = set()
        for i, defect in enumerate(defects):
            if defect['id'] in seen:
                continue
            
            # Use the duplicate detector's find_duplicates method for consistency
            # This uses the same weighted calculation (summary + description + key info)
            similar_matches = self.duplicate_detector.find_duplicates(defect, defects)
            
            similar_defects = []
            for other_defect, similarity in similar_matches:
                other_id = other_defect['id']
                if other_id != defect['id'] and other_id not in seen:
                    similar_defects.append({
                        'id': other_id,
                        'summary': other_defect['summary'],
                        'similarity': round(similarity * 100, 1)
                    })
                    seen.add(other_id)
            
            if similar_defects:
                duplicates.append({
                    'main_defect': {
                        'id': defect['id'],
                        'summary': defect['summary']
                    },
                    'similar_defects': similar_defects,
                    'count': len(similar_defects) + 1
                })
                seen.add(defect['id'])
        
        return duplicates
    
    def _find_rare_defects(self, component_name: str, defects: List[Dict]) -> List[Dict]:
        """Find defects that occurred only once (or never) and are older than 30 days"""
        rare_defects = []
        
        logger.debug(f"🔍 Checking {len(defects)} defects for rare defects (number_builds<=1, age>=30 days)")
        
        try:
            # Find defects with 0 or 1 build AND older than 30 days
            # This identifies defects that appeared once (or never) and never recurred
            for defect in defects:
                defect_id = defect['id']
                # Use the number_builds field (calculated from buildsReported array)
                build_count = defect.get('number_builds', 0)
                creation_date = defect.get('creation_date')
                
                logger.debug(f"  Checking defect {defect_id}: number_builds={build_count}, creation_date={creation_date}")
                
                # MUST have 0 or 1 build (not 2+)
                if build_count <= 1:
                    logger.debug(f"    → Defect {defect_id} has {build_count} build(s), checking age...")
                    # Skip if no creation date (can't determine age)
                    if not creation_date:
                        logger.warning(f"    → Defect {defect_id} has no creation_date, skipping")
                        continue
                    
                    age_info = "old defect"
                    days_old = None
                    
                    # Parse creation date
                    try:
                        # Try different date formats
                        for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                            try:
                                # Clean up the date string
                                clean_date = creation_date.split('+')[0].split('.')[0]
                                if 'T' not in clean_date:
                                    clean_date = creation_date  # It's just a date
                                
                                created_dt = datetime.strptime(clean_date, fmt.replace('.%fZ', '').replace('Z', ''))
                                days_old = (datetime.now() - created_dt).days
                                
                                # Calculate age info
                                if days_old < 7:
                                    age_info = f"{days_old} days old"
                                elif days_old < 30:
                                    weeks_old = days_old // 7
                                    age_info = f"{weeks_old} week{'s' if weeks_old > 1 else ''} old"
                                else:
                                    months_old = days_old // 30
                                    age_info = f"{months_old} month{'s' if months_old > 1 else ''} old"
                                break
                            except ValueError:
                                continue
                    except Exception as e:
                        logger.debug(f"Could not parse creation date for {defect_id}: {e}")
                        continue
                    
                    # Only include if defect is older than 14 days (2 weeks)
                    if days_old is not None and days_old >= 30:
                        logger.info(f"✅ Found rare defect: {defect_id} ({days_old} days old, {build_count} build)")
                        rare_defects.append({
                            'id': defect_id,
                            'summary': defect['summary'],
                            'tag': defect.get('tags', ['unknown'])[0] if defect.get('tags') else 'unknown',
                            'build_count': build_count,
                            'age_info': age_info,
                            'days_old': days_old,
                            'creation_date': creation_date
                        })
                        
                        logger.info(f"    → Added to rare defects: {defect_id}, created: {creation_date}, age: {days_old} days")
                    else:
                        logger.info(f"    → Skipping {defect_id}: only {days_old} days old (needs >= 30)")
                else:
                    if build_count > 1:
                        logger.debug(f"  Skipping {defect_id}: {build_count} builds (needs exactly 1)")
        
        except Exception as e:
            logger.error(f"Error finding rare defects: {e}")
        
        return rare_defects
    
    def _find_recurring_patterns(self, defects: List[Dict]) -> List[Dict]:
        """Find recurring patterns in defect summaries"""
        patterns = []
        
        # Extract common keywords from summaries
        all_words = []
        for defect in defects:
            summary = defect['summary'].lower()
            # Extract meaningful words (ignore common words)
            words = re.findall(r'\b[a-z]{4,}\b', summary)
            all_words.extend(words)
        
        # Find most common words
        word_counts = Counter(all_words)
        common_words = word_counts.most_common(5)
        
        for word, count in common_words:
            if count >= 2:  # Word appears in at least 2 defects
                # Find defects containing this word
                related_defects = [
                    {'id': d['id'], 'summary': d['summary']}
                    for d in defects
                    if word in d['summary'].lower()
                ]
                
                patterns.append({
                    'pattern': word.capitalize(),
                    'count': count,
                    'defects': related_defects[:3]  # Show max 3 examples
                })
        
        return patterns
    
    def _generate_recommendations(
        self, 
        component_name: str, 
        defects: List[Dict],
        insights: Dict
    ) -> List[Dict]:
        """Generate actionable recommendations based on insights"""
        recommendations = []
        
        # Recommendation for duplicates
        if insights['duplicates']:
            total_duplicates = sum(d['count'] for d in insights['duplicates'])
            recommendations.append({
                'type': 'duplicates',
                'priority': 'high',
                'title': f'Found {len(insights["duplicates"])} groups of duplicate defects',
                'description': f'There are {total_duplicates} defects that appear to be duplicates. Consider consolidating them to reduce noise.',
                'action': 'Review and close duplicate defects',
                'icon': '🔄'
            })
        
        # Recommendation for rare defects
        if insights['rare_defects']:
            infra_rare = [d for d in insights['rare_defects'] if 'infrastructure' in d.get('tag', '').lower()]
            if infra_rare:
                recommendations.append({
                    'type': 'rare_defects',
                    'priority': 'medium',
                    'title': f'{len(infra_rare)} infrastructure defects occurred only once',
                    'description': f'These defects have not recurred in the last 30 days. They may be one-time issues that can be closed.',
                    'action': 'Review and consider closing non-recurring infrastructure defects',
                    'icon': '📊'
                })
        
        # Recommendation for recurring patterns
        if insights['recurring_patterns']:
            top_pattern = insights['recurring_patterns'][0]
            recommendations.append({
                'type': 'pattern',
                'priority': 'high',
                'title': f'Recurring pattern detected: "{top_pattern["pattern"]}"',
                'description': f'This pattern appears in {top_pattern["count"]} defects. There may be a common root cause.',
                'action': 'Investigate common root cause for these defects',
                'icon': '🔍'
            })
        
        # Recommendation based on defect count
        if len(defects) > 20:
            recommendations.append({
                'type': 'volume',
                'priority': 'high',
                'title': f'{component_name} has {len(defects)} open defects',
                'description': 'High defect count may indicate systemic issues or need for triage.',
                'action': 'Schedule a triage session to prioritize and close stale defects',
                'icon': '⚠️'
            })
        
        # Recommendation for untriaged defects
        untriaged = [d for d in defects if d.get('owner') == 'Unassigned']
        if len(untriaged) > 5:
            recommendations.append({
                'type': 'untriaged',
                'priority': 'medium',
                'title': f'{len(untriaged)} defects are unassigned',
                'description': 'Unassigned defects may be overlooked. Assign owners for better tracking.',
                'action': 'Assign owners to untriaged defects',
                'icon': '👤'
            })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return recommendations
    
    def get_component_summary(self, component_name: str) -> Dict:
        """Get a summary of insights for a component"""
        try:
            # Get current defects for the component
            snapshot = self.database.get_latest_snapshot()
            if not snapshot or component_name not in snapshot.get('components', {}):
                return {'error': 'Component not found'}
            
            component_data = snapshot['components'][component_name]
            
            # Get detailed defects (this would need to be implemented in database)
            # For now, return basic summary
            return {
                'component': component_name,
                'total_defects': component_data.get('total', 0),
                'untriaged': component_data.get('untriaged', 0),
                'by_type': {
                    'test_bugs': component_data.get('test_bugs', 0),
                    'product_bugs': component_data.get('product_bugs', 0),
                    'infra_bugs': component_data.get('infra_bugs', 0)
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting component summary: {e}")
            return {'error': str(e)}

# Made with Bob
