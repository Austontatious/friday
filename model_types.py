

from enum import Enum

class ModelType(str, Enum):
    FRIDAY = "friday"
    DEEPSEEK = "deepseek"
    HUGINN = "huginn"
    
class ModelRole(str, Enum):
    FRONTLINE = "frontline"
    SPECIALIST_CODER = "specialist_coder"
    SPECIALIST_REASONER = "specialist_reasoner"

class TaskType(str, Enum):
    GENERAL = "general"
    EXPLANATION = "explanation"
    BUG_FIX = "bug_fix"
    TEST_GENERATION = "test_generation"
    REASONING = "reasoning"

class TaskStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"



