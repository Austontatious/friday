# friday/schema.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class TaskRequest(BaseModel):
    prompt: str = Field(..., description="The user's prompt or command")
     model: Optional[str] = Field(None, description="Model name to route to")
     temperature: Optional[float] = Field(0.7, description="Generation temperature")
     top_p: Optional[float] = Field(0.9, description="Top‑p nucleus sampling")
     max_tokens: Optional[int] = Field(512, description="Maximum tokens to generate")
 
        extra = "allow"
        allow_population_by_field_name = True
        json_schema_extra = {
            "example": {
                "prompt": "What’s the airspeed velocity of an unladen swallow?",
                "model": "openchat",
                "temperature": 0.8,
                "top_p": 0.95,
                "max_tokens": 100
            }
        }


class TaskResponse(BaseModel):
    output: str
    metadata: Optional[Dict[str, Any]] = None

# FastAPI route to handle the POST request
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.post("/api/v1/process")
async def process_task(request: TaskRequest):
    # Log the received request to inspect the data
    print('Received task data:', request.dict())

    # You can also check for missing fields or invalid data here
    if not request.task:
        raise HTTPException(status_code=422, detail="Task field is required")

    # Process the task and return a response (you can implement your logic here)
    return TaskResponse(output=f"Processed task: {request.task}")

