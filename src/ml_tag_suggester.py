"""
ML-Based Tag Suggester Module
Uses scikit-learn to train a real machine learning model on historical triaged defects
Enhanced with better feature engineering and ensemble methods for 60+ accuracy
"""

import logging
import pickle
import os
from typing import Dict, List, Optional, Tuple
from collections import Counter
import numpy as np
import re

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier, ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
    from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
    from sklearn.preprocessing import StandardScaler
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    ML_AVAILABLE = True
    SMOTE_AVAILABLE = True
    
    # Try to import advanced gradient boosting libraries
    try:
        from xgboost import XGBClassifier
        XGBOOST_AVAILABLE = True
    except ImportError:
        XGBOOST_AVAILABLE = False
        logger.info("ℹ️  XGBoost not available. Install with: pip install xgboost")
    
    try:
        from lightgbm import LGBMClassifier
        LIGHTGBM_AVAILABLE = True
    except ImportError:
        LIGHTGBM_AVAILABLE = False
        logger.info("ℹ️  LightGBM not available. Install with: pip install lightgbm")
    
    try:
        from catboost import CatBoostClassifier
        CATBOOST_AVAILABLE = True
    except ImportError:
        CATBOOST_AVAILABLE = False
        logger.info("ℹ️  CatBoost not available. Install with: pip install catboost")
        
except ImportError as e:
    if 'imblearn' in str(e):
        ML_AVAILABLE = True
        SMOTE_AVAILABLE = False
        XGBOOST_AVAILABLE = False
        LIGHTGBM_AVAILABLE = False
        CATBOOST_AVAILABLE = False
        logger.warning("⚠️ imbalanced-learn not installed. Install with: pip install imbalanced-learn")
        logger.warning("   Continuing without SMOTE (accuracy may be lower)")
    else:
        ML_AVAILABLE = False
        SMOTE_AVAILABLE = False
        XGBOOST_AVAILABLE = False
        LIGHTGBM_AVAILABLE = False
        CATBOOST_AVAILABLE = False
        logger.warning("⚠️ scikit-learn not installed. Install with: pip install scikit-learn")


