import os
import json
import time
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from model_types import ModelType

class ModelCache:
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self.cache_ttl = timedelta(hours=24)  # Cache TTL in hours
        self._initialize_cache()
        
    def _initialize_cache(self) -> None:
        """Initialize the cache directory and structure."""
        try:
            # Create cache directory if it doesn't exist
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Create model-specific cache directories
            for model_type in ModelType:
                model_cache_dir = os.path.join(self.cache_dir, model_type.value)
                os.makedirs(model_cache_dir, exist_ok=True)
                
        except Exception as e:
            logging.error(f"Failed to initialize cache: {e}")
            raise
            
    def _get_cache_key(self, model_type: ModelType, prompt: str, **kwargs) -> str:
        """Generate a cache key for a request."""
        # Create a unique key based on model type, prompt, and parameters
        key_data = {
            "model_type": model_type.value,
            "prompt": prompt,
            **kwargs
        }
        
        # Convert to JSON string and hash
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
        
    def _get_cache_path(self, model_type: ModelType, cache_key: str) -> str:
        """Get the cache file path for a key."""
        return os.path.join(self.cache_dir, model_type.value, f"{cache_key}.json")
        
    def get(self, model_type: ModelType, prompt: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get a cached response if available and not expired."""
        try:
            cache_key = self._get_cache_key(model_type, prompt, **kwargs)
            cache_path = self._get_cache_path(model_type, cache_key)
            
            if not os.path.exists(cache_path):
                return None
                
            # Read cache file
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is expired
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > self.cache_ttl:
                # Remove expired cache
                os.remove(cache_path)
                return None
                
            return cache_data['response']
            
        except Exception as e:
            logging.error(f"Error reading cache: {e}")
            return None
            
    def set(self, model_type: ModelType, prompt: str, response: Dict[str, Any], **kwargs) -> bool:
        """Cache a response."""
        try:
            cache_key = self._get_cache_key(model_type, prompt, **kwargs)
            cache_path = self._get_cache_path(model_type, cache_key)
            
            # Prepare cache data
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'model_type': model_type.value,
                'prompt': prompt,
                'response': response,
                **kwargs
            }
            
            # Write to cache file
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
                
            return True
            
        except Exception as e:
            logging.error(f"Error writing to cache: {e}")
            return False
            
    def clear(self, model_type: Optional[ModelType] = None) -> bool:
        """Clear cache for a specific model or all models."""
        try:
            if model_type:
                # Clear specific model cache
                model_cache_dir = os.path.join(self.cache_dir, model_type.value)
                if os.path.exists(model_cache_dir):
                    for file in os.listdir(model_cache_dir):
                        os.remove(os.path.join(model_cache_dir, file))
            else:
                # Clear all cache
                for model_type in ModelType:
                    model_cache_dir = os.path.join(self.cache_dir, model_type.value)
                    if os.path.exists(model_cache_dir):
                        for file in os.listdir(model_cache_dir):
                            os.remove(os.path.join(model_cache_dir, file))
                            
            return True
            
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")
            return False
            
    def get_cache_stats(self, model_type: Optional[ModelType] = None) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'total_entries': 0,
            'total_size': 0,
            'expired_entries': 0,
            'model_stats': {}
        }
        
        try:
            if model_type:
                # Get stats for specific model
                model_cache_dir = os.path.join(self.cache_dir, model_type.value)
                if os.path.exists(model_cache_dir):
                    model_stats = self._get_model_cache_stats(model_cache_dir)
                    stats['model_stats'][model_type.value] = model_stats
                    stats['total_entries'] = model_stats['entries']
                    stats['total_size'] = model_stats['size']
                    stats['expired_entries'] = model_stats['expired']
            else:
                # Get stats for all models
                for mt in ModelType:
                    model_cache_dir = os.path.join(self.cache_dir, mt.value)
                    if os.path.exists(model_cache_dir):
                        model_stats = self._get_model_cache_stats(model_cache_dir)
                        stats['model_stats'][mt.value] = model_stats
                        stats['total_entries'] += model_stats['entries']
                        stats['total_size'] += model_stats['size']
                        stats['expired_entries'] += model_stats['expired']
                        
            return stats
            
        except Exception as e:
            logging.error(f"Error getting cache stats: {e}")
            return stats
            
    def _get_model_cache_stats(self, cache_dir: str) -> Dict[str, Any]:
        """Get cache statistics for a specific model."""
        stats = {
            'entries': 0,
            'size': 0,
            'expired': 0
        }
        
        try:
            for file in os.listdir(cache_dir):
                if file.endswith('.json'):
                    file_path = os.path.join(cache_dir, file)
                    stats['entries'] += 1
                    stats['size'] += os.path.getsize(file_path)
                    
                    # Check if entry is expired
                    with open(file_path, 'r') as f:
                        cache_data = json.load(f)
                        cache_time = datetime.fromisoformat(cache_data['timestamp'])
                        if datetime.now() - cache_time > self.cache_ttl:
                            stats['expired'] += 1
                            
            return stats
            
        except Exception as e:
            logging.error(f"Error getting model cache stats: {e}")
            return stats

# Create global model cache instance
model_cache = ModelCache() 