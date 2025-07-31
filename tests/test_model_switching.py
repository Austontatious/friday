import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_types import ModelType, TaskType
from model_loader import ModelLoaderWrapper

class TestModelSwitching(unittest.TestCase):

    def setUp(self):
        self.persona_manager = MagicMock()
        self.model_loader = ModelLoaderWrapper(self.persona_manager)

    def test_task_type_detection_code(self):
        """Test code task detection."""
        code_inputs = [
            "```python\ndef hello():\n    print('Hello')\n```",
            "function calculateSum(a, b) { return a + b; }",
            "class MyClass { public void doSomething() { } }",
            "import numpy as np\nimport pandas as pd",
            "for (let i = 0; i < 10; i++) { console.log(i); }",
            "if (condition) { runAction(); }"
        ]
        
        for input_text in code_inputs:
            with self.subTest(input=input_text):
                task_type = self.model_loader.detect_task_type(input_text)
                self.assertEqual(task_type, TaskType.CODE)

    def test_task_type_detection_knowledge(self):
        """Test general knowledge task detection."""
        knowledge_inputs = [
            "Who was the first president of the United States?",
            "What is the capital of France?",
            "When was the Declaration of Independence signed?",
            "How does photosynthesis work?",
            "Tell me about quantum physics",
            "Explain the theory of relativity"
        ]
        
        for input_text in knowledge_inputs:
            with self.subTest(input=input_text):
                task_type = self.model_loader.detect_task_type(input_text)
                self.assertEqual(task_type, TaskType.GENERAL_KNOWLEDGE)

    def test_task_type_detection_natural_language(self):
        """Test natural language task detection."""
        nl_inputs = [
            "Write a story about a dragon",
            "Summarize the following text",
            "Create a poem about the ocean",
            "Rewrite this paragraph to be more formal",
            "What's a creative way to explain this to a child?",
            "Translate this text to French"
        ]
        
        for input_text in nl_inputs:
            with self.subTest(input=input_text):
                task_type = self.model_loader.detect_task_type(input_text)
                self.assertEqual(task_type, TaskType.NATURAL_LANGUAGE)

    def test_model_selection_for_task(self):
        """Test model selection based on task type."""
        test_cases = [
            (TaskType.CODE, ModelType.DEEPSEEK),
            (TaskType.NATURAL_LANGUAGE, ModelType.PHI),
            (TaskType.GENERAL_KNOWLEDGE, ModelType.MIXTRAL)
        ]
        
        for task_type, expected_model in test_cases:
            with self.subTest(task=task_type, model=expected_model):
                model = self.model_loader.get_model_for_task(task_type)
                self.assertEqual(model, expected_model)

    @patch.object(ModelLoaderWrapper, 'load_model')
    @patch.object(ModelLoaderWrapper, 'is_model_loaded')
    def test_model_loading_for_task(self, mock_is_loaded, mock_load):
        """Test loading the appropriate model for a task."""
        # Test when model is already loaded
        mock_is_loaded.return_value = True
        self.model_loader.current_model_type = ModelType.DEEPSEEK
        
        self.model_loader.load_model_for_task(TaskType.CODE)
        # Should not try to load a new model
        mock_load.assert_not_called()
        
        # Test when model is not loaded
        mock_is_loaded.return_value = False
        self.model_loader.current_model_type = None
        
        self.model_loader.load_model_for_task(TaskType.NATURAL_LANGUAGE)
        # Should load the PHI model
        mock_load.assert_called_with(ModelType.PHI)

if __name__ == '__main__':
    unittest.main() 