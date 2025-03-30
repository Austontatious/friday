import json
import os
import socket
import uvicorn
import logging
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from memory import MemoryManager
from persona import PersonaManager
from model_types import ModelType
from model_loader import initialize_model_loader
from task_manager import TaskManager
from confidence_evaluator import ConfidenceEvaluator
from typing import Dict, Any, Optional
import grpc
from concurrent import futures
import asyncio
from datetime import datetime
from config import config

# Initialize core components
memory = MemoryManager()
persona = PersonaManager()
initialize_model_loader(persona)
task_manager = TaskManager()
confidence_evaluator = ConfidenceEvaluator()

app = FastAPI(title="FRIDAY AI Assistant")

# Setup logging
LOG_FILE = "friday.log"
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add file and console handlers
logger = logging.getLogger()
logger.handlers = []  # Clear existing handlers

# Add file handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)

logging.info("FRIDAY logging initialized")
logging.info(f"Configuration: {config.to_dict()}")

# Add CORS logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logging.info(f"Request: {request.method} {request.url}")
    logging.info(f"Headers: {dict(request.headers)}")
    response = await call_next(request)
    logging.info(f"Response status: {response.status_code}")
    return response

# Enable CORS with centralized configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600  # Cache preflight requests for 1 hour
)

# Add response headers middleware
@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin in config.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

class Friday:
    def __init__(self):
        self.context = {}
        self.active_connections: Dict[str, WebSocket] = {}

    async def process_input(self, user_input: str, websocket: Optional[WebSocket] = None) -> Dict[str, Any]:
        """Process user input with advanced AI components."""
        try:
            # Check memory for context
            try:
                context = memory.retrieve_context(user_input)
                logging.info(f"Retrieved context: {len(context)} items")
            except Exception as e:
                logging.error(f"Error retrieving context: {e}")
                context = []
            
            # Evaluate confidence
            try:
                confidence_score = confidence_evaluator.evaluate(user_input, context)
                logging.info(f"Confidence score: {confidence_score}")
            except Exception as e:
                logging.error(f"Error evaluating confidence: {e}")
                confidence_score = 0.5
            
            # Determine task type
            try:
                task_type = self.identify_task(user_input)
                logging.info(f"Identified task type: {task_type}")
            except Exception as e:
                logging.error(f"Error identifying task type: {e}")
                task_type = "general_conversation"
            
            # Execute task with RAG augmentation
            try:
                result = task_manager.execute_task(user_input, task_type, context)
                logging.info(f"Task executed successfully: {result.get('task_id')}")
            except Exception as e:
                error_msg = str(e) if e else "Unknown error occurred"
                logging.error(f"Error executing task: {error_msg}")
                raise RuntimeError(f"Failed to execute task: {error_msg}")
            
            # Update context
            self.context.update(result.get("updated_context", {}))
            
            # Store in memory
            try:
                memory.store_context(
                    text=user_input,
                    metadata={
                        "task_type": task_type,
                        "confidence_score": confidence_score,
                        "response": result.get("response", "")
                    }
                )
                logging.info("Context stored successfully")
            except Exception as e:
                logging.error(f"Error storing context: {e}")
                # Continue even if memory storage fails
            
            # Stream progress if websocket is connected
            if websocket:
                try:
                    await websocket.send_json({
                        "type": "progress",
                        "task_id": result.get("task_id", ""),
                        "status": "completed"
                    })
                except Exception as e:
                    logging.error(f"Error sending websocket message: {e}")
            
            return result
            
        except Exception as e:
            error_msg = str(e) if e else "Unknown error occurred"
            logging.error(f"Error processing input: {error_msg}")
            error_response = {
                "error": error_msg,
                "status": "failed",
                "details": {
                    "timestamp": datetime.now().isoformat(),
                    "input": user_input,
                    "task_type": task_type if 'task_type' in locals() else None,
                    "confidence_score": confidence_score if 'confidence_score' in locals() else None
                }
            }
            
            if websocket:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg,
                        "details": error_response
                    })
                except Exception as ws_error:
                    logging.error(f"Error sending error message via websocket: {ws_error}")
            
            raise RuntimeError(error_msg)

    def identify_task(self, user_input: str) -> str:
        """Identify task type from user input."""
        input_lower = user_input.lower()
        
        if any(keyword in input_lower for keyword in ["code", "debug", "build", "implement"]):
            return "code_generation"
        elif any(keyword in input_lower for keyword in ["explain", "how", "what", "why"]):
            return "code_explanation"
        elif any(keyword in input_lower for keyword in ["test", "unit test", "integration test"]):
            return "test_generation"
        elif any(keyword in input_lower for keyword in ["document", "doc", "readme"]):
            return "documentation"
        else:
            return "general_conversation"

friday = Friday()

