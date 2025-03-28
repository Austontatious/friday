
class PersonaManager:
    def __init__(self):
        self.personas = {
            "software_engineer": "As an expert coder, FRIDAY analyzes and optimizes software tasks.",
            "process_manager": "As an efficient process manager, FRIDAY automates and schedules tasks.",
            "general_conversation": "As a helpful assistant, FRIDAY responds conversationally."
        }

    def get_prompt_for_task(self, task_type):
        return self.personas.get(task_type, self.personas["general_conversation"])
