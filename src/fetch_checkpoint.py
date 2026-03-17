"""
Checkpoint Manager for Background Fetch
Allows resuming interrupted fetches from where they stopped
"""

import json
import os
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class FetchCheckpoint:
    """Manages checkpoints for background fetch operations"""
    
    def __init__(self, checkpoint_file: str = "data/fetch_checkpoint.json"):
        self.checkpoint_file = checkpoint_file
        self.checkpoint_dir = os.path.dirname(checkpoint_file)
        
        # Create directory if it doesn't exist
        if self.checkpoint_dir and not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
    
    def save_checkpoint(self, completed_components: List[str], total_components: List[str]):
        """Save current progress"""
        try:
            checkpoint = {
                "timestamp": datetime.now().isoformat(),
                "completed": completed_components,
                "total": total_components,
                "remaining": [c for c in total_components if c not in completed_components]
            }
            
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            
            logger.info(f"💾 Checkpoint saved: {len(completed_components)}/{len(total_components)} components completed")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self) -> Optional[dict]:
        """Load saved checkpoint"""
        try:
            if not os.path.exists(self.checkpoint_file):
                return None
            
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            
            # Check if checkpoint is from today
            checkpoint_date = datetime.fromisoformat(checkpoint["timestamp"]).date()
            today = datetime.now().date()
            
            if checkpoint_date != today:
                logger.info("📅 Checkpoint is from previous day, starting fresh")
                self.clear_checkpoint()
                return None
            
            remaining = len(checkpoint.get("remaining", []))
            if remaining > 0:
                logger.info(f"📂 Found checkpoint: {remaining} components remaining")
                return checkpoint
            else:
                logger.info("✅ Previous fetch completed, starting fresh")
                self.clear_checkpoint()
                return None
                
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def clear_checkpoint(self):
        """Clear checkpoint file"""
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
                logger.info("🗑️  Checkpoint cleared")
        except Exception as e:
            logger.error(f"Failed to clear checkpoint: {e}")
    
    def get_remaining_components(self, all_components: List[str]) -> List[str]:
        """Get list of components that still need to be fetched"""
        checkpoint = self.load_checkpoint()
        
        if checkpoint:
            remaining = checkpoint.get("remaining", [])
            # Verify remaining components are still in all_components list
            valid_remaining = [c for c in remaining if c in all_components]
            
            if valid_remaining:
                logger.info(f"🔄 Resuming from checkpoint: {len(valid_remaining)} components to fetch")
                return valid_remaining
        
        # No checkpoint or invalid checkpoint - return all components
        logger.info(f"🆕 Starting fresh: {len(all_components)} components to fetch")
        return all_components

# Made with Bob
