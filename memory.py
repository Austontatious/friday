import json
import os
import shutil

class MemoryManager:
    def __init__(self):
        self.memory_file = "context.json"
        self.backup_file = "context_backup.json"

    def retrieve_context(self):
        """Retrieve the most recent context from the file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print("⚠️ Error reading context. Attempting backup restore...")
                return self.restore_backup()
        return {}

    def store_context(self, context):
        """Store updated context and create a backup."""
        try:
            # Backup previous context
            if os.path.exists(self.memory_file):
                shutil.copy(self.memory_file, self.backup_file)
            # Save updated context
            with open(self.memory_file, 'w') as f:
                json.dump(context, f, indent=4)
        except (IOError, json.JSONDecodeError) as e:
            print(f"⚠️ Error saving context: {e}")

    def restore_backup(self):
        """Restore context from backup in case of failure."""
        if os.path.exists(self.backup_file):
            shutil.copy(self.backup_file, self.memory_file)
            with open(self.backup_file, 'r') as f:
                return json.load(f)
        return {}

    def reset_memory(self):
        """Clear all stored context and backup."""
        if os.path.exists(self.memory_file):
            os.remove(self.memory_file)
        if os.path.exists(self.backup_file):
            os.remove(self.backup_file)
        print("✅ Memory reset complete. Context and backup cleared.")