class MLTagSuggester:
    """ML-based tag suggester using scikit-learn"""
    
    def __init__(self, model_path: str = "data/tag_model.pkl", test_set_path: str = "data/test_set.pkl"):
        self.model_path = model_path
        self.test_set_path = test_set_path
        self.model = None
        self.trained = False
        self.tag_mapping = {
            'test_bug': 0,
            'product_bug': 1,
            'infrastructure_bug': 2
        }
        self.reverse_tag_mapping = {v: k for k, v in self.tag_mapping.items()}
        self.training_stats = {}
        self.fixed_test_set = None  # Fixed test set for unbiased evaluation
        self.validation_set_age = 0  # Track how old validation set is (in weeks)
        
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
                    self.validation_set_age = data.get('validation_set_age', 0)
                self.trained = True
                logger.info(f"✅ Loaded ML model: {self.training_stats.get('accuracy', 'N/A')} accuracy")
                logger.info(f"   Validation set age: {self.validation_set_age} weeks")
                return True
        except Exception as e:
            logger.warning(f"Could not load model: {e}")
        
        # Try to load fixed test set
        self._load_test_set()
        
        return False
    
    def _load_test_set(self) -> bool:
        """Load fixed test set from disk"""
        if not ML_AVAILABLE:
            return False
        
        try:
            if os.path.exists(self.test_set_path):
                with open(self.test_set_path, 'rb') as f:
                    self.fixed_test_set = pickle.load(f)
                logger.info(f"✅ Loaded fixed test set: {len(self.fixed_test_set)} samples")
                return True
        except Exception as e:
            logger.warning(f"Could not load test set: {e}")
        
        return False
    
    def _save_test_set(self, test_data: List[Dict]) -> bool:
        """Save fixed test set to disk"""
        if not ML_AVAILABLE:
            return False
        
        try:
            os.makedirs(os.path.dirname(self.test_set_path), exist_ok=True)
            with open(self.test_set_path, 'wb') as f:
                pickle.dump(test_data, f)
            logger.info(f"✅ Saved fixed test set: {len(test_data)} samples")
            return True
        except Exception as e:
            logger.error(f"Error saving test set: {e}")
            return False
    
    def _save_model(self, training_data: Optional[List[Dict]] = None) -> bool:
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
                'training_data': training_data or [],  # Store training data for incremental learning
                'validation_set_age': self.validation_set_age  # Track validation set age
            }
            with open(self.model_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Saved trained model to {self.model_path}")
            if training_data:
                logger.info(f"   Stored {len(training_data)} training samples for incremental learning")
            logger.info(f"   Validation set age: {self.validation_set_age} weeks")
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
    
    def _extract_enhanced_features(self, defect: Dict) -> str:
        """
        Extract enhanced text features with advanced feature engineering
        
        Uses: Description (3x), Summary (1x), Functional Area (1x), Stack Trace Features (1x)
        Description has highest weight as it contains the most diagnostic information
        """
        # Get raw text
        description = str(defect.get('description', '')).lower()
        summary = str(defect.get('summary', '')).lower()
        functional_area = str(defect.get('functionalArea', '')).lower()
        
        # Clean and preprocess text
        description = self._preprocess_text(description)
        summary = self._preprocess_text(summary)
        
        # Remove misleading patterns from summary
        summary = re.sub(r'\btest\s+failure\b', '', summary)
        summary = re.sub(r'\bfailed\s+test\b', '', summary)
        
        # Extract advanced features
        error_keywords = self._extract_error_keywords(description)
        stack_features = self._extract_stack_trace_features(description)
        
        # Combine with intelligent weighting
        # Description gets 3x weight as it contains the most diagnostic information
        combined = (
            f"{description} {description} {description} "  # 3x weight (increased from 2x)
            f"{error_keywords} {error_keywords} "  # 2x weight for strong signals
            f"{stack_features} "  # 1x weight
            f"{summary} "  # 1x weight
            f"{functional_area}"  # 1x weight
        )
        
        return combined.strip()
    
    def _preprocess_text(self, text: str) -> str:
        """Advanced text preprocessing"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', ' url ', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', ' email ', text)
        
        # Remove file paths (but keep error indicators)
        text = re.sub(r'[/\\][\w/\\.-]+', ' filepath ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep important ones
        text = re.sub(r'[^\w\s\-_.:()]', ' ', text)
        
        return text.strip()
    
    def _extract_error_keywords(self, text: str) -> str:
        """Extract domain-specific error keywords - removed infrastructure bias"""
        # Return empty string - let ML learn patterns from training data
        return ''
    
    def _extract_stack_trace_features(self, text: str) -> str:
        """Extract stack trace patterns"""
        features = []
        
        # Exception types
        exceptions = re.findall(r'(\w+exception|\w+error)', text)
        if exceptions:
            unique_ex = list(dict.fromkeys(exceptions))[:2]
            features.extend([f'ex_{ex}' for ex in unique_ex])
        
        # File extensions
        if re.search(r'\.java\b', text):
            features.append('java_file')
        
        # Line numbers indicate code issues
        if re.search(r'line\s+\d+|:\d+:', text):
            features.append('has_line_num')
        
        return ' '.join(features)
    
    
    def _extract_text_features(self, defect: Dict) -> str:
        """Wrapper for backward compatibility"""
        return self._extract_enhanced_features(defect)
    
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
            
            # ============================================================================
            # IMPROVED STRATEGY: Separate Validation and Test Sets
            # ============================================================================
            # 1. Fixed Test Set (~100 defects, 30-40 per class) - NEVER changes
            # 2. Validation Set (~100 defects, 30-40 per class) - Refreshes monthly
            # 3. Training Set - All remaining defects
            # ============================================================================
            
            min_class_count = min(tag_counts.values())
            
            # Step 1: Load or create FIXED TEST SET (only once)
            if self.fixed_test_set is None:
                self._load_test_set()
            
            # Separate data by class for stratified splitting
            X_by_class = {tag: [] for tag in self.tag_mapping.values()}
            y_by_class = {tag: [] for tag in self.tag_mapping.values()}
            defect_by_class = {tag: [] for tag in self.tag_mapping.values()}
            
            for x, y, defect in zip(X_texts, y_labels, unique_training_data):
                X_by_class[y].append(x)
                y_by_class[y].append(y)
                defect_by_class[y].append(defect)
            
            # Step 2: Create or use FIXED TEST SET
            if self.fixed_test_set is None and min_class_count >= 70:
                # Create fixed test set: 30-40 samples per class (~100 total)
                test_samples_per_class = min(40, min_class_count // 3)
                logger.info(f"🎯 Creating FIXED TEST SET: {test_samples_per_class} samples per class")
                
                X_test_fixed = []
                y_test_fixed = []
                test_defects = []
                
                import random
                random.seed(42)  # Fixed seed for test set only
                
                for tag in self.tag_mapping.values():
                    indices = list(range(len(X_by_class[tag])))
                    random.shuffle(indices)
                    
                    # Reserve for fixed test set
                    test_indices = indices[:test_samples_per_class]
                    X_test_fixed.extend([X_by_class[tag][i] for i in test_indices])
                    y_test_fixed.extend([y_by_class[tag][i] for i in test_indices])
                    test_defects.extend([defect_by_class[tag][i] for i in test_indices])
                    
                    # Remove from available data
                    for idx in sorted(test_indices, reverse=True):
                        X_by_class[tag].pop(idx)
                        y_by_class[tag].pop(idx)
                        defect_by_class[tag].pop(idx)
                
                self.fixed_test_set = {
                    'X': X_test_fixed,
                    'y': y_test_fixed,
                    'defects': test_defects
                }
                self._save_test_set(test_defects)
                logger.info(f"✅ Fixed test set created: {len(X_test_fixed)} samples")
            elif self.fixed_test_set is not None:
                # Remove fixed test set defects from training pool
                test_ids = {str(d.get('id')) for d in self.fixed_test_set.get('defects', [])}
                logger.info(f"📌 Using existing FIXED TEST SET: {len(test_ids)} samples")
                
                for tag in self.tag_mapping.values():
                    filtered_X = []
                    filtered_y = []
                    filtered_defects = []
                    
                    for x, y, defect in zip(X_by_class[tag], y_by_class[tag], defect_by_class[tag]):
                        if str(defect.get('id')) not in test_ids:
                            filtered_X.append(x)
                            filtered_y.append(y)
                            filtered_defects.append(defect)
                    
                    X_by_class[tag] = filtered_X
                    y_by_class[tag] = filtered_y
                    defect_by_class[tag] = filtered_defects
            
            # Step 3: Create VALIDATION SET (refreshes monthly)
            # Check if validation set needs refresh (every 4 weeks)
            validation_samples_per_class = min(40, min(len(X_by_class[tag]) for tag in self.tag_mapping.values()) // 2)
            
            if validation_samples_per_class < 10:
                logger.warning(f"⚠️ Not enough data for proper validation/test split")
                logger.warning(f"   Need at least 70 samples per class (30 test + 30 validation + 10 training)")
                logger.warning(f"   Current: {min_class_count} samples per class")
                return False
            
            logger.info(f"📊 Creating VALIDATION SET: {validation_samples_per_class} samples per class")
            logger.info(f"   Validation set age: {self.validation_set_age} weeks (refreshes every 4 weeks)")
            
            X_validation = []
            y_validation = []
            X_train = []
            y_train = []
            
            import random
            # Use different seed each time for validation set diversity
            for tag in self.tag_mapping.values():
                indices = list(range(len(X_by_class[tag])))
                random.shuffle(indices)  # Random shuffle without fixed seed
                
                # Reserve for validation
                val_indices = indices[:validation_samples_per_class]
                train_indices = indices[validation_samples_per_class:]
                
                X_validation.extend([X_by_class[tag][i] for i in val_indices])
                y_validation.extend([y_by_class[tag][i] for i in val_indices])
                X_train.extend([X_by_class[tag][i] for i in train_indices])
                y_train.extend([y_by_class[tag][i] for i in train_indices])
            
            logger.info(f"✅ Data split complete:")
            logger.info(f"   Training set: {len(X_train)} samples")
            logger.info(f"   Validation set: {len(X_validation)} samples")
            if self.fixed_test_set:
                logger.info(f"   Fixed test set: {len(self.fixed_test_set['X'])} samples (NEVER changes)")
            
            # Increment validation set age
            self.validation_set_age += 1
            
            # Use validation set for model selection (not test set!)
            X_test = X_validation
            y_test = y_validation
            
            # Build ensemble model with multiple algorithms
            logger.info("🔧 Building advanced ensemble classifier...")
            
            # Calculate sample weights for minority classes
            class_counts = Counter(y_train)
            total_samples = len(y_train)
            class_weights = {cls: total_samples / (len(class_counts) * count)
                           for cls, count in class_counts.items()}
            sample_weights = np.array([class_weights[y] for y in y_train])
            
            logger.info(f"   Class distribution: {dict(class_counts)}")
            logger.info(f"   Class weights: {class_weights}")
            
            # Enhanced TF-IDF with better parameters
            tfidf = TfidfVectorizer(
                max_features=5000,  # More features for better representation
                ngram_range=(1, 3),  # Unigrams, bigrams, and trigrams
                min_df=2,  # At least 2 occurrences
                max_df=0.85,  # Filter very common terms
                stop_words='english',
                sublinear_tf=True,
                norm='l2',
                use_idf=True,
                smooth_idf=True,
                token_pattern=r'\b\w+\b'  # Better tokenization
            )
            
            # Transform training data
            logger.info("🔧 Extracting TF-IDF features...")
            X_train_tfidf = tfidf.fit_transform(X_train)
            X_test_tfidf = tfidf.transform(X_test)
            
            # Build ensemble with all available classifiers
            num_models = 3 + (1 if XGBOOST_AVAILABLE else 0) + (1 if LIGHTGBM_AVAILABLE else 0)
            logger.info(f"🔧 Training ensemble of {num_models} complementary classifiers...")
            
            # 1. Random Forest - good for non-linear patterns
            rf_clf = RandomForestClassifier(
                n_estimators=500,
                max_depth=15,
                min_samples_split=8,
                min_samples_leaf=3,
                max_features='sqrt',
                bootstrap=True,
                oob_score=True,
                random_state=42,
                n_jobs=-1,
                class_weight='balanced',
                max_samples=0.85
            )
            
            # 2. Gradient Boosting - good for sequential learning
            gb_clf = GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.1,
                max_depth=7,
                min_samples_split=10,
                min_samples_leaf=4,
                subsample=0.8,
                random_state=42,
                verbose=0
            )
            
            # 3. Logistic Regression - good for linear patterns
            lr_clf = LogisticRegression(
                max_iter=1000,
                C=1.0,
                class_weight='balanced',
                random_state=42,
                solver='lbfgs',
                multi_class='multinomial',
                n_jobs=-1
            )
            
            # Train base models
            logger.info("   Training Random Forest (500 trees)...")
            rf_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            logger.info("   Training Gradient Boosting (200 estimators)...")
            gb_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            logger.info("   Training Logistic Regression...")
            lr_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            # 4. XGBoost - powerful gradient boosting (if available)
            if XGBOOST_AVAILABLE:
                logger.info("   Training XGBoost (300 estimators)...")
                xgb_clf = XGBClassifier(
                    n_estimators=300,
                    learning_rate=0.1,
                    max_depth=6,
                    min_child_weight=3,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=-1,
                    verbosity=0
                )
                xgb_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            # 5. LightGBM - fast gradient boosting (if available)
            if LIGHTGBM_AVAILABLE:
                logger.info("   Training LightGBM (300 estimators)...")
                lgbm_clf = LGBMClassifier(
                    n_estimators=300,
                    learning_rate=0.1,
                    max_depth=6,
                    min_child_samples=10,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=-1,
                    verbose=-1
                )
                lgbm_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            # 6. CatBoost - excellent gradient boosting (if available)
            if CATBOOST_AVAILABLE:
                logger.info("   Training CatBoost (300 iterations)...")
                catboost_clf = CatBoostClassifier(
                    iterations=300,
                    learning_rate=0.1,
                    depth=6,
                    l2_leaf_reg=3,
                    random_seed=42,
                    verbose=False,
                    thread_count=-1
                )
                catboost_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            # 7. Extra Trees - faster alternative to Random Forest
            logger.info("   Training Extra Trees (500 trees)...")
            et_clf = ExtraTreesClassifier(
                n_estimators=500,
                max_depth=20,
                min_samples_split=5,
                min_samples_leaf=2,
                max_features='sqrt',
                bootstrap=True,
                oob_score=True,
                random_state=42,
                n_jobs=-1,
                class_weight='balanced'
            )
            et_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            # 8. Support Vector Machine - powerful for text classification
            logger.info("   Training SVM (RBF kernel)...")
            svm_clf = SVC(
                C=1.0,
                kernel='rbf',
                gamma='scale',
                class_weight='balanced',
                random_state=42,
                probability=True  # Enable probability estimates
            )
            svm_clf.fit(X_train_tfidf, y_train, sample_weight=sample_weights)
            
            # DYNAMIC MODEL SELECTION: Evaluate all models and pick the best
            num_models = 6 + (1 if XGBOOST_AVAILABLE else 0) + (1 if LIGHTGBM_AVAILABLE else 0) + (1 if CATBOOST_AVAILABLE else 0)
            logger.info(f"🔧 Evaluating {num_models} models to select the best...")
            
            model_scores = {}
            
            # Log OOB score
            if hasattr(rf_clf, 'oob_score_'):
                logger.info(f"   Random Forest OOB score: {rf_clf.oob_score_:.2%}")
            
            # Evaluate each model
            rf_pred = rf_clf.predict(X_test_tfidf)
            rf_acc = accuracy_score(y_test, rf_pred)
            model_scores['Random Forest'] = (rf_acc, rf_clf)
            logger.info(f"   Random Forest accuracy: {rf_acc:.2%}")
            
            gb_pred = gb_clf.predict(X_test_tfidf)
            gb_acc = accuracy_score(y_test, gb_pred)
            model_scores['Gradient Boosting'] = (gb_acc, gb_clf)
            logger.info(f"   Gradient Boosting accuracy: {gb_acc:.2%}")
            
            lr_pred = lr_clf.predict(X_test_tfidf)
            lr_acc = accuracy_score(y_test, lr_pred)
            model_scores['Logistic Regression'] = (lr_acc, lr_clf)
            logger.info(f"   Logistic Regression accuracy: {lr_acc:.2%}")
            
            if XGBOOST_AVAILABLE:
                xgb_pred = xgb_clf.predict(X_test_tfidf)
                xgb_acc = accuracy_score(y_test, xgb_pred)
                model_scores['XGBoost'] = (xgb_acc, xgb_clf)
                logger.info(f"   XGBoost accuracy: {xgb_acc:.2%}")
            
            if LIGHTGBM_AVAILABLE:
                lgbm_pred = lgbm_clf.predict(X_test_tfidf)
                lgbm_acc = accuracy_score(y_test, lgbm_pred)
                model_scores['LightGBM'] = (lgbm_acc, lgbm_clf)
                logger.info(f"   LightGBM accuracy: {lgbm_acc:.2%}")
            
            if CATBOOST_AVAILABLE:
                catboost_pred = catboost_clf.predict(X_test_tfidf)
                catboost_acc = accuracy_score(y_test, catboost_pred)
                model_scores['CatBoost'] = (catboost_acc, catboost_clf)
                logger.info(f"   CatBoost accuracy: {catboost_acc:.2%}")
            
            # Log OOB score for Extra Trees
            if hasattr(et_clf, 'oob_score_'):
                logger.info(f"   Extra Trees OOB score: {et_clf.oob_score_:.2%}")
            
            et_pred = et_clf.predict(X_test_tfidf)
            et_acc = accuracy_score(y_test, et_pred)
            model_scores['Extra Trees'] = (et_acc, et_clf)
            logger.info(f"   Extra Trees accuracy: {et_acc:.2%}")
            
            svm_pred = svm_clf.predict(X_test_tfidf)
            svm_acc = accuracy_score(y_test, svm_pred)
            model_scores['SVM'] = (svm_acc, svm_clf)
            logger.info(f"   SVM accuracy: {svm_acc:.2%}")
            
            # STEP 6: Select TOP 4 models based on test accuracy
            sorted_models = sorted(model_scores.items(), key=lambda x: x[1][0], reverse=True)
            top_4_models = sorted_models[:4]
            
            logger.info("🏆 Selected TOP 4 models based on test accuracy:")
            for i, (model_name, (test_acc, _)) in enumerate(top_4_models, 1):
                logger.info(f"   {i}. {model_name}: {test_acc:.2%}")
            
            # STEP 7: Test TOP 4 ensemble with SAME test set (reuse test data)
            logger.info("🔍 Testing TOP 4 ensemble with same test set...")
            
            # Prepare ensemble models list
            ensemble_models = []
            ensemble_accuracies = []
            for model_name, (test_acc, model_obj) in top_4_models:
                ensemble_models.append((model_name, model_obj))
                ensemble_accuracies.append(test_acc)
            
            # Create temporary ensemble for testing
            temp_ensemble = VotingClassifier(
                estimators=ensemble_models,
                voting='soft',
                n_jobs=-1
            )
            
            # Convert sparse matrices to dense arrays to avoid CatBoost/SVM compatibility issues
            X_train_tfidf_array = X_train_tfidf.toarray()
            X_test_tfidf_array = X_test_tfidf.toarray()
            
            # Fit temp ensemble on training data (not all data yet)
            temp_ensemble.fit(X_train_tfidf_array, y_train)
            
            # Test ensemble on SAME test set (reuse X_test, now as dense array)
            y_pred_ensemble = temp_ensemble.predict(X_test_tfidf_array)
            ensemble_test_accuracy = accuracy_score(y_test, y_pred_ensemble)
            
            logger.info(f"   🎯 Ensemble accuracy: {ensemble_test_accuracy:.2%}")
            
            # STEP 7.5: Smart Fallback - If ensemble worse than best single model, use best single model
            best_single_model_name, (best_single_accuracy, best_single_model) = top_4_models[0]
            logger.info(f"   🏆 Best single model: {best_single_model_name} ({best_single_accuracy:.2%})")
            
            use_ensemble = True
            if ensemble_test_accuracy < best_single_accuracy:
                logger.warning(f"⚠️ Ensemble ({ensemble_test_accuracy:.2%}) < Best single model ({best_single_accuracy:.2%})")
                logger.info(f"💡 Falling back to best single model: {best_single_model_name}")
                use_ensemble = False
                final_model_accuracy = best_single_accuracy
                final_model_name = best_single_model_name
                final_model_to_train = best_single_model
            else:
                logger.info(f"✅ Ensemble ({ensemble_test_accuracy:.2%}) ≥ Best single model ({best_single_accuracy:.2%})")
                logger.info(f"💡 Using ensemble of 4 models")
                use_ensemble = True
                final_model_accuracy = ensemble_test_accuracy
                final_model_name = "+".join([name for name, _ in ensemble_models])
                final_model_to_train = None  # Will create ensemble later
            
            # STEP 8: FINAL EVALUATION on FIXED TEST SET (unbiased)
            logger.info("=" * 80)
            logger.info("🎯 FINAL EVALUATION: Testing on FIXED TEST SET (unbiased)")
            logger.info("=" * 80)
            
            if self.fixed_test_set is not None:
                # Transform fixed test set
                X_test_fixed_tfidf = tfidf.transform(self.fixed_test_set['X'])
                X_test_fixed_array = X_test_fixed_tfidf.toarray()
                y_test_fixed = self.fixed_test_set['y']
                
                # Evaluate on fixed test set
                if use_ensemble:
                    y_pred_fixed = temp_ensemble.predict(X_test_fixed_array)
                else:
                    y_pred_fixed = final_model_to_train.predict(X_test_fixed_array)
                
                final_test_accuracy = accuracy_score(y_test_fixed, y_pred_fixed)
                logger.info(f"📊 Validation set accuracy: {final_model_accuracy:.2%} (used for model selection)")
                logger.info(f"🎯 FIXED TEST SET accuracy: {final_test_accuracy:.2%} (TRUE performance)")
                
                # Use fixed test set accuracy for comparison
                comparison_accuracy = final_test_accuracy
            else:
                logger.warning("⚠️ No fixed test set available - using validation accuracy")
                comparison_accuracy = final_model_accuracy
                final_test_accuracy = None
            
            # STEP 9: Compare with previous model accuracy
            previous_accuracy = 0.0
            previous_train_samples = 0
            if self.training_stats and 'test_accuracy' in self.training_stats:
                # Parse previous TEST accuracy (the real one)
                prev_acc_str = self.training_stats['test_accuracy'].rstrip('%')
                previous_accuracy = float(prev_acc_str) / 100.0
                previous_train_samples = self.training_stats.get('train_samples', 0)
                logger.info(f"   📊 Previous model TEST accuracy: {previous_accuracy:.2%} (trained on {previous_train_samples} samples)")
            elif self.training_stats and 'accuracy' in self.training_stats:
                # Fallback to old accuracy field
                prev_acc_str = self.training_stats['accuracy'].rstrip('%')
                previous_accuracy = float(prev_acc_str) / 100.0
                previous_train_samples = self.training_stats.get('train_samples', 0)
                logger.info(f"   📊 Previous model accuracy: {previous_accuracy:.2%} (trained on {previous_train_samples} samples)")
            else:
                logger.info(f"   📊 No previous model found - will train new model")
            
            # Check if new model is better than previous model
            # Train if: TEST accuracy is better OR (accuracy is same but more training data)
            current_train_samples = len(X_train)
            should_skip = False
            
            if previous_accuracy > 0:
                if comparison_accuracy < previous_accuracy:
                    # New model is worse - skip
                    should_skip = True
                    skip_reason = f"TEST accuracy decreased ({comparison_accuracy:.2%} < {previous_accuracy:.2%})"
                elif comparison_accuracy == previous_accuracy and current_train_samples <= previous_train_samples:
                    # Same accuracy but not more data - skip
                    should_skip = True
                    skip_reason = f"same TEST accuracy ({comparison_accuracy:.2%}) with same/less training data ({current_train_samples} ≤ {previous_train_samples})"
            
            if should_skip:
                logger.warning(f"⚠️ New model is NOT better - SKIPPING training")
                logger.warning(f"⚠️ Reason: {skip_reason}")
                logger.warning(f"⚠️ Keeping previous model")
                logger.warning(f"💡 Suggestion: Need better TEST accuracy or significantly more training data")
                
                # Store stats for skipped training (for Slack notification)
                self.training_stats['new_test_accuracy'] = f"{comparison_accuracy:.2%}"
                self.training_stats['previous_test_accuracy'] = f"{previous_accuracy:.2%}"
                self.training_stats['trained'] = False
                
                return False
            
            # Calculate improvement
            improvement = None
            if previous_accuracy > 0:
                if comparison_accuracy > previous_accuracy:
                    improvement = comparison_accuracy - previous_accuracy
                    logger.info(f"✅ New model TEST ({comparison_accuracy:.2%}) > Previous ({previous_accuracy:.2%}) - Improvement: {improvement:+.2%}")
                else:
                    # Same accuracy but more data
                    logger.info(f"✅ Same TEST accuracy ({comparison_accuracy:.2%}) but MORE training data ({current_train_samples} > {previous_train_samples})")
                    logger.info(f"✅ Training new model for better generalization")
            else:
                logger.info(f"✅ New model TEST accuracy: {comparison_accuracy:.2%} - Proceeding with training")
            
            logger.info(f"🔄 Proceeding with full training on all data...")
            
            # STEP 9: Train final model on ALL data
            logger.info(f"🔄 Training {'ensemble' if use_ensemble else 'single model'} on ALL {len(X_texts)} defects for production...")
            
            # Transform ALL data with TF-IDF
            X_all_tfidf = tfidf.transform(X_texts)
            X_all_tfidf_array = X_all_tfidf.toarray()  # Convert to dense for compatibility
            
            if use_ensemble:
                # Retrain all 4 models on ALL data
                for model_name, model_obj in ensemble_models:
                    model_obj.fit(X_all_tfidf_array, y_labels, sample_weight=np.array([class_weights[y] for y in y_labels]))
                
                # Create final Voting Classifier (soft voting = uses probabilities)
                final_classifier = VotingClassifier(
                    estimators=ensemble_models,
                    voting='soft',  # Use probability-based voting
                    n_jobs=-1
                )
                
                # Fit ensemble (this just sets up the voting, models already trained)
                final_classifier.fit(X_all_tfidf_array, y_labels)
                
                logger.info(f"✅ Ensemble model trained on ALL data for production use")
            else:
                # Train single best model on ALL data
                final_classifier = final_model_to_train
                final_classifier.fit(X_all_tfidf_array, y_labels, sample_weight=np.array([class_weights[y] for y in y_labels]))
                
                logger.info(f"✅ Single model ({final_model_name}) trained on ALL data for production use")
            
            # Store as pipeline
            self.model = Pipeline([
                ('tfidf', tfidf),
                ('classifier', final_classifier)
            ])
            
            logger.info(f"✅ Model selected and trained successfully!")
            logger.info(f"   Training samples: {len(X_train)}")
            logger.info(f"   Validation samples: {len(X_validation)}")
            if self.fixed_test_set:
                logger.info(f"   Fixed test samples: {len(self.fixed_test_set['X'])}")
            logger.info(f"   🎯 MODEL: {final_model_name}")
            logger.info(f"   📊 Validation accuracy: {final_model_accuracy:.2%}")
            if final_test_accuracy:
                logger.info(f"   🎯 TEST accuracy (unbiased): {final_test_accuracy:.2%}")
            
            # Store training stats with BOTH validation and test accuracies
            self.training_stats = {
                'accuracy': f"{final_model_accuracy:.2%}",  # Validation accuracy (for backward compatibility)
                'validation_accuracy': f"{final_model_accuracy:.2%}",  # Validation set accuracy
                'test_accuracy': f"{final_test_accuracy:.2%}" if final_test_accuracy else "N/A",  # Fixed test set accuracy (TRUE performance)
                'cv_std': "N/A",  # Not applicable for ensemble
                'model_name': final_model_name,
                'total_samples': len(X_texts),
                'train_samples': len(X_train),
                'validation_samples': len(X_validation),
                'test_samples': len(self.fixed_test_set['X']) if self.fixed_test_set else 0,
                'tag_distribution': dict(tag_counts),
                'validation_set_age': self.validation_set_age,
                'trained': True
            }
            
            # Add previous accuracy and improvement if applicable
            if previous_accuracy > 0:
                self.training_stats['previous_test_accuracy'] = f"{previous_accuracy:.2%}"
                if improvement:
                    self.training_stats['improvement'] = f"{improvement:+.2%}"
            
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
        Suggest tag using hybrid rule-based + ML approach
        
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
            text = self._extract_text_features(defect)
            
            if not text.strip():
                return ('unknown', 0.0, 'No text features available')
            
            # Transform text to TF-IDF features
            text_tfidf = self.model.named_steps['tfidf'].transform([text])
            
            # Convert sparse to dense for SVM compatibility
            text_tfidf_dense = text_tfidf.toarray()
            
            # PURE ML: No rules, let the model decide based on training data
            predicted_label = self.model.named_steps['classifier'].predict(text_tfidf_dense)[0]
            predicted_tag = self.reverse_tag_mapping[predicted_label]
            probabilities = self.model.named_steps['classifier'].predict_proba(text_tfidf_dense)[0]
            confidence = float(probabilities[predicted_label])
            
            # Generate reasoning based on ML prediction
            reasoning = self._generate_reasoning(defect, predicted_tag, probabilities)
            return (predicted_tag, confidence, f"ML: {reasoning}")
            
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