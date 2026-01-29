# friday/tools/init_tools.py

from .registry import register_tool
from .code_tools import FridayCodeTools
from .refactor import refactor_code
from .debug_code import debug_code
from friday.tools.tool_executor import list_tools as get_tool_list

tools = FridayCodeTools(base_path="/workspace/ai-lab", writable_paths=["."])

register_tool(
    name="list_tools",
    description="Returns metadata for all available tools including name, description, usage hint, and parameters.",
    usage_hint="Use this to dynamically enumerate tool capabilities.",
    entrypoint=lambda: get_tool_list()
)

register_tool(
    name="list_files",
    description="Lists all source files in the codebase (like .py, .ts, .html, etc).",
    usage_hint="Use this to explore the project structure before making edits.",
    entrypoint=lambda: tools.list_files()
)

register_tool(
    name="read_file",
    description="Reads the content of a file given a relative path.",
    usage_hint="Use this to see the code before editing or debugging it.",
    entrypoint=lambda path: tools.read_file(path)
)

register_tool(
    name="write_file",
    description="Writes new content to a file, if it’s in an allowed path.",
    usage_hint="Use this after editing or generating new code.",
    entrypoint=lambda path, content: tools.write_file(path, content)
)

register_tool(
    name="refactor_code",
    description="Refactors a code snippet to improve readability, performance, or style.",
    usage_hint="Use this when the user asks to improve existing code.",
    entrypoint=lambda code, language="python", filename="", style="best_practices": refactor_code(code, language, filename, style)
)

register_tool(
    name="debug_code",
    description="Debugs a code snippet using an error message or stack trace.",
    usage_hint="Use this when the user reports a bug or provides an error log.",
    entrypoint=lambda code, language="python", error="", filename="": debug_code(code, language, error, filename)
)

from friday.memory.memory_core import memory_manager

def recall_memory(query: str = "", session_id: str = "default", k: int = 5) -> str:
    if not query:
        return "Please provide a query to search memory."

    results = memory_manager.retrieve_context(query=query, k=k, session_id=session_id)
    if not results:
        return "No relevant memories found."

    return "\n".join([
        f"- {r.get('text') or r.get('content') or '[no content]'}"
        for r in results
    ])

register_tool(
    name="recall_memory",
    description="Searches memory for relevant context based on a query string.",
    usage_hint="Use this to recall past events, preferences, or facts.",
    entrypoint=recall_memory
)

from friday.tools.web_tools import search_google

register_tool(
    name="web_search",
    description="Search Google and return the top results.",
    usage_hint="Use for real-time fact lookups or news.",
    entrypoint=search_google
)

from friday.tools.net_tools import download_file

register_tool(
    name="download_file",
    description="Downloads a file from a URL and saves it locally.",
    usage_hint="Use this to fetch external files, scripts, or datasets from the web.",
    entrypoint=lambda url, save_path="/tmp": download_file(url, save_path)
)

from friday.tools.web_tools import fetch_webpage

register_tool(
    name="fetch_webpage",
    description="Fetches the raw HTML content of a webpage.",
    usage_hint="Use this to read the source or scrape data.",
    entrypoint=lambda url: fetch_webpage(url)
)

from friday.tools.web_tools import summarize_webpage

register_tool(
    name="summarize_webpage",
    description="Downloads and summarizes the main content of a web page.",
    usage_hint="Use this to understand the content of a URL without opening it.",
    entrypoint=lambda url: summarize_webpage(url)
)

from friday.huginn.core import generate_idea

register_tool(
    name="generate_idea",
    description=(
        "Invoke Huginn, FRIDAY's symbolic imagination engine, to produce highly creative, speculative, or emotionally charged ideas. "
        "This tool excels at answering prompts that request imagination, brainstorming, symbolic visions, surreal concepts, or speculative scenarios. "
        "Use it for anything where the user wants creative thinking, alternative realities, or 'hallucinated' responses beyond literal facts."
    ),
    usage_hint=(
        "Call this tool when the prompt includes words or phrases like: 'imagine', 'dream up', 'give me a vision', "
        "'symbolic', 'get creative', 'hallucinate', 'invent', 'write a surreal idea', or 'describe a possible future'.\n"
        "Examples of good triggers:\n"
        "- 'Imagine a utopian AI society.'\n"
        "- 'Give me a wild, symbolic explanation for why the sky is blue.'\n"
        "- 'Can you hallucinate a world where gravity is reversed?'\n"
        "- 'Describe a surreal first date in the metaverse.'"
    ),
    entrypoint=lambda prompt: generate_idea(prompt)
)


def test_huginn_direct():
    from friday.huginn.core import generate_idea
    result = generate_idea("Describe a utopian AI society.", stream=True)
    print("🧠 HUGINN TEST OUTPUT:\n", result)
    
from .deepseek_tool import analyze_code

register_tool(
    name="analyze_code",
    description="Uses FRIDAY’s internal DeepSeek engine to write, fix, or refactor code.",
    usage_hint="Use when technical coding analysis is required.",
    entrypoint=analyze_code
)





