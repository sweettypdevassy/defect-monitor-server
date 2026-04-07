#!/usr/bin/env python3
"""
Quick script to update the state of a specific defect in the cache
This will fetch the current state from Jazz/RTC and update the database
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.ibm_auth import IBMAuthenticator
from src.defect_checker import DefectChecker
from src.database import DefectDatabase
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_defect_state(defect_id: str):
    """Update the state of a specific defect"""
    
    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    authenticator = IBMAuthenticator(config)
    database = DefectDatabase()
    checker = DefectChecker(authenticator, database)
    
    logger.info(f"🔍 Fetching current state for defect #{defect_id}...")
    
    # Fetch current details from Jazz/RTC
    details = checker.fetch_defect_details(defect_id)
    
    if details:
        state = details.get('state', '')
        is_cancelled = details.get('is_cancelled', False)
        
        logger.info(f"📋 Defect #{defect_id}:")
        logger.info(f"   State: {state}")
        logger.info(f"   Is Cancelled: {is_cancelled}")
        
        if is_cancelled:
            logger.info(f"🚫 Defect #{defect_id} is CANCELLED - will be filtered from dashboard")
        else:
            logger.info(f"✅ Defect #{defect_id} is ACTIVE")
        
        # Update cache
        defect_data = {
            'id': defect_id,
            'state': state,
            'is_cancelled': is_cancelled,
            'description': details.get('description', ''),
            'summary': f'Updated state for #{defect_id}',
            'component': 'Unknown',  # Will be preserved from existing cache
            'functionalArea': '',
            'triageTags': []
        }
        
        database.cache_defect_descriptions([defect_data])
        logger.info(f"✅ Updated cache for defect #{defect_id}")
        
    else:
        logger.error(f"❌ Could not fetch details for defect #{defect_id}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 update_defect_state.py <defect_id>")
        print("Example: python3 update_defect_state.py 308691")
        sys.exit(1)
    
    defect_id = sys.argv[1]
    update_defect_state(defect_id)

# Made with Bob
