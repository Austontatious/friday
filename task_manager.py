from typing import Dict, Any, List, Optional
import json
import logging
from datetime import datetime
import uuid
from memory import MemoryManager
from persona import PersonaManager, ModelType
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

class TaskManager:
    def __init__(self):
        self.memory = MemoryManager()
        self.persona = PersonaManager()
        self.task_history: List[Dict[str, Any]] = []
        self._initialize_rag()

    def _initialize_rag(self):
        """Initialize RAG components."""
        try:
            # Load RAG model and tokenizer
            self.rag_tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            self.rag_model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
            
            # Move model to GPU if available
            if torch.cuda.is_available():
                self.rag_model = self.rag_model.to("cuda")
                
        except Exception as e:
            logging.error(f"Error initializing RAG: {e}")
            raise

    def _generate_embeddings(self, text: str) -> np.ndarray:
        """Generate embeddings for RAG."""
        inputs = self.rag_tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
        with torch.no_grad():
            outputs = self.rag_model(**inputs)
            embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
            
        return embeddings[0]

    def _augment_task_with_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Augment task with relevant context using RAG."""
        # Generate task embedding
        task_embedding = self._generate_embeddings(task["input"])
        
        # Retrieve relevant contexts
        relevant_contexts = self.memory.retrieve_context(task["input"])
        
        # Combine contexts
        context_text = "\n".join([ctx["text"] for ctx in relevant_contexts])
        
        # Update task with context
        augmented_task = task.copy()
        augmented_task["context"] = context_text
        
        return augmented_task

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def execute_task(self, user_input: str, task_type: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a task with RAG augmentation and model routing."""
        try:
            # Create task object
            task = {
                "task_id": str(uuid.uuid4()),
                "type": task_type,
                "input": user_input,
                "context": context or {},
                "timestamp": datetime.now().isoformat(),
                "status": "processing"
            }
            
            # Augment task with RAG
            augmented_task = self._augment_task_with_context(task)
            
            # Generate prompt
            prompt = self.persona.get_prompt_for_task(task_type, augmented_task["context"])
            
            # Get confidence score from memory
            confidence_score = context.get("confidence_score", 0.5) if context else 0.5
            
            # Generate response using appropriate model
            response = self.persona.generate_response(prompt, task_type, confidence_score)
            
            # Update task with response
            task["status"] = "completed"
            task["response"] = response
            task["model_used"] = self.persona.current_model.value if self.persona.current_model else None
            
            # Store task in history
            self.task_history.append(task)
            
            # Update context in memory
            self.memory.store_context(
                text=user_input,
                metadata={
                    "task_type": task_type,
                    "confidence_score": confidence_score,
                    "response": response
                }
            )
            
            return {
                "task_id": task["task_id"],
                "output": response,
                "updated_context": {
                    "last_task": task_type,
                    "confidence_score": confidence_score,
                    "timestamp": task["timestamp"]
                }
            }
            
        except Exception as e:
            logging.error(f"Error executing task: {e}")
            return {
                "task_id": task.get("task_id", str(uuid.uuid4())),
                "output": "I apologize, but I encountered an error while processing your request.",
                "error": str(e)
            }

    def explain_code(self, code: str) -> str:
        """Explain code using RAG-augmented context."""
        try:
            # Create code explanation task
            task = {
                "task_id": str(uuid.uuid4()),
                "type": "code_explanation",
                "input": code,
                "timestamp": datetime.now().isoformat(),
                "status": "processing"
            }
            
            # Augment with relevant code context
            augmented_task = self._augment_task_with_context(task)
            
            # Generate explanation
            prompt = self.persona.get_prompt_for_task("code_explanation", augmented_task["context"])
            explanation = self.persona.generate_response(prompt, "code_explanation", 0.8)
            
            # Store in memory
            self.memory.store_context(
                text=code,
                metadata={
                    "type": "code_explanation",
                    "explanation": explanation
                }
            )
            
            return explanation
            
        except Exception as e:
            logging.error(f"Error explaining code: {e}")
            return "I apologize, but I encountered an error while explaining the code."

    def get_task_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent task history."""
        return sorted(
            self.task_history,
            key=lambda x: x["timestamp"],
            reverse=True
        )[:limit]

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        for task in self.task_history:
            if task["task_id"] == task_id:
                return task
        return None

    def clear_task_history(self):
        """Clear task history."""
        self.task_history = []
