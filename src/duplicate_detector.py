"""
Duplicate Detector Module
Detects if a new defect is similar to existing defects within the same component
Uses text similarity to find potential duplicates
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detects duplicate defects using text similarity"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        """
        Initialize duplicate detector
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider as duplicate
        """
        self.similarity_threshold = similarity_threshold
        self._similarity_cache = {}  # Cache for similarity calculations
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using SequenceMatcher with caching
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        # Normalize texts
        text1_norm = text1.lower().strip()
        text2_norm = text2.lower().strip()
        
        # Create cache key (order-independent)
        cache_key = tuple(sorted([text1_norm, text2_norm]))
        
        # Check cache
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]
        
        # Calculate similarity
        similarity = SequenceMatcher(None, text1_norm, text2_norm).ratio()
        
        # Cache result
        self._similarity_cache[cache_key] = similarity
        
        return similarity
    
    def extract_key_info(self, defect: Dict) -> Tuple[str, str]:
        """
        Extract key information from defect for comparison
        Returns both summary and description for comprehensive matching
        
        Args:
            defect: Defect dictionary
            
        Returns:
            Tuple of (summary_key_info, description)
        """
        summary = str(defect.get('summary', '')).lower()
        description = str(defect.get('description', '')).lower()
        
        # Extract test name (everything after "Test Failure: ")
        if 'test failure:' in summary:
            test_name = summary.split('test failure:', 1)[1].strip()
        else:
            test_name = summary
        
        # Remove build-specific information (dates, build numbers, etc.)
        # Keep only the core test name and error type
        key_parts = []
        
        # Add test class and method name
        if '.' in test_name:
            # Get the last part (method name) and second-to-last (class name)
            parts = test_name.split('.')
            if len(parts) >= 2:
                key_parts.append(parts[-2])  # Class name
                key_parts.append(parts[-1].split(':')[0])  # Method name (before any colon)
        else:
            key_parts.append(test_name)
        
        summary_key = ' '.join(key_parts)
        
        return (summary_key, description)
    
    def find_duplicates(self, new_defect: Dict, existing_defects: List[Dict]) -> List[Tuple[Dict, float]]:
        """
        Find potential duplicates of a new defect among ALL existing defects in component
        Compares summary and description (if available) for accurate duplicate detection
        
        Args:
            new_defect: The new defect to check
            existing_defects: List of ALL existing defects in the same component
            
        Returns:
            List of tuples (defect, similarity_score) for potential duplicates
        """
        try:
            duplicates = []
            
            # Extract key info from new defect
            new_summary_key, new_description = self.extract_key_info(new_defect)
            new_summary_full = str(new_defect.get('summary', '')).lower()
            has_description = bool(new_description.strip())
            
            logger.debug(f"Checking for duplicates of: {new_summary_full[:100]}")
            logger.debug(f"Searching through {len(existing_defects)} existing defects...")
            logger.debug(f"Description available: {has_description}")
            
            for existing in existing_defects:
                # Skip if same defect
                if existing.get('id') == new_defect.get('id'):
                    continue
                
                # Extract key info from existing defect
                existing_summary_key, existing_description = self.extract_key_info(existing)
                existing_summary_full = str(existing.get('summary', '')).lower()
                
                # Calculate similarity on full summary
                summary_similarity = self.calculate_similarity(new_summary_full, existing_summary_full)
                
                # Calculate similarity on key info (test class/method name)
                key_similarity = self.calculate_similarity(new_summary_key, existing_summary_key)
                
                # Calculate similarity based on available data
                if has_description and existing_description.strip():
                    # Both have descriptions: use summary + description + key info
                    description_similarity = self.calculate_similarity(new_description, existing_description)
                    # 40% summary, 40% description, 20% key info
                    similarity = (
                        0.4 * summary_similarity +
                        0.4 * description_similarity +
                        0.2 * key_similarity
                    )
                    
                    # If similarity is above threshold, it's a potential duplicate
                    if similarity >= self.similarity_threshold:
                        duplicates.append((existing, similarity))
                        logger.info(f"  🔄 Found potential duplicate: {existing.get('id')} (similarity: {similarity:.2%}, summary: {summary_similarity:.2%}, desc: {description_similarity:.2%}, key: {key_similarity:.2%})")
                else:
                    # No descriptions: use summary + key info only
                    # 80% summary, 20% key info
                    similarity = (0.8 * summary_similarity) + (0.2 * key_similarity)
                    
                    # If similarity is above threshold, it's a potential duplicate
                    if similarity >= self.similarity_threshold:
                        duplicates.append((existing, similarity))
                        logger.info(f"  🔄 Found potential duplicate: {existing.get('id')} (similarity: {similarity:.2%}, summary: {summary_similarity:.2%}, key: {key_similarity:.2%})")
            
            # Sort by similarity (highest first)
            duplicates.sort(key=lambda x: x[1], reverse=True)
            
            if duplicates:
                logger.info(f"  ✅ Found {len(duplicates)} potential duplicate(s)")
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def check_defect_for_duplicates(self, new_defect: Dict, component_defects: List[Dict]) -> Optional[Dict]:
        """
        Check if a new defect is a duplicate and return duplicate information
        
        Args:
            new_defect: The new untriaged defect
            component_defects: All defects in the same component
            
        Returns:
            Dictionary with duplicate information or None
        """
        try:
            # Find duplicates
            duplicates = self.find_duplicates(new_defect, component_defects)
            
            if not duplicates:
                return None
            
            # Get the best match
            best_match, similarity = duplicates[0]
            
            # Return duplicate information
            return {
                'is_duplicate': True,
                'duplicate_id': best_match.get('id'),
                'duplicate_summary': best_match.get('summary'),
                'duplicate_tags': best_match.get('triageTags', []),
                'similarity': similarity,
                'total_similar': len(duplicates)
            }
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            return None


# Made with Bob