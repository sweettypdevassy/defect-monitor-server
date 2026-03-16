#!/usr/bin/env python3
"""
Test script to verify description caching is working properly.
This will:
1. Clear the cache
2. Train the model (should fetch and cache descriptions)
3. Run a daily check (should use cached descriptions)
"""

import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database import Database
from defect_checker import DefectChecker
from ibm_auth import IBMAuth
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration"""
    with open('config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_description_caching():
    """Test the description caching functionality"""
    
    logger.info("=" * 80)
    logger.info("🧪 TESTING DESCRIPTION CACHING")
    logger.info("=" * 80)
    
    # Load config
    config = load_config()
    
    # Initialize components
    database = Database()
    ibm_auth = IBMAuth(config)
    defect_checker = DefectChecker(config, ibm_auth, database)
    
    # Get training components
    training_components = config.get('ml_training', {}).get('training_components', [])
    logger.info(f"\n📋 Training components: {training_components}")
    
    # Step 1: Clear existing cache for training components
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Clearing cache for training components")
    logger.info("=" * 80)
    
    for component in training_components:
        count = database.clear_cached_descriptions(component)
        logger.info(f"   🗑️  Cleared {count} cached descriptions for {component}")
    
    # Step 2: Train the model (should fetch and cache descriptions)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Training model (should fetch and cache descriptions)")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    defect_checker.train_ml_model_on_all_components()
    training_duration = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"\n   ⏱️  Training took {training_duration:.1f} seconds")
    
    # Check cache after training
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Checking cache after training")
    logger.info("=" * 80)
    
    total_cached = 0
    for component in training_components:
        cached = database.get_all_cached_descriptions_for_component(component)
        count = len(cached)
        total_cached += count
        logger.info(f"   💾 {component}: {count} descriptions cached")
    
    logger.info(f"\n   ✅ Total cached descriptions: {total_cached}")
    
    if total_cached == 0:
        logger.error("\n   ❌ FAILED: No descriptions were cached during training!")
        return False
    
    # Step 4: Run a daily check (should use cached descriptions)
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Running daily check (should use cache)")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # Simulate daily check by parsing defects for one component
    test_component = training_components[0] if training_components else "Spring Boot"
    logger.info(f"\n   🔍 Testing with component: {test_component}")
    
    # Fetch defects
    defects = defect_checker.fetch_soe_triage_defects(monitored_components=[test_component])
    
    if defects:
        logger.info(f"   📥 Fetched {len(defects)} defects from API")
        
        # Parse defects (this should use cache)
        parsed = defect_checker.parse_defects(defects, [test_component])
        
        check_duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n   ⏱️  Daily check took {check_duration:.1f} seconds")
        
        # Compare durations
        logger.info("\n" + "=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)
        logger.info(f"   Training duration: {training_duration:.1f}s")
        logger.info(f"   Daily check duration: {check_duration:.1f}s")
        
        if check_duration < training_duration * 0.3:  # Should be much faster
            logger.info(f"\n   ✅ SUCCESS: Daily check is {training_duration/check_duration:.1f}x faster!")
            logger.info("   ✅ Cache is working properly!")
            return True
        else:
            logger.warning(f"\n   ⚠️  WARNING: Daily check should be much faster")
            logger.warning("   ⚠️  Cache might not be working optimally")
            return False
    else:
        logger.error("\n   ❌ No defects fetched for testing")
        return False

if __name__ == "__main__":
    try:
        success = test_description_caching()
        
        logger.info("\n" + "=" * 80)
        if success:
            logger.info("🎉 TEST PASSED: Description caching is working!")
        else:
            logger.info("❌ TEST FAILED: Description caching needs attention")
        logger.info("=" * 80)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
        sys.exit(1)

# Made with Bob
