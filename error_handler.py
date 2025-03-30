import logging
from typing import Dict, Any, Optional, Callable
from model_types import ModelType

class ModelError(Exception):
    """Base class for model-related errors."""
    pass

class ModelLoadError(ModelError):
    """Error raised when a model fails to load."""
    pass

class ModelInferenceError(ModelError):
    """Error raised when a model fails during inference."""
    pass

class ModelConfigError(ModelError):
    """Error raised when there is a configuration error."""
    pass

class ErrorHandler:
    def __init__(self):
        self.error_counts: Dict[str, Dict[str, int]] = {}
        self.recovery_strategies: Dict[str, Callable] = self._initialize_recovery_strategies()
        
    def _initialize_recovery_strategies(self) -> Dict[str, Callable]:
        """Initialize recovery strategies for different error types."""
        return {
            "model_load": self._handle_model_load_error,
            "inference": self._handle_inference_error,
            "config": self._handle_config_error
        }
        
    def _handle_model_load_error(self, model_type: ModelType, error: Exception) -> None:
        """Handle model loading errors."""
        error_key = f"{model_type.value}_load"
        self.error_counts.setdefault(error_key, 0)
        self.error_counts[error_key] += 1
        
        if self.error_counts[error_key] <= 3:
            logging.warning(f"Attempting to recover from model load error for {model_type.value}")
            # Add recovery logic here
        else:
            logging.error(f"Max retries exceeded for model load error on {model_type.value}")
            
    def _handle_inference_error(self, model_type: ModelType, error: Exception) -> None:
        """Handle model inference errors."""
        error_key = f"{model_type.value}_inference"
        self.error_counts.setdefault(error_key, 0)
        self.error_counts[error_key] += 1
        
        if self.error_counts[error_key] <= 3:
            logging.warning(f"Attempting to recover from inference error for {model_type.value}")
            # Add recovery logic here
        else:
            logging.error(f"Max retries exceeded for inference error on {model_type.value}")
            
    def _handle_config_error(self, model_type: ModelType, error: Exception) -> None:
        """Handle configuration errors."""
        error_key = f"{model_type.value}_config"
        self.error_counts.setdefault(error_key, 0)
        self.error_counts[error_key] += 1
        
        if self.error_counts[error_key] <= 3:
            logging.warning(f"Attempting to recover from config error for {model_type.value}")
            # Add recovery logic here
        else:
            logging.error(f"Max retries exceeded for config error on {model_type.value}")
            
    def handle_error(self, error_type: str, model_type: ModelType, error: Exception) -> None:
        """Handle an error by retrieving and executing the appropriate recovery strategy."""
        if error_type in self.recovery_strategies:
            try:
                self.recovery_strategies[error_type](model_type, error)
            except Exception as e:
                logging.error(f"Error during recovery for {model_type.value}: {e}")
        else:
            logging.error(f"No recovery strategy found for error type: {error_type}")
            
    def reset_error_count(self, model_type: ModelType, error_type: str) -> None:
        """Reset the error count for a specific model and error type."""
        error_key = f"{model_type.value}_{error_type}"
        self.error_counts[error_key] = 0
        
    def get_error_count(self, model_type: ModelType, error_type: str) -> int:
        """Get the current error count for a specific model and error type."""
        error_key = f"{model_type.value}_{error_type}"
        return self.error_counts.get(error_key, 0)
        
    def should_attempt_recovery(self, model_type: ModelType, error_type: str) -> bool:
        """Check if recovery should be attempted based on error count."""
        return self.get_error_count(model_type, error_type) < 3

# Create global error handler instance
error_handler = ErrorHandler() 