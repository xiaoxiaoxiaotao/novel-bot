from typing import Callable, Any, Dict, List
import json
import inspect
from loguru import logger
from novel_bot.agent.memory import MemoryStore

class ToolRegistry:
    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict] = []
        self._register_defaults()

    def register(self, func: Callable):
        self.tools[func.__name__] = func
        # Generate JSON schema for the function (simplified)
        # In a real app, use Pydantic or docstring parsing
        # Here we manually define schemas for the known defaults for simplicity
        # or implement a helper. 
        # For this stage, I will manually clear and rebuild schemas or just hardcode the known ones.
        return func

    def _register_defaults(self):
        # We define schemas manually here to ensure OpenAI compatibility perfection
        
        self.tools["read_file"] = self.memory.read
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the content of a file from the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "The path to the file relative to workspace root (e.g. 'story/chapter1.md')"}
                    },
                    "required": ["filename"],
                    "additionalProperties": False
                },
                "strict": True
            }
        })

        self.tools["write_file"] = self.memory.write
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file. Overwrites if exists. IMPORTANT: You MUST provide the complete 'content' parameter with the full text to write. Do NOT call this tool without content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "The path to the file relative to workspace root. Use format 'drafts/chapter_XX_Your_Title.md' (e.g., 'drafts/chapter_01_The_Beginning.md')"},
                        "content": {"type": "string", "description": "REQUIRED: The complete full text content to write into the file. Must not be empty or omitted."}
                    },
                    "required": ["filename", "content"],
                    "additionalProperties": False
                },
                "strict": True
            }
        })

        self.tools["list_files"] = self.memory.list_files
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List markdown files in the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Glob pattern (default: '*.md')"}
                    },
                    "required": ["pattern"],
                    "additionalProperties": False
                },
                "strict": True
            }
        })
        
        # Helper for appending to lists (like summary or characters)
        self.tools["append_file"] = self.memory.append
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "append_file",
                "description": "Append text to an existing file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "The path to the file relative to workspace root"},
                        "content": {"type": "string", "description": "Text content to append"}
                    },
                    "required": ["filename", "content"],
                    "additionalProperties": False
                },
                "strict": True
            }
        })
        
        # New Memory Tools
        self.tools["memorize_chapter_event"] = self.memory.save_chapter_memory
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "memorize_chapter_event",
                "description": "Save a chapter memory summary to memory/chapters/. Use this AFTER write_file to record the key events of the chapter.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chapter_title": {"type": "string", "description": "The title of the chapter. Use format 'Chapter XX: Your Title' (e.g., 'Chapter 03: The Beginning')."},
                        "memory_summary": {"type": "string", "description": "Detailed bullet points summary of plot events, item acquisition, and character status changes."}
                    },
                    "required": ["chapter_title", "memory_summary"],
                    "additionalProperties": False
                },
                "strict": True
            }
        })
        
        self.tools["memorize_important_fact"] = self.memory.update_global_memory
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "memorize_important_fact",
                "description": "Add an important fact to long-term memory (MEMORY.md).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The fact to remember (concise bullet point)."}
                    },
                    "required": ["content"],
                    "additionalProperties": False
                },
                "strict": True
            }
        })

        # Progress tracking tool
        self.tools["get_writing_progress"] = self.memory.get_writing_progress
        self.schemas.append({
            "type": "function",
            "function": {
                "name": "get_writing_progress",
                "description": "Get current writing progress: latest chapter number, total chapters written, and story completion status.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                },
                "strict": True
            }
        })

    async def execute(self, tool_call: Any) -> str:
        name = tool_call.function.name
        raw_args = tool_call.function.arguments

        # Handle potential JSON parsing issues with truncated or malformed arguments
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            # Try to fix common issues: unescaped newlines, trailing content, etc.
            try:
                # First, try a more robust approach: parse character by character
                # to handle unescaped content within strings
                cleaned = []
                i = 0
                in_string = False
                escape_next = False

                while i < len(raw_args):
                    char = raw_args[i]

                    if escape_next:
                        cleaned.append(char)
                        escape_next = False
                        i += 1
                        continue

                    if char == '\\':
                        # Check if this is escaping a quote or newline
                        if i + 1 < len(raw_args):
                            next_char = raw_args[i + 1]
                            if next_char in '"\\nrtbf':
                                cleaned.append(char)
                                escape_next = True
                            else:
                                # Backslash not followed by valid escape char - escape it
                                cleaned.append('\\\\')
                        else:
                            cleaned.append('\\\\')
                        i += 1
                        continue

                    if char == '"':
                        in_string = not in_string
                        cleaned.append(char)
                        i += 1
                        continue

                    if in_string:
                        if char == '\n':
                            cleaned.append('\\n')
                        elif char == '\r':
                            cleaned.append('\\r')
                        elif char == '\t':
                            cleaned.append('\\t')
                        else:
                            cleaned.append(char)
                    else:
                        cleaned.append(char)

                    i += 1

                cleaned_str = ''.join(cleaned)

                # If still in string at end, close it and the JSON object
                if in_string:
                    cleaned_str += '"}'

                # Try to find a valid JSON object boundary if we have unclosed braces
                brace_count = 0
                for char in cleaned_str:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1

                # Add closing braces if needed
                while brace_count > 0:
                    cleaned_str += '}'
                    brace_count -= 1

                args = json.loads(cleaned_str)
                logger.warning(f"Fixed malformed JSON arguments for tool {name}")
            except Exception as fix_error:
                logger.error(f"Failed to parse tool arguments for {name}: {raw_args[:200]}... Error: {e}, Fix error: {fix_error}")
                return f"Error: Invalid tool arguments format. Please try again with proper JSON."

        if name in self.tools:
            try:
                # Validate required parameters before execution
                sig = inspect.signature(self.tools[name])
                required_params = [
                    p.name for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty and p.name != 'self'
                ]
                missing = [p for p in required_params if p not in args]
                if missing:
                    logger.error(f"Tool {name} called with missing params: {missing}, got args: {args}")
                    if name == "write_file" and "content" in missing:
                        return f"Error: Missing required parameters: {', '.join(missing)}. You MUST provide the complete 'content' parameter with the full text to write. Do not call write_file without content."
                    return f"Error: Missing required parameters: {', '.join(missing)}"
                logger.info(f"Executing tool: {name} with args: {args}")

                result = self.tools[name](**args)
                return str(result)
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return f"Error: {e}"
        return f"Error: Tool {name} not found."
