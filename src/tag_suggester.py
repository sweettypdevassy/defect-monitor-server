"""
Tag Suggester Module
Uses machine learning to suggest triage tags for untriaged defects
Based on historical triaged defects
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class TagSuggester:
    """Suggests triage tags for defects using ML-based classification"""
    
    def __init__(self):
        self.trained = False
        self.training_data = []
        self.feature_keywords = {
            'test_bug': [
                'test failure', 'test', 'junit', 'fat', 'bucket', 'testcase',
                'assertion', 'expected', 'actual', 'timeout', 'intermittent',
                'flaky', 'sporadic', 'random failure', 'test infrastructure'
            ],
            'product_bug': [
                'npe', 'nullpointerexception', 'exception', 'error', 'crash',
                'hang', 'deadlock', 'memory leak', 'performance', 'regression',
                'functionality', 'feature', 'api', 'behavior', 'incorrect'
            ],
            'infrastructure_bug': [
                'infrastructure', 'build', 'environment', 'network', 'timeout',
                'connection', 'setup', 'configuration', 'deployment', 'ci/cd',
                'jenkins', 'docker', 'kubernetes', 'server', 'machine'
            ]
        }
        
        # Weights for different features
        self.weights = {
            'summary': 3.0,      # Summary is most important
            'description': 1.5,  # Description has medium weight
            'functional_area': 2.0,  # Functional area is important
            'state': 0.5         # State has low weight
        }
    
    def train_from_defects(self, triaged_defects: List[Dict]) -> bool:
        """
        Train the suggester using historical triaged defects
        
        Args:
            triaged_defects: List of defects with triage tags
            
        Returns:
            True if training successful
        """
        try:
            logger.info(f"🎓 Training tag suggester with {len(triaged_defects)} triaged defects...")
            
            self.training_data = []
            tag_counts = Counter()
            
            for defect in triaged_defects:
                triage_tags = defect.get('triageTags', [])
                if not triage_tags:
                    continue
                
                # Normalize tags
                tags_lower = [str(tag).lower().strip() for tag in triage_tags]
                
                # Determine primary tag
                primary_tag = self._determine_primary_tag(tags_lower)
                if not primary_tag:
                    continue
                
                # Extract features
                features = self._extract_features(defect)
                
                self.training_data.append({
                    'features': features,
                    'tag': primary_tag,
                    'defect_id': defect.get('id', 'unknown')
                })
                
                tag_counts[primary_tag] += 1
            
            self.trained = len(self.training_data) > 0
            
            if self.trained:
                logger.info(f"✅ Training complete: {len(self.training_data)} examples")
                logger.info(f"   Tag distribution: {dict(tag_counts)}")
            else:
                logger.warning("⚠️ No training data available")
            
            return self.trained
            
        except Exception as e:
            logger.error(f"Error training tag suggester: {e}")
            return False
    
    def _determine_primary_tag(self, tags_lower: List[str]) -> Optional[str]:
        """Determine the primary triage tag from a list of tags"""
        # Priority order: infrastructure > test > product
        if any('infra' in tag or 'infrastructure' in tag for tag in tags_lower):
            return 'infrastructure_bug'
        elif any('test' in tag for tag in tags_lower):
            return 'test_bug'
        elif any('product' in tag for tag in tags_lower):
            return 'product_bug'
        return None
    
    def _extract_features(self, defect: Dict) -> Dict[str, str]:
        """Extract relevant features from a defect"""
        return {
            'summary': str(defect.get('summary', '')).lower(),
            'description': str(defect.get('description', '')).lower(),
            'functional_area': str(defect.get('functionalArea', '')).lower(),
            'state': str(defect.get('state', '')).lower(),
            'owner': str(defect.get('owner', '')).lower()
        }
    
    def suggest_tag(self, defect: Dict) -> Tuple[str, float, str]:
        """
        Suggest a triage tag for an untriaged defect
        
        Args:
            defect: Defect dictionary
            
        Returns:
            Tuple of (suggested_tag, confidence, reasoning)
        """
        if not self.trained:
            return ('unknown', 0.0, 'Model not trained')
        
        try:
            # Extract features from the defect
            features = self._extract_features(defect)
            
            # Calculate scores for each tag type
            scores = {
                'test_bug': 0.0,
                'product_bug': 0.0,
                'infrastructure_bug': 0.0
            }
            
            # Keyword-based scoring
            for tag_type, keywords in self.feature_keywords.items():
                for feature_name, feature_value in features.items():
                    if not feature_value:
                        continue
                    
                    weight = self.weights.get(feature_name, 1.0)
                    
                    for keyword in keywords:
                        if keyword in feature_value:
                            scores[tag_type] += weight
            
            # Find best match
            if max(scores.values()) == 0:
                return ('test_bug', 0.3, 'Default suggestion (no strong indicators)')
            
            best_tag = max(scores, key=scores.get)
            total_score = sum(scores.values())
            confidence = scores[best_tag] / total_score if total_score > 0 else 0.0
            
            # Generate reasoning
            reasoning = self._generate_reasoning(defect, best_tag, features)
            
            logger.debug(f"Defect {defect.get('id')}: Suggested {best_tag} (confidence: {confidence:.2f})")
            
            return (best_tag, confidence, reasoning)
            
        except Exception as e:
            logger.error(f"Error suggesting tag: {e}")
            return ('unknown', 0.0, f'Error: {str(e)}')
    
    def _generate_reasoning(self, defect: Dict, suggested_tag: str, features: Dict) -> str:
        """Generate human-readable reasoning for the suggestion"""
        summary = defect.get('summary', '')
        
        # Find matching keywords
        matching_keywords = []
        for keyword in self.feature_keywords.get(suggested_tag, []):
            if keyword in summary.lower():
                matching_keywords.append(keyword)
        
        if matching_keywords:
            keywords_str = ', '.join(matching_keywords[:3])
            return f"Keywords: {keywords_str}"
        
        return "Based on pattern analysis"
    
    def suggest_tags_batch(self, defects: List[Dict]) -> Dict[str, Tuple[str, float, str]]:
        """
        Suggest tags for multiple defects
        
        Args:
            defects: List of defect dictionaries
            
        Returns:
            Dictionary mapping defect_id to (tag, confidence, reasoning)
        """
        suggestions = {}
        
        for defect in defects:
            defect_id = defect.get('id', 'unknown')
            suggestions[defect_id] = self.suggest_tag(defect)
        
        return suggestions
    
    def get_training_stats(self) -> Dict:
        """Get statistics about the training data"""
        if not self.trained:
            return {
                'trained': False,
                'total_examples': 0,
                'tag_distribution': {}
            }
        
        tag_counts = Counter(item['tag'] for item in self.training_data)
        
        return {
            'trained': True,
            'total_examples': len(self.training_data),
            'tag_distribution': dict(tag_counts)
        }


# Made with Bob