import fastapi
import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
from datetime import datetime
import uuid
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InputRequest(BaseModel):
    input: str

@app.post('/process')
async def process_input(request: InputRequest):
    task_id = str(uuid.uuid4())
    
    # Log the input request for debugging
    print(f"Processing input: '{request.input}'")
    
    # Simple hardcoded responses for testing
    response = None
    input_lower = request.input.lower()
    
    # Basic math operations
    if '1+1' in input_lower or '1 + 1' in input_lower:
        response = 'The answer is 2.'
    elif '2+2' in input_lower or '2 + 2' in input_lower:
        response = 'The answer is 4.'
    
    # Greetings
    elif 'hello' in input_lower or 'hi' in input_lower or 'hey' in input_lower:
        response = 'Hello! How can I help you today?'
    elif 'how are you' in input_lower:
        response = "I'm doing well, thank you for asking! How can I assist you today?"
    elif 'thank' in input_lower:
        response = "You're welcome! I'm happy to help. Is there anything else you'd like to know?"
    
    # Programming questions
    elif 'python' in input_lower and 'function' in input_lower:
        response = """
In Python, you can define a function using the `def` keyword:

```python
def my_function(param1, param2):
    # Function body
    result = param1 + param2
    return result
```

You can call the function like this:
```python
answer = my_function(5, 3)
print(answer)  # Outputs: 8
```

Functions can have default parameters, variable arguments, and more advanced features."""
    elif 'javascript' in input_lower or 'js' in input_lower:
        response = """
JavaScript is a versatile programming language commonly used for web development. Here's a simple example:

```javascript
function greet(name) {
  return `Hello, ${name}!`;
}

// Using the function
console.log(greet('World'));  // Outputs: Hello, World!
```

JavaScript supports functional programming, object-oriented patterns, and is the primary language for client-side web scripting."""
    elif 'react' in input_lower or 'component' in input_lower:
        response = """
React is a JavaScript library for building user interfaces. Here's a basic React component:

```jsx
import React from 'react';

function SimpleComponent() {
  return (
    <div>
      <h1>Hello from React!</h1>
      <p>This is a simple component.</p>
    </div>
  );
}

export default SimpleComponent;
```

React components can manage state, handle side effects, and efficiently update the UI."""
    elif ('code' in input_lower and ('generate' in input_lower or 'create' in input_lower)) or ('write' in input_lower and 'code' in input_lower):
        response = """I can help you generate code. Here's a simple example of a utility function in JavaScript:

```javascript
/**
 * Debounce function to limit how often a function can be called
 * @param {Function} func - The function to debounce
 * @param {number} wait - Time in milliseconds to wait between calls
 * @return {Function} - The debounced function
 */
function debounce(func, wait) {
  let timeout;
  
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Usage
const debouncedSearch = debounce((query) => {
  console.log(`Searching for: ${query}`);
  // Actual search implementation
}, 500);
```

This debounce function is useful for things like search inputs or window resize handlers."""
    # General questions
    elif '?' in request.input:
        response = f"That's an interesting question! {request.input} I'd say it depends on the specific context, but I can provide more details if you'd like."
    else:
        response = f"You said: {request.input}\n\nI understand your request and will process it accordingly. What specifically would you like me to help you with?"
    
    print(f"Generated response: '{response[:50]}...'")
    
    result = {
        'task_id': task_id,
        'output': response,
        'response': response,
        'status': 'completed',
        'task_type': 'general_conversation',
        'updated_context': {
            'last_task': 'general_conversation',
            'confidence_score': 0.5,
            'timestamp': datetime.now().isoformat()
        }
    }
    
    return result

@app.get('/models/capabilities')
async def get_model_capabilities(request: Request):
    """Get capabilities of models."""
    print(f"GET /models/capabilities received from {request.client}")
    print(f"Headers: {request.headers}")
    
    # Return capabilities
    return {
        "DEEPSEEK": {
            "context_length": 4096,
            "embedding_length": 4096,
            "attention_heads": 32,
            "token_config": {
                "bos_token_id": 32013,
                "eos_token_id": 32021,
                "eot_token_id": 32014,
                "pad_token_id": 32014,
                "max_token_length": 128
            },
            "supported_tasks": [
                "code_generation",
                "code_explanation", 
                "test_generation",
                "documentation",
                "general_conversation"
            ]
        }
    }

@app.get('/tasks/history')
async def get_task_history(limit: int = 10):
    """Get recent task history."""
    return []

@app.get('/tasks/{task_id}')
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    return {
        "task_id": task_id,
        "status": "completed",
        "response": "Task completed successfully",
        "task_type": "general_conversation"
    }

@app.get('/health')
async def health_check():
    return {'status': 'healthy'}

if __name__ == '__main__':
    print("Starting mock server on http://0.0.0.0:8001")
    uvicorn.run(app, host='0.0.0.0', port=8001) 