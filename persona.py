class PersonaManager:
    def __init__(self):
        self.personas = {
            "software_engineer": "As an expert coder, FRIDAY analyzes and optimizes software tasks.",
            "process_manager": "As an efficient process manager, FRIDAY automates and schedules tasks.",
            "general_conversation": "As a helpful assistant, FRIDAY responds conversationally."
        }
        self.current_persona = "general_conversation"

    def get_prompt_for_task(self, task_type):
        """Retrieve the appropriate persona prompt for a given task."""
        if task_type in self.personas:
            self.current_persona = task_type
        return self.personas.get(task_type, self.personas["general_conversation"])

    def update_persona(self, new_persona):
        """Dynamically update persona for future tasks."""
        if new_persona in self.personas:
            self.current_persona = new_persona
        else:
            raise ValueError(f"Persona '{new_persona}' not found. Available options: {list(self.personas.keys())}")

    def get_current_persona(self):
        """Return the active persona."""
        return self.personas.get(self.current_persona, self.personas["general_conversation"])

