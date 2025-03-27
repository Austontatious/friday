from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
import socket  # <-- Add this line
from memory import save_to_memory, recall_from_memory, list_memory, clear_memory


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model and CLI Configuration
MODEL_PATH = "/mnt/ai-lab/friday/models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
LLAMA_PATH = "/mnt/ai-lab/friday/llama.cpp/build/bin/llama-cli"
DEFAULT_TOKENS = 512

def run_llama_task(prompt: str, tokens: int = DEFAULT_TOKENS):
    # Build the CLI command
    cmd = [LLAMA_PATH, "-m", MODEL_PATH, "-p", prompt, "-n", str(tokens)]

    # ✅ Debugging: Print the exact command before running
    print(f"Running command: {' '.join(cmd)}")

    try:
        # Run the command and capture output
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # ✅ Debugging: Print the raw CLI output
        print(f"Raw output: {result.stdout}")
        
        # Handle errors
        if result.returncode != 0:
            print(f"Error running llama-cli: {result.stderr}")
            return f"Error running llama-cli: {result.stderr}"
        
        return result.stdout
    except Exception as e:
        print(f"Exception while running llama-cli: {e}")
        return f"Exception: {e}"

# Generate prompt with clarification and confidence checks
def run_with_clarifications(prompt: str):
    clarification_attempts = 0
    while clarification_attempts < MAX_CLARIFICATION_ATTEMPTS:
        output = run_llama_task(prompt)
        
        # ✅ Check for confidence score
        if "CONFIDENCE:" in output:
            try:
                confidence_score = float(output.split("CONFIDENCE:")[-1].strip())
                if confidence_score >= CONFIDENCE_THRESHOLD:
                    return output
                
                # ✅ If confidence is too low, ask for clarification
                elif clarification_attempts < MAX_CLARIFICATION_ATTEMPTS:
                    clarification_attempts += 1
                    clarification_prompt = f"Your previous answer had a confidence of {confidence_score:.2f}. Ask a clarifying question to improve confidence."
                    clarification_response = run_llama_task(clarification_prompt)
                    
                    # 💡 Update the original prompt with the clarification
                    prompt += f"\nClarification {clarification_attempts}: {clarification_response.strip()}"
                    continue
            
            except ValueError:
                pass

        # If confidence parsing fails or max attempts exceeded
        clarification_attempts += 1

    # 🛑 Final fallback if confidence never improves
    return output + "\nNote: Confidence after 3 clarifications is still below threshold."



@app.get("/")
def home():
    return {"message": "FRIDAY is online. Ask her something!"}


@app.post("/refactor")
async def refactor_code(request: Request):
    data = await request.json()
    code = data.get("code", "")
    prior = recall_from_memory(code)
    context = "\n".join(prior)
    prompt = f"{context}\n\nRefactor this code:\n{code}"
    output = run_with_clarifications(prompt)
    save_to_memory(code, output)
    return JSONResponse({"response": output})


@app.post("/generate_tests")
async def generate_tests(request: Request):
    data = await request.json()
    code = data.get("code", "")
    prior = recall_from_memory(code)
    context = "\n".join(prior)
    prompt = f"{context}\n\nWrite unit tests for the following function:\n{code}"
    output = run_with_clarifications(prompt)
    save_to_memory(code, output)
    return JSONResponse(content={"response": output})


@app.post("/explain")
async def explain_code(request: Request):
    data = await request.json()
    code = data.get("code", "")
    prior = recall_from_memory(code)
    context = "\n".join(prior)
    prompt = f"{context}\n\nExplain what this code does in plain English:\n{code}"
    output = run_with_clarifications(prompt)
    save_to_memory(code, output)
    return JSONResponse(content={"response": output})


@app.post("/fix_bugs")
async def fix_bugs(request: Request):
    data = await request.json()
    code = data.get("code", "")
    prior = recall_from_memory(code)
    context = "\n".join(prior)
    prompt = f"{context}\n\nFix any bugs or issues in the following code:\n{code}"
    output = run_with_clarifications(prompt)
    save_to_memory(code, output)
    return JSONResponse(content={"response": output})


@app.get("/memory")
async def get_memory():
    memory_items = list_memory()
    return JSONResponse(content={"memory": memory_items})


@app.delete("/memory")
async def delete_memory():
    clear_memory()
    return JSONResponse(content={"message": "Memory wiped."})


# Automatically find available port
def get_available_port(start=8000, end=8100):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError("No available ports found.")


if __name__ == "__main__":
    port = get_available_port()
    print(f"🚀 FRIDAY is online at http://localhost:{port}/docs")
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=port)

