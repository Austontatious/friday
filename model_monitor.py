import os
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge
from model_types import ModelType

class ModelMonitor:
    def __init__(self):
        # Initialize Prometheus metrics
        self.request_counter = Counter(
            'model_requests_total',
            'Total number of model requests',
            ['model_type', 'task_type']
        )
        
        self.error_counter = Counter(
            'model_errors_total',
            'Total number of model errors',
            ['model_type', 'error_type']
        )
        
        self.latency_histogram = Histogram(
            'model_latency_seconds',
            'Model request latency in seconds',
            ['model_type', 'task_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.token_counter = Counter(
            'model_tokens_total',
            'Total number of tokens processed',
            ['model_type', 'direction']
        )
        
        self.model_memory_gauge = Gauge(
            'model_memory_bytes',
            'Current memory usage of models',
            ['model_type']
        )
        
        self.model_status_gauge = Gauge(
            'model_status',
            'Current status of models (1=loaded, 0=unloaded)',
            ['model_type']
        )
        
        # Initialize logging
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """Setup model-specific logging."""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Setup model-specific log file
        model_logger = logging.getLogger('model_monitor')
        model_logger.setLevel(logging.INFO)
        
        # File handler for model logs
        file_handler = logging.FileHandler('logs/model_monitor.log')
        file_handler.setLevel(logging.INFO)
        
        # Console handler for model logs
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        model_logger.addHandler(file_handler)
        model_logger.addHandler(console_handler)
        
        self.logger = model_logger
        
    def log_request(self, model_type: ModelType, task_type: str) -> None:
        """Log a model request."""
        self.request_counter.labels(
            model_type=model_type.value,
            task_type=task_type
        ).inc()
        
        self.logger.info(
            f"Model request - Type: {model_type.value}, Task: {task_type}"
        )
        
    def log_error(self, model_type: ModelType, error_type: str, error: Exception) -> None:
        """Log a model error."""
        self.error_counter.labels(
            model_type=model_type.value,
            error_type=error_type
        ).inc()
        
        self.logger.error(
            f"Model error - Type: {model_type.value}, Error: {error_type}, "
            f"Message: {str(error)}"
        )
        
    def log_latency(self, model_type: ModelType, task_type: str, start_time: float) -> None:
        """Log request latency."""
        latency = time.time() - start_time
        self.latency_histogram.labels(
            model_type=model_type.value,
            task_type=task_type
        ).observe(latency)
        
        self.logger.info(
            f"Request latency - Type: {model_type.value}, Task: {task_type}, "
            f"Latency: {latency:.2f}s"
        )
        
    def log_tokens(self, model_type: ModelType, input_tokens: int, output_tokens: int) -> None:
        """Log token usage."""
        self.token_counter.labels(
            model_type=model_type.value,
            direction='input'
        ).inc(input_tokens)
        
        self.token_counter.labels(
            model_type=model_type.value,
            direction='output'
        ).inc(output_tokens)
        
        self.logger.info(
            f"Token usage - Type: {model_type.value}, Input: {input_tokens}, "
            f"Output: {output_tokens}"
        )
        
    def update_memory_usage(self, model_type: ModelType, memory_bytes: int) -> None:
        """Update model memory usage."""
        self.model_memory_gauge.labels(
            model_type=model_type.value
        ).set(memory_bytes)
        
        self.logger.info(
            f"Memory usage - Type: {model_type.value}, Usage: {memory_bytes/1024/1024:.2f}MB"
        )
        
    def update_model_status(self, model_type: ModelType, is_loaded: bool) -> None:
        """Update model status."""
        self.model_status_gauge.labels(
            model_type=model_type.value
        ).set(1 if is_loaded else 0)
        
        self.logger.info(
            f"Model status - Type: {model_type.value}, Status: {'Loaded' if is_loaded else 'Unloaded'}"
        )
        
    def get_model_stats(self, model_type: ModelType) -> Dict[str, Any]:
        """Get statistics for a specific model."""
        return {
            'requests': self.request_counter.labels(
                model_type=model_type.value
            )._value.get(),
            'errors': self.error_counter.labels(
                model_type=model_type.value
            )._value.get(),
            'latency': self.latency_histogram.labels(
                model_type=model_type.value
            )._sum.get(),
            'tokens': {
                'input': self.token_counter.labels(
                    model_type=model_type.value,
                    direction='input'
                )._value.get(),
                'output': self.token_counter.labels(
                    model_type=model_type.value,
                    direction='output'
                )._value.get()
            },
            'memory': self.model_memory_gauge.labels(
                model_type=model_type.value
            )._value.get(),
            'status': self.model_status_gauge.labels(
                model_type=model_type.value
            )._value.get()
        }
        
    def generate_report(self) -> str:
        """Generate a monitoring report."""
        report = []
        report.append(f"Model Monitoring Report - {datetime.now()}")
        report.append("=" * 50)
        
        for model_type in ModelType:
            stats = self.get_model_stats(model_type)
            report.append(f"\nModel: {model_type.value}")
            report.append(f"Status: {'Loaded' if stats['status'] == 1 else 'Unloaded'}")
            report.append(f"Total Requests: {stats['requests']}")
            report.append(f"Total Errors: {stats['errors']}")
            report.append(f"Average Latency: {stats['latency']:.2f}s")
            report.append(f"Token Usage:")
            report.append(f"  Input: {stats['tokens']['input']}")
            report.append(f"  Output: {stats['tokens']['output']}")
            report.append(f"Memory Usage: {stats['memory']/1024/1024:.2f}MB")
            
        return "\n".join(report)

# Create global model monitor instance
model_monitor = ModelMonitor() 