@app.post("/process")
async def process_input(request: Request):
    """Process user input through FRIDAY."""
    try:
        # Parse and validate request body
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Request body must be a JSON object")
            
            user_input = data.get("input", "")
            if not user_input or not isinstance(user_input, str):
                raise ValueError("Input must be a non-empty string")
                
            logging.info(f"Received /process request: {user_input}")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in request body: {str(e)}"
            logging.error(error_msg)
            raise HTTPException(
                status_code=400,
                detail={"error": error_msg, "status": "failed"}
            )
        except ValueError as e:
            error_msg = str(e)
            logging.error(error_msg)
            raise HTTPException(
                status_code=400,
                detail={"error": error_msg, "status": "failed"}
            )
        
        # Process input
        try:
            result = await friday.process_input(user_input)
            return result
        except Exception as e:
            error_msg = str(e) if e else "Unknown error occurred"
            logging.error(f"Error in /process: {error_msg}")
            error_response = {
                "error": error_msg,
                "status": "failed",
                "details": {
                    "timestamp": datetime.now().isoformat(),
                    "input": user_input
                }
            }
            raise HTTPException(status_code=500, detail=error_response)
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if e else "Unknown error occurred"
        logging.error(f"Unexpected error in /process: {error_msg}")
        error_response = {
            "error": error_msg,
            "status": "failed",
            "details": {
                "timestamp": datetime.now().isoformat(),
                "input": user_input if 'user_input' in locals() else None
            }
        }
        raise HTTPException(status_code=500, detail=error_response)

@app.post("/process/explain")
async def explain_code(request: Request):
    """Explain code using RAG-augmented context."""
    data = await request.json()
    code_input = data.get("code", "")
    logging.info(f"Received /process/explain request: {code_input}")
    
    try:
        explanation = task_manager.explain_code(code_input)
        return {"response": explanation}
    except Exception as e:
        logging.error(f"Error in /process/explain: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time task progress."""
    await websocket.accept()
    client_id = str(id(websocket))
    friday.active_connections[client_id] = websocket
    
    try:
        while True:
            data = await websocket.receive_json()
            user_input = data.get("input", "")
            
            if user_input:
                result = await friday.process_input(user_input, websocket)
                await websocket.send_json({
                    "type": "response",
                    "data": result
                })
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        del friday.active_connections[client_id]

@app.get("/tasks/history")
async def get_task_history(limit: int = 10):
    """Get recent task history."""
    return task_manager.get_task_history(limit)

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.get("/models/capabilities")
async def get_model_capabilities():
    """Get capabilities of all available models."""
    return {
        model_type.value: persona.get_model_capabilities(model_type)
        for model_type in ModelType
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

def get_available_port(start=None, end=None):
    """Find an available port in the given range."""
    start = start or config.PORT_RANGE["start"]
    end = end or config.PORT_RANGE["end"]
    
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((config.HOST, port))
                return port
        except OSError:
            continue
    raise OSError(f"No available ports found in range {start}-{end}")

def kill_process_on_port(port):
    """Kill any process running on the specified port."""
    try:
        if os.name == 'nt':  # Windows
            os.system(f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port}\') do taskkill /F /PID %a')
        else:  # Linux/Mac
            os.system(f"lsof -ti:{port} | xargs kill -9")
    except Exception as e:
        logging.warning(f"Failed to kill process on port {port}: {e}")

if __name__ == "__main__":
    logging.info("Starting FRIDAY server...")
    try:
        # Use configured port or find an available one
        port = config.BACKEND_PORT
        if port == 0:
            try:
                port = get_available_port()
                logging.info(f"Using dynamically assigned port: {port}")
            except OSError as e:
                logging.error(f"Failed to find available port: {e}")
                raise

        # Try to kill any existing process on the port
        kill_process_on_port(port)

        # Log server startup information
        logging.info(f"Starting FRIDAY server on port {port}")
        logging.info(f"Server will be accessible at http://localhost:{port}")
        logging.info(f"API documentation available at http://localhost:{port}/docs")

        # Start the server with proper reload configuration
        uvicorn.run(
            "friday:app",
            host=config.HOST,
            port=port,
            reload=True,
            reload_dirs=["."],  # Only watch the current directory
            reload_delay=config.RELOAD_DELAY,  # Add delay to prevent rapid reloads
            log_level=config.LOG_LEVEL.lower(),
            workers=1,  # Single worker to avoid model loading issues
            loop="auto",  # Use the best event loop for the platform
            limit_concurrency=1000,  # Increase concurrent connections limit
            timeout_keep_alive=30,  # Keep connections alive longer
            access_log=True,  # Enable access logging
            use_colors=True,  # Enable colored output
            proxy_headers=True,  # Trust proxy headers
            server_header=True,  # Add server header
            date_header=True  # Add date header
        )
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        raise
