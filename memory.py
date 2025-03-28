
import json
import os

class MemoryManager:
    def __init__(self):
        self.memory_file = "context.json"

    def retrieve_context(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        return {}

    def store_context(self, context):
        with open(self.memory_file, 'w') as f:
            json.dump(context, f)
