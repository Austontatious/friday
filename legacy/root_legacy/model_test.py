# --- model_test.py ---
from friday.model_types import TaskType, get_model_role, ROLE_TO_MODEL

def test_task_to_model_mapping():
    for task_type in TaskType:
        model_role = get_model_role(task_type)
        model_type = ROLE_TO_MODEL.get(model_role)
        print(f"TaskType: {task_type.value:15} → Role: {model_role.value:20} → ModelType: {model_type.value}")

if __name__ == "__main__":
    test_task_to_model_mapping()

