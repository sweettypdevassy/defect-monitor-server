#!/usr/bin/env python3
"""
Cache existing descriptions from the trained model to database.
This will save the descriptions that were already fetched during training.
"""

import sys
import os
import pickle
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database import DefectDatabase

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cache_descriptions_from_model():
    """Load descriptions from trained model and cache them"""
    
    logger.info("=" * 70)
    logger.info("💾 Caching Existing Descriptions to Database")
    logger.info("=" * 70)
    
    # Initialize database
    database = DefectDatabase()
    
    # Load the trained model data
    model_file = 'data/tag_model.pkl'
    
    if not os.path.exists(model_file):
        logger.error(f"❌ Model file not found: {model_file}")
        logger.error("   Please train the model first")
        return False
    
    logger.info(f"\n📂 Loading model from: {model_file}")
    
    try:
        with open(model_file, 'rb') as f:
            model_data = pickle.load(f)
        
        # Extract training data
        training_defects = model_data.get('training_defects', [])
        
        if not training_defects:
            logger.error("❌ No training defects found in model")
            return False
        
        logger.info(f"✅ Found {len(training_defects)} defects in trained model")
        
        # Count defects with descriptions
        defects_with_desc = [d for d in training_defects if d.get('description')]
        logger.info(f"📝 {len(defects_with_desc)} defects have descriptions")
        
        if not defects_with_desc:
            logger.error("❌ No descriptions found to cache")
            return False
        
        # Cache the descriptions
        logger.info(f"\n💾 Caching {len(defects_with_desc)} descriptions to database...")
        database.cache_defect_descriptions(defects_with_desc)
        
        # Verify cache
        logger.info("\n✅ Verifying cache...")
        
        # Group by component
        components = {}
        for defect in defects_with_desc:
            comp = defect.get('component', 'Unknown')
            if comp not in components:
                components[comp] = []
            components[comp].append(defect)
        
        total_cached = 0
        for component, defects in components.items():
            cached = database.get_all_cached_descriptions_for_component(component)
            count = len(cached)
            total_cached += count
            logger.info(f"   {component}: {count} descriptions cached")
        
        logger.info(f"\n🎉 Successfully cached {total_cached} descriptions!")
        logger.info("   Next 'Check Now' will use these cached descriptions")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    try:
        success = cache_descriptions_from_model()
        
        logger.info("\n" + "=" * 70)
        if success:
            logger.info("✅ SUCCESS: Descriptions cached to database")
            logger.info("\nNext steps:")
            logger.info("1. Click 'Check Now' in dashboard")
            logger.info("2. Watch logs for: '✅ Using X cached descriptions'")
            logger.info("3. Should only fetch 2-3 new descriptions")
        else:
            logger.info("❌ FAILED: Could not cache descriptions")
        logger.info("=" * 70)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"\n❌ Script failed: {e}", exc_info=True)
        sys.exit(1)

# Made with Bob
