"""
Cache Cleaner Module
Automatically cleans Chrome profile cache to prevent unbounded growth
"""

import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class CacheCleaner:
    """Manages Chrome profile cache cleanup"""
    
    def __init__(self, profile_path: str = "data/chrome_profile"):
        self.profile_path = profile_path
        self.cache_dirs = [
            "Default/Code Cache",
            "Default/DawnCache",
            "Default/GPUCache",
            "Default/Service Worker/CacheStorage"
        ]
        # Keep these - essential for authentication
        self.keep_files = [
            "Default/Cookies",
            "Default/Cookies-journal",
            "Default/Local Storage",
            "Default/Preferences",
            "Default/Network"
        ]
    
    def clean_cache(self, max_age_days: int = 7) -> dict:
        """
        Clean cache files older than max_age_days
        
        Args:
            max_age_days: Maximum age of cache files in days
            
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': 0
        }
        
        if not os.path.exists(self.profile_path):
            logger.info("Chrome profile path does not exist, nothing to clean")
            return stats
        
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        try:
            for cache_dir in self.cache_dirs:
                cache_path = os.path.join(self.profile_path, cache_dir)
                
                if not os.path.exists(cache_path):
                    continue
                
                logger.info(f"Cleaning cache directory: {cache_dir}")
                
                # Remove entire cache directory
                try:
                    dir_size = self._get_dir_size(cache_path)
                    shutil.rmtree(cache_path)
                    stats['bytes_freed'] += dir_size
                    stats['files_deleted'] += 1
                    logger.info(f"  Removed {cache_dir} ({dir_size / 1024 / 1024:.2f} MB)")
                except Exception as e:
                    logger.warning(f"  Error removing {cache_dir}: {e}")
                    stats['errors'] += 1
            
            logger.info(f"✅ Cache cleanup complete:")
            logger.info(f"   Files/dirs deleted: {stats['files_deleted']}")
            logger.info(f"   Space freed: {stats['bytes_freed'] / 1024 / 1024:.2f} MB")
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            stats['errors'] += 1
        
        return stats
    
    def _get_dir_size(self, path: str) -> int:
        """Get total size of directory in bytes"""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_dir_size(entry.path)
        except Exception as e:
            logger.debug(f"Error calculating size for {path}: {e}")
        return total
    
    def get_cache_stats(self) -> dict:
        """Get current cache statistics"""
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'cache_dirs': {}
        }
        
        if not os.path.exists(self.profile_path):
            return stats
        
        try:
            # Count all files
            for root, dirs, files in os.walk(self.profile_path):
                stats['total_files'] += len(files)
            
            # Get size of each cache directory
            for cache_dir in self.cache_dirs:
                cache_path = os.path.join(self.profile_path, cache_dir)
                if os.path.exists(cache_path):
                    size = self._get_dir_size(cache_path)
                    stats['cache_dirs'][cache_dir] = {
                        'size_mb': size / 1024 / 1024,
                        'exists': True
                    }
            
            # Total size
            total_size = self._get_dir_size(self.profile_path)
            stats['total_size_mb'] = total_size / 1024 / 1024
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
        
        return stats


def clean_chrome_cache():
    """Standalone function to clean cache (for scheduler)"""
    cleaner = CacheCleaner()
    return cleaner.clean_cache(max_age_days=7)


if __name__ == "__main__":
    # For manual testing
    logging.basicConfig(level=logging.INFO)
    cleaner = CacheCleaner()
    
    print("\n📊 Current cache stats:")
    stats = cleaner.get_cache_stats()
    print(f"Total files: {stats['total_files']}")
    print(f"Total size: {stats['total_size_mb']:.2f} MB")
    print(f"\nCache directories:")
    for dir_name, dir_stats in stats['cache_dirs'].items():
        if dir_stats['exists']:
            print(f"  {dir_name}: {dir_stats['size_mb']:.2f} MB")
    
    print("\n🧹 Cleaning cache...")
    result = cleaner.clean_cache()
    print(f"\n✅ Cleanup complete:")
    print(f"Files deleted: {result['files_deleted']}")
    print(f"Space freed: {result['bytes_freed'] / 1024 / 1024:.2f} MB")

# Made with Bob
