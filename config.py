import os
import logging
from typing import Dict, Any

class Config:
    def __init__(self):
        # Server Configuration
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.BACKEND_PORT = int(os.getenv("FRIDAY_PORT", "8001"))
        self.FRONTEND_PORT = int(os.getenv("REACT_APP_BACKEND_PORT", "8001"))
        
        # Model Configuration
        self.DEEPSEEK_MODEL_PATH = os.getenv("DEEPSEEK_MODEL_PATH", "models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf")
        self.LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH", "models/llama-2-7b-chat.Q4_K_M.gguf")
        
        # Logging Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # API Keys
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        
        # CORS Configuration
        self.ALLOWED_ORIGINS = [
            f"http://localhost:{self.FRONTEND_PORT}",
            f"http://127.0.0.1:{self.FRONTEND_PORT}",
            f"http://localhost:{self.BACKEND_PORT}",
            f"http://127.0.0.1:{self.BACKEND_PORT}"
        ]
        
        # Port Range for Dynamic Port Allocation
        self.PORT_RANGE = {
            "start": 8001,
            "end": 8100
        }
        
        # Server Timeouts
        self.SERVER_TIMEOUT = 30
        self.RELOAD_DELAY = 2
        
        # Validate configuration
        self._validate_config()
        
    def _validate_config(self) -> None:
        """Validate the configuration and raise errors if invalid."""
        if not os.path.exists(self.DEEPSEEK_MODEL_PATH):
            raise FileNotFoundError(f"DeepSeek model not found at {self.DEEPSEEK_MODEL_PATH}")
            
        if not os.path.exists(self.LLAMA_MODEL_PATH):
            logging.warning(f"Llama model not found at {self.LLAMA_MODEL_PATH}. Some features may be limited.")
            
        if not self.ANTHROPIC_API_KEY:
            logging.warning("ANTHROPIC_API_KEY not set. Some features may be limited.")
            
        if self.BACKEND_PORT == self.FRONTEND_PORT:
            raise ValueError("Backend and frontend ports cannot be the same")
            
        if self.PORT_RANGE["start"] > self.PORT_RANGE["end"]:
            raise ValueError("Port range start must be less than end")
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            "host": self.HOST,
            "backend_port": self.BACKEND_PORT,
            "frontend_port": self.FRONTEND_PORT,
            "log_level": self.LOG_LEVEL,
            "allowed_origins": self.ALLOWED_ORIGINS,
            "port_range": self.PORT_RANGE,
            "server_timeout": self.SERVER_TIMEOUT,
            "reload_delay": self.RELOAD_DELAY
        }

# Create global config instance
config = Config() 