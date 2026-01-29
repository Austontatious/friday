import os
import signal
import logging
import subprocess
import time
import threading
import requests
from typing import Dict, Optional
from pathlib import Path


class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.temp_files: list[Path] = []
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame) -> None:
        logging.info("Received signal %s, initiating graceful shutdown...", signum)
        self.cleanup()
        os._exit(0)

    def _read_output(self, process, name):
        def read_stream(stream, is_error):
            while True:
                line = stream.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="replace").strip()
                if line:
                    if is_error:
                        logging.error("%s: %s", name, line)
                    else:
                        logging.info("%s: %s", name, line)

        stdout_thread = threading.Thread(
            target=read_stream,
            args=(process.stdout, False),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=read_stream,
            args=(process.stderr, True),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()
        return stdout_thread, stderr_thread

    def start_backend(self) -> None:
        try:
            backend_port = int(os.getenv("FRIDAY_API_PORT", "9001"))
            self._kill_process_on_port(backend_port)

            process = subprocess.Popen(
                ["python", "-m", "backend.main"],
                env={
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False,
            )

            self.processes["backend"] = process
            logging.info("Started backend server with PID %s", process.pid)
            self._read_output(process, "backend")

            if not self._wait_for_server(backend_port, 60):
                raise RuntimeError("Backend server failed to start")

            logging.info("Backend server started successfully")

        except Exception as e:
            logging.error("Failed to start backend server: %s", e)
            raise

    def start_frontend(self) -> None:
        try:
            frontend_port = int(os.getenv("FRIDAY_FRONTEND_PORT", "5173"))
            self._kill_process_on_port(frontend_port)

            process = subprocess.Popen(
                ["npm", "start"],
                cwd="frontend",
                env={
                    **os.environ,
                    "NODE_OPTIONS": "--max-old-space-size=4096",
                    "BROWSER": "none",
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False,
            )

            self.processes["frontend"] = process
            logging.info("Started frontend server with PID %s", process.pid)
            self._read_output(process, "frontend")

            if not self._wait_for_server(frontend_port, 120):
                logging.warning("Frontend server didn't respond on health endpoint, but may still be starting")
            else:
                logging.info("Frontend server started successfully")

        except Exception as e:
            logging.error("Failed to start frontend server: %s", e)
            self.cleanup()
            raise

    def _wait_for_server(self, port: int, timeout: int = 30) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_in_use(port):
                try:
                    response = requests.get(f"http://localhost:{port}/healthz")
                    if response.status_code == 200:
                        return True
                except Exception:
                    time.sleep(0.1)
            time.sleep(0.1)
        return False

    def _is_port_in_use(self, port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except socket.error:
                return True

    def _kill_process_on_port(self, port: int) -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /F /PID %a',
                    shell=True,
                )
            else:
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)
        except Exception as e:
            logging.warning("Failed to kill process on port %s: %s", port, e)

    def cleanup(self) -> None:
        for name, process in self.processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                logging.error("Error killing %s process: %s", name, e)

        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logging.error("Error removing temporary file %s: %s", temp_file, e)

        self.processes.clear()
        self.temp_files.clear()

    def monitor_processes(self) -> None:
        while True:
            try:
                if "backend" in self.processes and self.processes["backend"].poll() is not None:
                    logging.warning("Backend process terminated unexpectedly")
                    if self.processes["backend"].returncode == 0:
                        logging.info("Backend process terminated normally")
                    else:
                        logging.error("Backend process terminated with code %s", self.processes["backend"].returncode)
                        self.start_backend()

                if "frontend" in self.processes and self.processes["frontend"].poll() is not None:
                    logging.warning("Frontend process terminated unexpectedly")
                    if self.processes["frontend"].returncode == 0:
                        logging.info("Frontend process terminated normally")
                    else:
                        logging.error("Frontend process terminated with code %s", self.processes["frontend"].returncode)
                        self.start_frontend()

                time.sleep(1)

            except Exception as e:
                logging.error("Error monitoring processes: %s", e)
                time.sleep(1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


process_manager = ProcessManager()
