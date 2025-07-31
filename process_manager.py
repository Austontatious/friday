import os
import signal
import logging
import subprocess
import time
import requests
import threading
from typing import Dict, Any, Optional
from pathlib import Path
from .config import config

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.temp_files: List[Path] = []
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _handle_shutdown(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logging.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.cleanup()
        os._exit(0)
        
    def _read_output(self, process, name):
        """Read and log output from a process in real-time."""
        import threading
        
        def read_stream(stream, is_error):
            while True:
                line = stream.readline()
                if not line:
                    break
                line = line.decode('utf-8', errors='replace').strip()
                if line:
                    if is_error:
                        logging.error(f"{name}: {line}")
                    else:
                        logging.info(f"{name}: {line}")
        
        stdout_thread = threading.Thread(
            target=read_stream, 
            args=(process.stdout, False),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=read_stream, 
            args=(process.stderr, True),
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        return stdout_thread, stderr_thread
        
    def start_backend(self) -> None:
        """Start the backend server."""
        try:
            # Kill any existing process on the backend port
            self._kill_process_on_port(config.BACKEND_PORT)
            
            # Start backend server with proper reload configuration
            process = subprocess.Popen(
                ["python", "friday.py"],
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                    "WATCHFILES_FORCE_POLLING": "1",
                    "WATCHFILES_IGNORE_PATTERNS": "*.pyc,__pycache__/*,tmp/*"
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False
            )
            
            self.processes["backend"] = process
            logging.info(f"Started backend server with PID {process.pid}")
            
            # Start output readers
            self._read_output(process, "backend")
            
            # Wait for server to be ready
            if not self._wait_for_server(config.BACKEND_PORT, 60):
                raise RuntimeError("Backend server failed to start")
                
            logging.info("Backend server started successfully")
            
        except Exception as e:
            logging.error(f"Failed to start backend server: {e}")
            raise
            
    def start_frontend(self) -> None:
        """Start the frontend development server."""
        try:
            # Kill any existing process on the port
            self._kill_process_on_port(config.FRONTEND_PORT)
            
            # Start the frontend server
            process = subprocess.Popen(
                ["npm", "start"],
                cwd="frontend",
                env={
                    **os.environ,
                    "NODE_OPTIONS": "--max-old-space-size=4096",
                    "BROWSER": "none"
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False
            )
            
            self.processes["frontend"] = process
            logging.info(f"Started frontend server with PID {process.pid}")
            
            # Start output readers
            self._read_output(process, "frontend")
            
            # Wait for server to start (increase timeout for frontend)
            if not self._wait_for_server(config.FRONTEND_PORT, 120):
                logging.warning("Frontend server didn't respond on health endpoint, but may still be starting")
            else:
                logging.info("Frontend server started successfully")
            
        except Exception as e:
            logging.error(f"Failed to start frontend server: {e}")
            self.cleanup()
            raise
            
    def _wait_for_server(self, port: int, timeout: int = 30) -> bool:
        """Wait for a server to be ready on the specified port."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_in_use(port):
                # Additional check to ensure server is actually responding
                try:
                    response = requests.get(f"http://localhost:{port}/health")
                    if response.status_code == 200:
                        return True
                except:
                    time.sleep(0.1)
            time.sleep(0.1)
        return False
        
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except socket.error:
                return True
                
    def _kill_process_on_port(self, port: int) -> None:
        """Kill any process running on the specified port."""
        try:
            if os.name == "nt":  # Windows
                subprocess.run(
                    f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /F /PID %a',
                    shell=True
                )
            else:  # Linux/Mac
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)
        except Exception as e:
            logging.warning(f"Failed to kill process on port {port}: {e}")
            
    def cleanup(self) -> None:
        """Clean up all processes and temporary files."""
        # Kill all processes
        for name, process in self.processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                logging.error(f"Error killing {name} process: {e}")
                
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logging.error(f"Error removing temporary file {temp_file}: {e}")
                
        self.processes.clear()
        self.temp_files.clear()
        
    def monitor_processes(self) -> None:
        """Monitor running processes and handle any issues."""
        while True:
            try:
                # Check backend process
                if "backend" in self.processes and self.processes["backend"].poll() is not None:
                    logging.warning("Backend process terminated unexpectedly")
                    # Check if it was a normal termination
                    if self.processes["backend"].returncode == 0:
                        logging.info("Backend process terminated normally")
                    else:
                        logging.error(f"Backend process terminated with code {self.processes['backend'].returncode}")
                        self.start_backend()
                        
                # Check frontend process
                if "frontend" in self.processes and self.processes["frontend"].poll() is not None:
                    logging.warning("Frontend process terminated unexpectedly")
                    # Check if it was a normal termination
                    if self.processes["frontend"].returncode == 0:
                        logging.info("Frontend process terminated normally")
                    else:
                        logging.error(f"Frontend process terminated with code {self.processes['frontend'].returncode}")
                        self.start_frontend()
                        
                time.sleep(1)
                    
            except Exception as e:
                logging.error(f"Error monitoring processes: {e}")
                time.sleep(1)
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()

# Create global process manager instance
process_manager = ProcessManager() 