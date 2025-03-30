from typing import Dict, Any, Optional
from model_types import ModelType

class PromptTemplates:
    @staticmethod
    def get_code_explanation_prompt(code: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Get prompt for code explanation task."""
        return f"""Please explain the following code in detail:

{code}

Focus on:
1. Overall purpose and functionality
2. Key components and their interactions
3. Important algorithms or patterns used
4. Potential improvements or optimizations

{context.get('additional_instructions', '') if context else ''}"""

    @staticmethod
    def get_code_generation_prompt(description: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Get prompt for code generation task."""
        return f"""Please generate code based on the following description:

{description}

Requirements:
1. Follow best practices and coding standards
2. Include appropriate error handling
3. Add comments for complex logic
4. Consider edge cases

{context.get('additional_instructions', '') if context else ''}"""

    @staticmethod
    def get_debugging_prompt(error_message: str, code: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Get prompt for debugging task."""
        return f"""Please help debug the following code that produced this error:

Error: {error_message}

Code:
{code}

Please:
1. Identify the root cause
2. Suggest specific fixes
3. Explain why the error occurred
4. Provide a corrected version

{context.get('additional_instructions', '') if context else ''}"""

    @staticmethod
    def get_model_specific_prompt(model_type: ModelType, task_type: str, **kwargs) -> str:
        """Get model-specific prompt based on task type."""
        base_prompt = ""
        
        if model_type == ModelType.DEEPSEEK:
            if task_type == "code_explanation":
                base_prompt = PromptTemplates.get_code_explanation_prompt(**kwargs)
            elif task_type == "code_generation":
                base_prompt = PromptTemplates.get_code_generation_prompt(**kwargs)
            elif task_type == "debugging":
                base_prompt = PromptTemplates.get_debugging_prompt(**kwargs)
                
            # Add DeepSeek-specific instructions
            return f"""You are an expert programming assistant. {base_prompt}

Please provide a clear, concise, and well-structured response.
Focus on technical accuracy and practical implementation details."""
            
        elif model_type == ModelType.LLAMA:
            if task_type == "code_explanation":
                base_prompt = PromptTemplates.get_code_explanation_prompt(**kwargs)
            elif task_type == "code_generation":
                base_prompt = PromptTemplates.get_code_generation_prompt(**kwargs)
            elif task_type == "debugging":
                base_prompt = PromptTemplates.get_debugging_prompt(**kwargs)
                
            # Add Llama-specific instructions
            return f"""You are a helpful programming assistant. {base_prompt}

Please provide a clear and helpful response.
Focus on explaining concepts in an accessible way."""
            
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    @staticmethod
    def get_system_prompt(model_type: ModelType) -> str:
        """Get system prompt for a specific model."""
        if model_type == ModelType.DEEPSEEK:
            return """You are an expert programming assistant with deep knowledge of software development.
Your responses should be technical, precise, and focused on practical implementation.
Always follow best practices and consider edge cases in your solutions."""
            
        elif model_type == ModelType.LLAMA:
            return """You are a helpful programming assistant with good knowledge of software development.
Your responses should be clear, accessible, and focused on explaining concepts.
Always provide practical examples and consider real-world usage."""
            
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

# Create global prompt templates instance
prompt_templates = PromptTemplates() 