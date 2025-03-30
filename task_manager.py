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
            # Check if already initialized
            if hasattr(self, 'rag_tokenizer') and hasattr(self, 'rag_model'):
                logging.info("RAG components already initialized")
                return

            logging.info("Initializing RAG components...")
            
            # Load RAG model and tokenizer
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            try:
                self.rag_tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.rag_model = AutoModel.from_pretrained(model_name)
            except Exception as e:
                error_msg = f"Failed to load RAG model: {str(e)}"
                logging.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Move model to appropriate device
            try:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self.rag_model = self.rag_model.to(device)
                logging.info(f"RAG model moved to {device}")
            except Exception as e:
                error_msg = f"Failed to move model to device: {str(e)}"
                logging.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Set model to evaluation mode
            try:
                self.rag_model.eval()
                logging.info("RAG model set to evaluation mode")
            except Exception as e:
                error_msg = f"Failed to set model to evaluation mode: {str(e)}"
                logging.error(error_msg)
                raise RuntimeError(error_msg)
            
            logging.info("RAG components initialized successfully")
                
        except Exception as e:
            error_msg = str(e) if e else "Unknown error occurred"
            logging.error(f"Error initializing RAG: {error_msg}")
            # Don't raise the error, just log it
            # This allows the system to continue functioning even if RAG fails
            self.rag_tokenizer = None
            self.rag_model = None

    def _generate_embeddings(self, text: str) -> np.ndarray:
        """Generate embeddings for RAG."""
        try:
            # Validate text input
            if not text or not isinstance(text, str):
                raise ValueError("Invalid text input for embedding generation")

            # Check if RAG components are available
            if not self.rag_tokenizer or not self.rag_model:
                logging.warning("RAG components not available, returning zero vector")
                return np.zeros(768)  # Default dimension for all-MiniLM-L6-v2

            # Generate embeddings
            try:
                inputs = self.rag_tokenizer(
                    text,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512  # Add max length to prevent OOM
                )

                # Move inputs to appropriate device
                device = "cuda" if torch.cuda.is_available() else "cpu"
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                # Generate embeddings
                with torch.no_grad():
                    outputs = self.rag_model(**inputs)
                    embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
                
                return embeddings[0]
            except Exception as e:
                error_msg = f"Failed to generate embeddings: {str(e)}"
                logging.error(error_msg)
                return np.zeros(768)  # Return zero vector as fallback

        except Exception as e:
            error_msg = str(e) if e else "Unknown error occurred"
            logging.error(f"Error in _generate_embeddings: {error_msg}")
            return np.zeros(768)  # Return zero vector as fallback

    def _augment_task_with_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Augment task with relevant context using RAG."""
        try:
            # Validate input
            if not task.get("input"):
                logging.warning("No input provided for task, skipping context augmentation")
                return task

            # Generate task embedding
            try:
                task_embedding = self._generate_embeddings(task["input"])
            except Exception as e:
                logging.error(f"Error generating embeddings: {e}")
                return task
            
            # Retrieve relevant contexts
            try:
                relevant_contexts = self.memory.retrieve_context(task["input"])
                if not relevant_contexts:
                    logging.info("No relevant contexts found")
                    return task
            except Exception as e:
                logging.error(f"Error retrieving context: {e}")
                return task
            
            # Combine contexts
            try:
                context_text = "\n".join([ctx.get("text", "") for ctx in relevant_contexts if ctx.get("text")])
                if not context_text:
                    logging.info("No valid context text found")
                    return task
            except Exception as e:
                logging.error(f"Error combining contexts: {e}")
                return task
            
            # Update task with context
            augmented_task = task.copy()
            augmented_task["context"] = context_text
            logging.info(f"Successfully augmented task with {len(relevant_contexts)} contexts")
            
            return augmented_task
            
        except Exception as e:
            logging.error(f"Error in _augment_task_with_context: {e}")
            return task

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def execute_task(self, user_input: str, task_type: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a task with RAG augmentation and model routing."""
        task = {
            "task_id": str(uuid.uuid4()),
            "type": task_type,
            "input": user_input,
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
            "status": "processing"
        }
        
        try:
            logging.info(f"Starting task execution: {task['task_id']}")
            logging.info(f"Task type: {task_type}")
            logging.info(f"Input: {user_input}")
            
            # Augment task with RAG
            try:
                augmented_task = self._augment_task_with_context(task)
                logging.info("Task augmented with context successfully")
            except Exception as e:
                logging.error(f"Error augmenting task with context: {e}")
                # Continue without context augmentation
                augmented_task = task
            
            # Generate prompt
            try:
                prompt = self.persona.get_prompt_for_task(task_type, augmented_task["context"])
                logging.info(f"Generated prompt for task type: {task_type}")
            except Exception as e:
                logging.error(f"Error generating prompt: {e}")
                raise RuntimeError(f"Failed to generate prompt: {e}")
            
            # Get confidence score from memory
            confidence_score = context.get("confidence_score", 0.5) if context else 0.5
            logging.info(f"Using confidence score: {confidence_score}")
            
            # Generate response using appropriate model
            try:
                response = self.persona.generate_response(prompt, task_type, confidence_score)
                logging.info("Generated response successfully")
            except Exception as e:
                logging.error(f"Error generating response: {e}")
                raise RuntimeError(f"Failed to generate response: {e}")
            
            # Update task with response
            task["status"] = "completed"
            task["response"] = response
            task["model_used"] = self.persona.current_model.value if self.persona.current_model else None
            
            # Store task in history
            self.task_history.append(task)
            logging.info(f"Task {task['task_id']} completed successfully")
            
            # Update context in memory
            try:
                self.memory.store_context(
                    text=user_input,
                    metadata={
                        "task_type": task_type,
                        "confidence_score": confidence_score,
                        "response": response
                    }
                )
                logging.info("Context stored successfully")
            except Exception as e:
                logging.error(f"Error storing context: {e}")
                # Continue even if memory storage fails
            
            return {
                "task_id": task["task_id"],
                "response": response,
                "status": "completed",
                "task_type": task_type,
                "updated_context": {
                    "last_task": task_type,
                    "confidence_score": confidence_score,
                    "timestamp": task["timestamp"]
                }
            }
            
        except Exception as e:
            error_msg = str(e) if e else "Unknown error occurred"
            logging.error(f"Error executing task: {error_msg}")
            task["status"] = "failed"
            task["error"] = error_msg
            
            # Store failed task in history
            self.task_history.append(task)
            
            # Return detailed error response
            return {
                "task_id": task["task_id"],
                "response": f"I apologize, but I encountered an error while processing your request: {error_msg}",
                "status": "failed",
                "error": error_msg,
                "task_type": task_type
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
