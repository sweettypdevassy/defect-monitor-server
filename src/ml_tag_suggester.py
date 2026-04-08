"""
ML-Based Tag Suggester Module
Uses scikit-learn to train a real machine learning model on historical triaged defects
"""

import logging
import pickle
import os
from typing import Dict, List, Optional, Tuple
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import classification_report, accuracy_score
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    import re
    ML_AVAILABLE = True
    SMOTE_AVAILABLE = True
except ImportError as e:
    if 'imblearn' in str(e):
        ML_AVAILABLE = True
        SMOTE_AVAILABLE = False
        logger.warning("⚠️ imbalanced-learn not installed. Install with: pip install imbalanced-learn")
        logger.warning("   Continuing without SMOTE (accuracy may be lower)")
    else:
        ML_AVAILABLE = False
        SMOTE_AVAILABLE = False
        logger.warning("⚠️ scikit-learn not installed. Install with: pip install scikit-learn")


class MLTagSuggester:
    """ML-based tag suggester using scikit-learn"""
    
    def __init__(self, model_path: str = "data/tag_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.trained = False
        self.tag_mapping = {
            'test_bug': 0,
            'product_bug': 1,
            'infrastructure_bug': 2
        }
        self.reverse_tag_mapping = {v: k for k, v in self.tag_mapping.items()}
        self.training_stats = {}
        
        if not ML_AVAILABLE:
            logger.error("❌ scikit-learn not available. Cannot use ML-based suggestions.")
            return
        
        # Try to load existing model
        self._load_model()
    
    def _load_model(self) -> bool:
        """Load pre-trained model from disk"""
        if not ML_AVAILABLE:
            return False
        
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data['model']
                    self.training_stats = data.get('stats', {})
                self.trained = True
                logger.info(f"✅ Loaded ML model: {self.training_stats.get('accuracy', 'N/A')} accuracy")
                return True
        except Exception as e:
            logger.warning(f"Could not load model: {e}")
        
        return False
    
    def _save_model(self, training_data: List[Dict] = None) -> bool:
        """
        Save trained model to disk with training data for incremental learning
        
        Args:
            training_data: Optional training data to save with model
        """
        if not ML_AVAILABLE or not self.model:
            return False
        
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            data = {
                'model': self.model,
                'stats': self.training_stats,
                'training_data': training_data or []  # Store training data for incremental learning
            }
            with open(self.model_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Saved trained model to {self.model_path}")
            if training_data:
                logger.info(f"   Stored {len(training_data)} training samples for incremental learning")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
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
    
    def _extract_text_features(self, defect: Dict) -> str:
        """Extract and combine text features from defect - SIMPLE VERSION"""
        # Keep it simple - just combine the text fields
        # Random Forest will learn the patterns from the raw text
        summary = str(defect.get('summary', '')).lower()
        description = str(defect.get('description', '')).lower()
        functional_area = str(defect.get('functionalArea', '')).lower()
        
        # Combine all text - description is most important (has error details)
        # But include all fields for context
        text = f"{description} {summary} {functional_area}"
        return text.strip()
    
    def train_from_defects(self, triaged_defects: List[Dict], min_samples: int = 10, incremental: bool = True) -> bool:
        """
        Train ML model using historical triaged defects with incremental learning
        
        Args:
            triaged_defects: List of NEW defects with triage tags
            min_samples: Minimum samples needed per class
            incremental: If True, load and combine with previous training data
            
        Returns:
            True if training successful
        """
        if not ML_AVAILABLE:
            logger.error("❌ Cannot train: scikit-learn not installed")
            return False
        
        try:
            # INCREMENTAL LEARNING: Load previous training data if it exists
            previous_training_data = []
            if incremental and os.path.exists(self.model_path):
                try:
                    with open(self.model_path, 'rb') as f:
                        data = pickle.load(f)
                        previous_training_data = data.get('training_data', [])
                    
                    if previous_training_data:
                        logger.info(f"📚 Loaded {len(previous_training_data)} previous training samples")
                except Exception as e:
                    logger.warning(f"Could not load previous training data: {e}")
            
            # Combine old and new training data
            all_training_data = previous_training_data + triaged_defects
            
            # Remove duplicates based on defect ID (normalize to string for comparison)
            seen_ids = set()
            unique_training_data = []
            duplicates_removed = 0
            
            for defect in all_training_data:
                defect_id = defect.get('id')
                if defect_id:
                    # Normalize ID to string for consistent comparison
                    normalized_id = str(defect_id)
                    if normalized_id not in seen_ids:
                        seen_ids.add(normalized_id)
                        unique_training_data.append(defect)
                    else:
                        duplicates_removed += 1
            
            logger.info(f"🎓 Incremental training: {len(previous_training_data)} old + {len(triaged_defects)} new = {len(unique_training_data)} total unique samples")
            if duplicates_removed > 0:
                logger.info(f"   🗑️  Removed {duplicates_removed} duplicate defects")
            
            # Prepare training data from combined dataset
            X_texts = []
            y_labels = []
            tag_counts = Counter()
            
            for defect in unique_training_data:
                triage_tags = defect.get('triageTags', [])
                if not triage_tags:
                    continue
                
                # Normalize tags
                tags_lower = [str(tag).lower().strip() for tag in triage_tags]
                
                # Determine primary tag
                primary_tag = self._determine_primary_tag(tags_lower)
                if not primary_tag or primary_tag not in self.tag_mapping:
                    continue
                
                # Extract text features
                text = self._extract_text_features(defect)
                if not text.strip():
                    continue
                
                X_texts.append(text)
                y_labels.append(self.tag_mapping[primary_tag])
                tag_counts[primary_tag] += 1
            
            if len(X_texts) < min_samples:
                logger.warning(f"⚠️ Not enough training data: {len(X_texts)} samples (need {min_samples})")
                return False
            
            # Check if we have samples for all classes
            if len(tag_counts) < 2:
                logger.warning(f"⚠️ Need at least 2 different tag types for training")
                return False
            
            logger.info(f"📊 Training data distribution: {dict(tag_counts)}")
            
            # Check if we can use balanced test set (10 samples per class)
            min_class_count = min(tag_counts.values())
            samples_per_class = 10
            
            # Split data for validation
            if min_class_count >= samples_per_class + 2:  # Need at least 12 samples per class
                # Use balanced test set: 10 samples from each class
                logger.info(f"📊 Using balanced test set: {samples_per_class} samples per class")
                
                # Separate data by class
                X_by_class = {tag: [] for tag in self.tag_mapping.values()}
                y_by_class = {tag: [] for tag in self.tag_mapping.values()}
                
                for x, y in zip(X_texts, y_labels):
                    X_by_class[y].append(x)
                    y_by_class[y].append(y)
                
                # Take 10 samples from each class for testing
                X_test = []
                y_test = []
                X_train = []
                y_train = []
                
                for tag in self.tag_mapping.values():
                    # Use RANDOM selection for diverse test set
                    # This ensures test set includes defects from different components
                    import random
                    indices = list(range(len(X_by_class[tag])))
                    
                    # Shuffle indices to get random samples
                    random.seed(42)  # Fixed seed for reproducibility
                    random.shuffle(indices)
                    
                    # Test: Random 10 samples from shuffled indices
                    test_indices = indices[:samples_per_class]
                    train_indices = indices[samples_per_class:]
                    
                    X_test.extend([X_by_class[tag][i] for i in test_indices])
                    y_test.extend([y_by_class[tag][i] for i in test_indices])
                    X_train.extend([X_by_class[tag][i] for i in train_indices])
                    y_train.extend([y_by_class[tag][i] for i in train_indices])
                
                logger.info(f"   Test set: {len(X_test)} samples ({samples_per_class} per class)")
                logger.info(f"   Train set: {len(X_train)} samples")
            else:
                # Fall back to stratified split if not enough samples
                logger.info(f"⚠️ Not enough samples for balanced test set (need {samples_per_class+2} per class)")
                logger.info(f"   Using stratified 80/20 split instead")
                try:
                    X_train, X_test, y_train, y_test = train_test_split(
                        X_texts, y_labels, test_size=0.2, random_state=42, stratify=y_labels
                    )
                except ValueError:
                    logger.warning(f"⚠️ Cannot use stratified split, using random split")
                    X_train, X_test, y_train, y_test = train_test_split(
                        X_texts, y_labels, test_size=0.2, random_state=42
                    )
            
            # Don't use SMOTE - it creates unrealistic synthetic samples
            # Instead: optimize Random Forest with careful hyperparameters
            logger.info("🔧 Building optimized Random Forest classifier...")
            logger.info("   Using sample_weight to handle class imbalance naturally")
            
            # Calculate sample weights to give more importance to minority classes
            class_counts = Counter(y_train)
            total_samples = len(y_train)
            
            # Weight inversely proportional to class frequency
            class_weights = {cls: total_samples / (len(class_counts) * count)
                           for cls, count in class_counts.items()}
            
            # Create sample weights array
            sample_weights = np.array([class_weights[y] for y in y_train])
            
            logger.info(f"   Class distribution: {dict(class_counts)}")
            logger.info(f"   Class weights: {class_weights}")
            
            self.model = Pipeline([
                ('tfidf', TfidfVectorizer(
                    max_features=3000,  # Reduced to focus on most important terms
                    ngram_range=(1, 2),  # Unigrams and bigrams
                    min_df=3,  # More conservative - need at least 3 occurrences
                    max_df=0.80,  # Filter common terms more aggressively
                    stop_words='english',
                    sublinear_tf=True,
                    norm='l2'  # L2 normalization
                )),
                ('classifier', RandomForestClassifier(
                    n_estimators=400,  # More trees for stability
                    max_depth=12,  # Shallower trees to prevent overfitting
                    min_samples_split=10,  # Require more samples to split
                    min_samples_leaf=4,  # Require more samples in leaves
                    max_features='log2',  # Use log2 of features (more conservative)
                    bootstrap=True,
                    oob_score=True,
                    random_state=42,
                    n_jobs=-1,
                    class_weight=None,  # We use sample_weight instead
                    verbose=0,
                    max_samples=0.8  # Use 80% of samples per tree (regularization)
                ))
            ])
            
            logger.info("🔧 Training Random Forest (400 trees) with sample weighting...")
            self.model.fit(X_train, y_train, classifier__sample_weight=sample_weights)
            
            # Log OOB score
            if hasattr(self.model.named_steps['classifier'], 'oob_score_'):
                oob_score = self.model.named_steps['classifier'].oob_score_
                logger.info(f"   Out-of-bag score: {oob_score:.2%}")
            
            # Evaluate on test set
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            logger.info(f"✅ Model trained successfully!")
            logger.info(f"   Training samples: {len(X_train)}")
            logger.info(f"   Test samples: {len(X_test)}")
            logger.info(f"   Accuracy: {accuracy:.2%}")
            
            # Store training stats
            self.training_stats = {
                'accuracy': f"{accuracy:.2%}",
                'total_samples': len(X_texts),
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'tag_distribution': dict(tag_counts)
            }
            
            # Print detailed classification report
            # Only include classes that are actually in the test set
            unique_labels = sorted(set(y_test) | set(y_pred))
            target_names = [self.reverse_tag_mapping[i] for i in unique_labels]
            report = classification_report(y_test, y_pred, labels=unique_labels, target_names=target_names, zero_division=0)
            logger.info(f"\n📈 Classification Report:\n{report}")
            
            self.trained = True
            
            # Save model WITH training data for incremental learning
            self._save_model(training_data=unique_training_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error training ML model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def suggest_tag(self, defect: Dict) -> Tuple[str, float, str]:
        """
        Suggest a triage tag for an untriaged defect using ML model
        
        Args:
            defect: Defect dictionary
            
        Returns:
            Tuple of (suggested_tag, confidence, reasoning)
        """
        if not ML_AVAILABLE:
            return ('unknown', 0.0, 'ML libraries not available')
        
        if not self.trained or not self.model:
            return ('unknown', 0.0, 'Model not trained')
        
        try:
            # Extract text features
            text = self._extract_text_features(defect)
            
            if not text.strip():
                return ('unknown', 0.0, 'No text features available')
            
            # Predict tag
            predicted_label = self.model.predict([text])[0]
            predicted_tag = self.reverse_tag_mapping[predicted_label]
            
            # Get probability scores for all classes
            probabilities = self.model.predict_proba([text])[0]
            confidence = float(probabilities[predicted_label])
            
            # Generate reasoning
            reasoning = self._generate_reasoning(defect, predicted_tag, probabilities)
            
            logger.debug(f"Defect {defect.get('id')}: Predicted {predicted_tag} (confidence: {confidence:.2f})")
            
            return (predicted_tag, confidence, reasoning)
            
        except Exception as e:
            logger.error(f"Error suggesting tag: {e}")
            return ('unknown', 0.0, f'Error: {str(e)}')
    
    def _generate_reasoning(self, defect: Dict, predicted_tag: str, probabilities: np.ndarray) -> str:
        """Generate human-readable reasoning for the prediction"""
        # Get top features from TF-IDF if available
        summary = defect.get('summary', '')[:100]  # First 100 chars
        
        # Format probabilities for all classes
        prob_str = ", ".join([
            f"{self.reverse_tag_mapping[i].replace('_', ' ').title()}: {prob:.0%}"
            for i, prob in enumerate(probabilities)
        ])
        
        return f"ML prediction based on text analysis ({prob_str})"
    
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
        """Get statistics about the trained model"""
        if not self.trained:
            return {
                'trained': False,
                'ml_available': ML_AVAILABLE
            }
        
        return {
            'trained': True,
            'ml_available': ML_AVAILABLE,
            **self.training_stats
        }


# Made with Bob