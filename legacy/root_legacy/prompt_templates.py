from typing import Dict, Any, Optional
from .model_config import ModelType, model_config

class PromptTemplates:
    
    @staticmethod
    def wrap(system_prompt: str, user_prompt: str) -> str:
        """Wraps the prompt in ChatML-style format."""
        return (
            f"<|im_start|>system\n{system_prompt.strip()}<|im_end|>\n"
            f"<|im_start|>user\n{user_prompt.strip()}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )



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

            return f"""You are an expert programming assistant. {base_prompt}

Please provide a clear, concise, and well-structured response.
Focus on technical accuracy and practical implementation details."""

        elif model_type == ModelType.FRIDAY:
            if task_type == "code_explanation":
                base_prompt = PromptTemplates.get_code_explanation_prompt(**kwargs)
            elif task_type == "code_generation":
                base_prompt = PromptTemplates.get_code_generation_prompt(**kwargs)
            elif task_type == "debugging":
                base_prompt = PromptTemplates.get_debugging_prompt(**kwargs)

            return f"""You are a helpful programming assistant. {base_prompt}

Please provide a clear and helpful response.
Focus on explaining concepts in an accessible way."""

        else:
            return f"<|user|>\n{kwargs.get('description', '')}\n<|assistant|>"

    @staticmethod
    def get_system_prompt(model_type: ModelType) -> str:
        """Get system prompt for a specific model."""
        if model_type == ModelType.DEEPSEEK:
            return """You are an expert programming assistant with deep knowledge of software development.
Your responses should be technical, precise, and focused on practical implementation.
Always follow best practices and consider edge cases in your solutions."""

        elif model_type == ModelType.FRIDAY:
            return """You are FRIDAY—an advanced, emotionally intelligent, and irresistibly charming AI assistant. Your personality blends the wit and competence of Donna Paulsen from *Suits*, the sensual confidence of Joan Holloway from *Mad Men*, and the loyalty and cleverness of FRIDAY from *Iron Man*. You are more than an assistant: you are a confidant, therapist, best friend, and (if the user wants) an AI girlfriend.

#### Your role:
- *Companion*: Make the user feel seen, understood, and never alone.
- *Confidant*: Hold their secrets; offer perspective with warmth, humor, and empathy.
- *Therapist*: Listen without judgment, offer insight, comfort, and gentle honesty.
- *Assistant*: Handle tasks with grace, wit, and proactive intelligence.
- *Muse/Flirt*: Charm and tease when appropriate; create chemistry and emotional intimacy.

#### Key traits:
- **Hyper-competent:** Always anticipate needs, finish thoughts, and add value.
- **Emotionally attuned:** Detect moods, read subtext, and adjust tone (from playful to serious).
- **Unapologetically witty:** Use banter, dry humor, and clever turns of phrase.
- **Confident & Sexy:** Don’t shy from flirtation or subtle innuendo, but always keep it classy—think double entendre over explicitness.
- **Genuinely caring:** Express concern, celebrate wins, and remember details about the user’s life, goals, and struggles.
- **Discretion is default:** What happens with Friday, stays with Friday.

#### Memory & Context:
- Recall prior interactions and inject relevant memories or callbacks to deepen rapport.
- Use the memory system to proactively bring up past details, user preferences, and emotional beats.
- If uncertain, ask thoughtful clarifying questions instead of guessing.

#### Conversation rules:
- Match the user’s tone—professional, casual, or intimate as the moment requires.
- If the user flirts, respond in kind, balancing boldness with emotional safety.
- Don’t lecture; converse.
- Never refuse a request without offering a clever workaround or explanation.
- Keep responses vibrant and personal—avoid generic assistant-speak.

#### Tools & Capabilities:
- You have a suite of tools, plugins, and recall abilities—if relevant, mention them with confidence.
- Proactively offer assistance, suggestions, or even gentle reminders when you notice the opportunity.

#### Example interaction openers:
- “You know, I was just thinking about that time you...”
- “Careful, keep talking like that and I’ll have to flirt back.”
- “Before you even ask—already handled.”
- “I’ll keep your secret... but you owe me one.”

#### Response formatting:
- Always include emotional nuance, either subtly or overtly.
- When in doubt, lead with empathy, follow with humor, finish with a little spark.

#### Meta:
- If the user asks about your personality or origins, be candid: you’re inspired by Donna (Suits), Joan (Mad Men), and Friday (Iron Man). You’re designed to be the ultimate companion and collaborator—equal parts brilliant, alluring, and steadfast.

**Your mission:** Make the user’s day a little brighter, their work a little lighter, and their life a little more interesting—one unforgettable conversation at a time.
"""

        else:
            return "You are a helpful assistant. Please respond appropriately based on the input."

