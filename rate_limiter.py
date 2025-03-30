import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from model_types import ModelType

class RateLimiter:
    def __init__(self):
        self.rate_limits: Dict[str, Dict[str, Any]] = {
            ModelType.DEEPSEEK.value: {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "max_concurrent": 5
            },
            ModelType.LLAMA.value: {
                "requests_per_minute": 30,
                "requests_per_hour": 500,
                "max_concurrent": 3
            }
        }
        
        self.request_history: Dict[str, list] = {}
        self.concurrent_requests: Dict[str, int] = {}
        self._initialize_rate_limits()
        
    def _initialize_rate_limits(self) -> None:
        """Initialize rate limit tracking."""
        for model_type in ModelType:
            self.request_history[model_type.value] = []
            self.concurrent_requests[model_type.value] = 0
            
    def _cleanup_old_requests(self, model_type: str) -> None:
        """Remove old requests from history."""
        now = datetime.now()
        self.request_history[model_type] = [
            req_time for req_time in self.request_history[model_type]
            if now - req_time < timedelta(hours=1)
        ]
        
    def can_make_request(self, model_type: ModelType) -> bool:
        """Check if a request can be made based on rate limits."""
        try:
            model_str = model_type.value
            limits = self.rate_limits[model_str]
            
            # Clean up old requests
            self._cleanup_old_requests(model_str)
            
            # Check concurrent requests
            if self.concurrent_requests[model_str] >= limits["max_concurrent"]:
                logging.warning(f"Rate limit exceeded: Too many concurrent requests for {model_str}")
                return False
                
            # Check requests per minute
            minute_ago = datetime.now() - timedelta(minutes=1)
            recent_requests = [
                req_time for req_time in self.request_history[model_str]
                if req_time > minute_ago
            ]
            if len(recent_requests) >= limits["requests_per_minute"]:
                logging.warning(f"Rate limit exceeded: Too many requests per minute for {model_str}")
                return False
                
            # Check requests per hour
            if len(self.request_history[model_str]) >= limits["requests_per_hour"]:
                logging.warning(f"Rate limit exceeded: Too many requests per hour for {model_str}")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Error checking rate limits: {e}")
            return False
            
    def record_request(self, model_type: ModelType) -> None:
        """Record a request for rate limiting."""
        try:
            model_str = model_type.value
            self.request_history[model_str].append(datetime.now())
            self.concurrent_requests[model_str] += 1
            
        except Exception as e:
            logging.error(f"Error recording request: {e}")
            
    def release_request(self, model_type: ModelType) -> None:
        """Release a request from rate limiting."""
        try:
            model_str = model_type.value
            if self.concurrent_requests[model_str] > 0:
                self.concurrent_requests[model_str] -= 1
                
        except Exception as e:
            logging.error(f"Error releasing request: {e}")
            
    def get_rate_limit_status(self, model_type: ModelType) -> Dict[str, Any]:
        """Get current rate limit status for a model."""
        try:
            model_str = model_type.value
            limits = self.rate_limits[model_str]
            
            # Clean up old requests
            self._cleanup_old_requests(model_str)
            
            # Get current counts
            minute_ago = datetime.now() - timedelta(minutes=1)
            recent_requests = [
                req_time for req_time in self.request_history[model_str]
                if req_time > minute_ago
            ]
            
            return {
                "model": model_str,
                "limits": limits,
                "current_requests": {
                    "per_minute": len(recent_requests),
                    "per_hour": len(self.request_history[model_str]),
                    "concurrent": self.concurrent_requests[model_str]
                },
                "can_make_request": self.can_make_request(model_type)
            }
            
        except Exception as e:
            logging.error(f"Error getting rate limit status: {e}")
            return {
                "model": model_type.value,
                "error": str(e)
            }
            
    def update_rate_limits(self, model_type: ModelType, limits: Dict[str, int]) -> bool:
        """Update rate limits for a model."""
        try:
            model_str = model_type.value
            if model_str in self.rate_limits:
                self.rate_limits[model_str].update(limits)
                return True
            return False
            
        except Exception as e:
            logging.error(f"Error updating rate limits: {e}")
            return False
            
    def reset_rate_limits(self, model_type: Optional[ModelType] = None) -> bool:
        """Reset rate limits for a model or all models."""
        try:
            if model_type:
                # Reset specific model
                model_str = model_type.value
                if model_str in self.rate_limits:
                    self._initialize_rate_limits()
                    return True
            else:
                # Reset all models
                self._initialize_rate_limits()
                return True
                
            return False
            
        except Exception as e:
            logging.error(f"Error resetting rate limits: {e}")
            return False

# Create global rate limiter instance
rate_limiter = RateLimiter() 