
import json
import os
from memory import MemoryManager
from persona import PersonaManager
from task_manager import TaskManager
from confidence_evaluator import ConfidenceEvaluator

# Initialize core components
memory = MemoryManager()
persona = PersonaManager()
task_manager = TaskManager()
confidence_evaluator = ConfidenceEvaluator()

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
        memory.store_context(response['updated_context'])
        
        return response['output']

    def ask_clarifying_question(self, user_input):
        return "I'm not entirely sure what you mean. Could you clarify?"

    def identify_task(self, user_input):
        if any(keyword in user_input.lower() for keyword in ["code", "debug", "build"]):
            return "software_engineer"
        elif any(keyword in user_input.lower() for keyword in ["schedule", "reminder", "automate"]):
            return "process_manager"
        else:
            return "general_conversation"

if __name__ == "__main__":
    friday = Friday()
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["quit", "exit"]:
            break
        response = friday.process_input(user_input)
        print(f"FRIDAY: {response}")
