

from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server
import threading
import time
from .model_config import ModelType

class ModelMonitor:
    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or CollectorRegistry()

        # Core metrics
        self.request_counter = Counter(
            'model_requests_total',
            'Total number of model requests',
            ['model_type', 'task_type'],
            registry=self.registry
        )
        self.error_counter = Counter(
            'model_errors_total',
            'Total number of model errors',
            ['model_type', 'error_type'],
            registry=self.registry
        )
        self.model_status_gauge = Gauge(
            'model_status',
            'Model status (1=loaded, 0=unloaded)',
            ['model_type'],
            registry=self.registry
        )

        # Monitoring control
        self.stop_monitoring = False
        self.monitor_thread = None

    def start_monitoring(self, port: int = 8001):
        """Start Prometheus metrics server and optional background monitoring."""
        start_http_server(port, registry=self.registry)
        print(f"✅ Prometheus metrics server running at http://localhost:{port}/metrics")

        # Start background thread if you want runtime health checks
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def monitor_loop(self):
        """Optional live monitoring - e.g., memory usage, VRAM, health checks."""
        while not self.stop_monitoring:
            # In future: Check GPU health, RAM usage, etc.
            time.sleep(5)  # Sleep to avoid busy-loop

    def record_request(self, model_type: ModelType, task_type: str):
        self.request_counter.labels(model_type=model_type.value, task_type=task_type).inc()

    def record_error(self, model_type: ModelType, error_type: str):
        self.error_counter.labels(model_type=model_type.value, error_type=error_type).inc()

    def set_model_status(self, model_type: ModelType, loaded: bool):
        self.model_status_gauge.labels(model_type=model_type.value).set(1 if loaded else 0)

