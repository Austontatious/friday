
import json
import os
import socket
import uvicorn
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from memory import MemoryManager
from persona import PersonaManager
from task_manager import TaskManager
from confidence_evaluator import ConfidenceEvaluator

# Initialize core components
memory = MemoryManager()
persona = PersonaManager()
task_manager = TaskManager()
confidence_evaluator = ConfidenceEvaluator()

app = FastAPI()

# Enable CORS to allow frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
LOG_FILE = "friday.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Friday:
    def __init__(self):
        self.context = {}

    def process_input(self, user_input):
        # Check memory for context
        context = memory.retrieve_context()

        # Evaluate confidence of the input to determine clarity
        confidence_score = confidence_evaluator.evaluate(user_input, context)

        # Trigger clarifying questions if confidence is low
        if confidence_score < 0.75:
            return self.ask_clarifying_question(user_input)

        # Determine task type and switch persona dynamically
        task_type = self.identify_task(user_input)
        persona_prompt = persona.get_prompt_for_task(task_type)

        # Route to task manager for execution
        response = task_manager.execute_task(user_input, task_type, context)

        # Save updated context
        memory.store_context(response["updated_context"])

        return response["output"]

    def ask_clarifying_question(self, user_input):
        return "I'm not entirely sure what you mean. Could you clarify?"

    def identify_task(self, user_input):
        if any(keyword in user_input.lower() for keyword in ["code", "debug", "build"]):
            return "software_engineer"
        elif any(keyword in user_input.lower() for keyword in ["schedule", "reminder", "automate"]):
            return "process_manager"
        elif "explain" in user_input.lower():
            return "explain_code"
        else:
            return "general_conversation"

friday = Friday()

@app.post("/process")
async def process_input(request: Request):
    data = await request.json()
    user_input = data.get("input", "")
    logging.info(f"Received /process request: {user_input}")
    response = friday.process_input(user_input)
    return {"response": response}

@app.post("/process/explain")
async def explain_code(request: Request):
    data = await request.json()
    code_input = data.get("code", "")
    logging.info(f"Received /process/explain request: {code_input}")

    try:
        explanation = task_manager.explain_code(code_input)
        logging.info(f"Explanation generated successfully")
        return {"response": explanation}
    except Exception as e:
        error_msg = f"Error while explaining code: {str(e)}"
        logging.error(error_msg)
        return {"error": error_msg}

# Smart port management to find an available port
def get_available_port(start=8001, end=8100):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError("No available ports found in the specified range.")

# Automatically kill any processes on the target port
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
