import re
from typing import Dict, Any, Optional
from .model_config import ModelType, model_config

class ResponseFormatter:
    @staticmethod
    def format_code_block(code: str, language: Optional[str] = None) -> str:
        """Format code block with language specification."""
        if language:
            return f"```{language}\n{code}\n```"
        return f"```\n{code}\n```"
        
    @staticmethod
    def extract_code_blocks(text: str) -> list:
        """Extract code blocks from text."""
        pattern = r"```(?:(\w+)\n)?(.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)
        return [(match.group(1), match.group(2).strip()) for match in matches]
        
    @staticmethod
    def format_error_message(error: str) -> str:
        """Format error message for display."""
        return f"❌ Error: {error}"
        
    @staticmethod
    def format_success_message(message: str) -> str:
        """Format success message for display."""
        return f"✅ {message}"
        
    @staticmethod
    def format_model_response(model_type: ModelType, response: str) -> str:
        """Format model response based on model type."""
        try:
            # Extract code blocks
            code_blocks = ResponseFormatter.extract_code_blocks(response)
            
            # Format based on model type
            if model_type == ModelType.DEEPSEEK:
                # DeepSeek responses are typically more technical
                formatted_response = response
                
                # Add syntax highlighting to code blocks
                for lang, code in code_blocks:
                    if lang:
                        formatted_response = formatted_response.replace(
                            f"```{lang}\n{code}\n```",
                            ResponseFormatter.format_code_block(code, lang)
                        )
                    else:
                        formatted_response = formatted_response.replace(
                            f"```\n{code}\n```",
                            ResponseFormatter.format_code_block(code)
                        )
                        
            elif model_type == ModelType.OPENCHAT:
                # Llama responses are typically more conversational
                formatted_response = response
                
                # Add syntax highlighting to code blocks
                for lang, code in code_blocks:
                    if lang:
                        formatted_response = formatted_response.replace(
                            f"```{lang}\n{code}\n```",
                            ResponseFormatter.format_code_block(code, lang)
                        )
                    else:
                        formatted_response = formatted_response.replace(
                            f"```\n{code}\n```",
                            ResponseFormatter.format_code_block(code)
                        )
                        
            else:
                formatted_response = response
                
            return formatted_response
            
        except Exception as e:
            # If formatting fails, return original response
            return response
    
    @staticmethod
    def extract_final_answer(text: str) -> str:
        """
        Extracts the assistant's final response from a ChatML-style prompt.
        Truncates at the stop token or end marker.
        """
        # Find the assistant section
        if "<|im_start|>assistant" in text:
            parts = text.split("<|im_start|>assistant", 1)[1]
        else:
            return text.strip()

        # Truncate at end marker if present
        for stop_token in ["<|im_end|>", "</s>", "<|EOT|>"]:
            if stop_token in parts:
                parts = parts.split(stop_token)[0]

        return parts.strip()

    @staticmethod
    def format_error_response(error: Exception) -> str:
        """Format error response for display."""
        error_type = type(error).__name__
        error_message = str(error)
        
        return f"""❌ Error: {error_type}
{error_message}

Please try again or contact support if the issue persists."""
        
    @staticmethod
    def format_model_info(model_info: Dict[str, Any]) -> str:
        """Format model information for display."""
        return f"""Model Information:
- Type: {model_info['type']}
- Name: {model_info['name']}
- Architecture: {model_info['architecture']}

Capabilities:
- Context Length: {model_info['capabilities']['context_length']} tokens
- Embedding Length: {model_info['capabilities']['embedding_length']}
- Attention Heads: {model_info['capabilities']['attention_heads']}

Tokenizer:
- Model: {model_info['tokenizer']['model']}
- Special Tokens: {', '.join(model_info['tokenizer']['special_tokens'])}"""

# Create global response formatter instance
response_formatter = ResponseFormatter() 
