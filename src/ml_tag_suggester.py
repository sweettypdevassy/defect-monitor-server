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
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, accuracy_score
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
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
                logger.info(f"✅ Loaded pre-trained model from {self.model_path}")
                logger.info(f"   Training accuracy: {self.training_stats.get('accuracy', 'N/A')}")
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
        """Extract and combine text features from defect"""
        # Combine multiple fields into one text for training
        summary = str(defect.get('summary', '')).lower()
        description = str(defect.get('description', '')).lower()
        functional_area = str(defect.get('functionalArea', '')).lower()
        
        # Give equal weight to all three features
        # Description contains crucial error information (e.g., "Connection refused")
        # Summary contains test name
        # Functional area contains component context
        text = f"{summary} {description} {functional_area}"
        return text
    
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
            
            # Remove duplicates based on defect ID
            seen_ids = set()
            unique_training_data = []
            for defect in all_training_data:
                defect_id = defect.get('id')
                if defect_id and defect_id not in seen_ids:
                    seen_ids.add(defect_id)
                    unique_training_data.append(defect)
            
            logger.info(f"🎓 Incremental training: {len(previous_training_data)} old + {len(triaged_defects)} new = {len(unique_training_data)} total unique samples")
            
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
            
            # Check if we can use stratified split (need at least 2 samples per class)
            min_class_count = min(tag_counts.values())
            
            # Split data for validation
            try:
                # Try stratified split first
                X_train, X_test, y_train, y_test = train_test_split(
                    X_texts, y_labels, test_size=0.2, random_state=42, stratify=y_labels
                )
            except ValueError:
                # Fall back to random split if stratification fails
                logger.warning(f"⚠️ Cannot use stratified split (some classes have <2 samples), using random split")
                X_train, X_test, y_train, y_test = train_test_split(
                    X_texts, y_labels, test_size=0.2, random_state=42
                )
            
            # Create ML pipeline: TF-IDF + Naive Bayes
            self.model = Pipeline([
                ('tfidf', TfidfVectorizer(
                    max_features=1000,
                    ngram_range=(1, 2),  # Use unigrams and bigrams
                    min_df=2,  # Ignore terms that appear in less than 2 documents
                    stop_words='english'
                )),
                ('classifier', MultinomialNB(alpha=0.1))
            ])
            
            # Train the model
            logger.info("🔧 Training Naive Bayes classifier with TF-IDF features...")
            self.model.fit(X_train, y_train)
            
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