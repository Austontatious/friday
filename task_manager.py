import logging
import uuid
from typing import Optional, Dict, Any, Union

from .memory import MemoryManager
from .persona import PersonaManager
from .model_loader_core import ModelLoader
from .model_types import TaskType

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(
        self,
        model_loader: ModelLoader,
        memory_manager: Optional[MemoryManager] = None,
        persona_manager: Optional[PersonaManager] = None
    ):
        self.model_loader = model_loader
        self.memory = memory_manager
        self.persona = persona_manager

    async def process_input(
        self,
        user_input: str,
        websocket: Optional[Any] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_type: str = TaskType.GENERAL,
        confidence_score: float = 0.5,
    ) -> Dict[str, Union[str, Dict[str, Any]]]:
        try:
            logger.info(f"Processing input: {user_input}")

            response = self.persona.generate_response(
                prompt=user_input,
                task_type=task_type,
                confidence_score=confidence_score
            )

            # Threaded memory: accumulate full conversation in one shard
            if user_id and session_id:
                thread_id = f"{user_id}-{session_id}"
                self.memory.append_to_thread(
                    thread_id=thread_id,
                    role="user",
                    content=user_input,
                    session_id=session_id,
                    metadata={
                        "task_type": task_type,
                        "confidence_score": confidence_score,
                        "model": "friday"
                    }
                )
                self.memory.append_to_thread(
                    thread_id=thread_id,
                    role="assistant",
                    content=response,
                    session_id=session_id,
                    metadata={
                        "task_type": task_type,
                        "confidence_score": confidence_score,
                        "model": "friday"
                    }
                )

            result = {
                "status": "success",
                "task_type": task_type,
                "response": response
            }

            if websocket:
                await websocket.send_json({
                    "type": "response",
                    "data": result
                })

            return result

        except Exception as e:
            logger.exception("Error while processing input")
            return {
                "status": "error",
                "error": str(e)
            }

    def execute_task(
        self,
        prompt: str,
        task_type: str,
        confidence_score: float = 0.5,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            logger.info("Executing task with prompt: %s", prompt)
            result = self.persona.generate_response(prompt, task_type, confidence_score)

            # Threaded memory: accumulate
            if user_id and session_id:
                thread_id = f"{user_id}-{session_id}"
                self.memory.append_to_thread(
                    thread_id=thread_id,
                    role="user",
                    content=prompt,
                    session_id=session_id,
                    metadata={
                        "task_type": task_type,
                        "confidence_score": confidence_score,
                        "model": "friday"
                    }
                )
                self.memory.append_to_thread(
                    thread_id=thread_id,
                    role="assistant",
                    content=result,
                    session_id=session_id,
                    metadata={
                        "task_type": task_type,
                        "confidence_score": confidence_score,
                        "model": "friday"
                    }
                )

            return {
                "status": "success",
                "task_type": task_type,
                "response": result
            }

        except Exception as e:
            logger.exception("Task execution failed")
            return {
                "status": "error",
                "error": str(e)
            }

