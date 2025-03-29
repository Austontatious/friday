import json
import os
import socket
import uvicorn
import logging
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from memory import MemoryManager
from persona import PersonaManager, ModelType
from task_manager import TaskManager
from confidence_evaluator import ConfidenceEvaluator
from typing import Dict, Any, Optional
import grpc
from concurrent import futures
import asyncio
from datetime import datetime

# Initialize core components
memory = MemoryManager()
persona = PersonaManager()
task_manager = TaskManager()
confidence_evaluator = ConfidenceEvaluator()

app = FastAPI(title="FRIDAY AI Assistant")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
LOG_FILE = "friday.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class Friday:
    def __init__(self):
        self.context = {}
        self.active_connections: Dict[str, WebSocket] = {}

    async def process_input(self, user_input: str, websocket: Optional[WebSocket] = None) -> Dict[str, Any]:
        """Process user input with advanced AI components."""
        try:
            # Check memory for context
            context = memory.retrieve_context(user_input)
            
            # Evaluate confidence
            confidence_score = confidence_evaluator.evaluate(user_input, context)
            
            # Determine task type
            task_type = self.identify_task(user_input)
            
            # Execute task with RAG augmentation
            result = task_manager.execute_task(user_input, task_type, context)
            
            # Update context
            self.context.update(result["updated_context"])
            
            # Store in memory
            memory.store_context(
                text=user_input,
                metadata={
                    "task_type": task_type,
                    "confidence_score": confidence_score,
                    "response": result["output"]
                }
            )
            
            # Stream progress if websocket is connected
            if websocket:
                await websocket.send_json({
                    "type": "progress",
                    "task_id": result["task_id"],
                    "status": "completed"
                })
            
            return result
            
        except Exception as e:
            logging.error(f"Error processing input: {e}")
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            raise HTTPException(status_code=500, detail=str(e))

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
    data = await request.json()
    user_input = data.get("input", "")
    logging.info(f"Received /process request: {user_input}")
    
    try:
        result = await friday.process_input(user_input)
        return result
    except Exception as e:
        logging.error(f"Error in /process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

# Smart port management
def get_available_port(start=8001, end=8100):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError("No available ports found in the specified range.")

def kill_process_on_port(port):
    cmd = f"sudo lsof -ti:{port} | xargs sudo kill -9"
    os.system(cmd)

if __name__ == "__main__":
    try:
        port = get_available_port()
        print(f"🚀 FRIDAY is online at http://localhost:{port}/docs")
        logging.info(f"FRIDAY is online at http://localhost:{port}/docs")
        uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
    except OSError:
        print(f"⚠️ Port conflict detected on 8001. Trying to fix...")
        kill_process_on_port(8001)
        port = get_available_port()
        print(f"🚀 FRIDAY is online at http://localhost:{port}/docs")
        uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
