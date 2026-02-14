import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown

from novel_bot.agent.provider import LLMProvider
from novel_bot.agent.memory import MemoryStore
from novel_bot.agent.context import ContextBuilder
from novel_bot.agent.tools import ToolRegistry
from novel_bot.config.settings import settings

console = Console()

class AgentLoop:
    # Maximum messages to keep in active context (to prevent token overflow)
    # Only user and assistant messages count towards this limit
    MAX_CONTEXT_MESSAGES = 10

    def __init__(self):
        self.memory = MemoryStore(settings.workspace_path)
        self.context = ContextBuilder(self.memory)
        self.provider = LLMProvider()
        self.tools = ToolRegistry(self.memory)
        self.history: List[Dict] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._load_session()

    def _get_session_path(self) -> Path:
        """Get path for current session file."""
        sessions_dir = self.memory.workspace / "memory" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir / f"session_{self.session_id}.json"

    def _load_session(self):
        """Try to load most recent session if exists."""
        sessions_dir = self.memory.workspace / "memory" / "sessions"
        if sessions_dir.exists():
            session_files = sorted(sessions_dir.glob("session_*.json"))
            if session_files:
                latest = session_files[-1]
                try:
                    with open(latest, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.history = data.get("history", [])
                        self.session_id = data.get("session_id", self.session_id)
                        logger.info(f"Loaded previous session: {latest.name} ({len(self.history)} messages)")
                        console.print(f"[dim]Loaded previous session: {latest.name} ({len(self.history)} messages)[/dim]")
                except Exception as e:
                    logger.warning(f"Failed to load session: {e}")

    def _save_session(self):
        """Save current session to file."""
        try:
            session_path = self._get_session_path()
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump({
                    "session_id": self.session_id,
                    "timestamp": datetime.now().isoformat(),
                    "history": self.history
                }, f, ensure_ascii=False, indent=2)
            logger.debug(f"Session saved: {session_path.name}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    async def start(self):
        """Start the interactive loop."""
        console.print("[bold green]Novel Writer Agent Started.[/bold green]")
        console.print(f"Workspace: {settings.workspace_path}")
        console.print(f"Session ID: {self.session_id}")
        
        # Ensure workspace has basic files
        if not (self.memory.workspace / "SETTINGS.md").exists():
            console.print("[yellow]Warning: SETTINGS.md not found. Run 'init' command first.[/yellow]")

        while True:
            try:
                user_input = await asyncio.to_thread(input, "\nEditor > ")
                if user_input.lower() in ["exit", "quit"]:
                    self._save_session()
                    console.print(f"[dim]Session saved: session_{self.session_id}.json[/dim]")
                    break
                
                await self.process_turn(user_input)
                self._save_session()
            except KeyboardInterrupt:
                self._save_session()
                console.print(f"\n[dim]Session saved: session_{self.session_id}.json[/dim]")
                break
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")

    def _clean_content(self, content: str) -> str:
        """Remove surrogate characters that can't be encoded to UTF-8."""
        if content is None:
            return ""
        return content.encode("utf-8", errors="ignore").decode("utf-8")

    def _build_context_messages(self) -> List[Dict]:
        """Build messages for LLM context, limiting history to prevent token overflow.
        
        Strategy:
        1. Always include system prompt
        2. Keep recent messages (up to MAX_CONTEXT_MESSAGES)
        3. Ensure tool calls are always paired with results
        """
        system_prompt = self._clean_content(self.context.build_system_prompt())

        # Always include system prompt
        messages = [{"role": "system", "content": system_prompt}]

        # Prepare messages from history
        context_msgs = []
        
        # If history is too long, we need to truncate
        # We process from the end to keep the most recent interactions
        # We need to be careful not to split tool call/result pairs
        
        reversed_history = list(reversed(self.history))
        count = 0
        
        truncated = False
        
        msgs_to_add = []
        
        i = 0
        while i < len(reversed_history) and count < self.MAX_CONTEXT_MESSAGES:
            msg = reversed_history[i]
            role = msg.get("role")
            
            # If it's a tool result, we MUST include the corresponding assistant tool call
            if role == "tool":
                # Collect all sequential tool results (search forward in reversed list)
                tool_results = []
                while i < len(reversed_history) and reversed_history[i].get("role") == "tool":
                    tool_results.append(reversed_history[i])
                    i += 1
                
                # Now the next message (in reversed order) MUST be the assistant tool call
                if i < len(reversed_history) and reversed_history[i].get("role") == "assistant" and reversed_history[i].get("tool_calls"):
                    assistant_msg = reversed_history[i]
                    
                    # Check if adding these messages would exceed the limit
                    # We need to add: len(tool_results) + 1 (assistant) messages
                    # But they count as ONE logical interaction
                    total_new = len(tool_results) + 1
                    if count + 1 > self.MAX_CONTEXT_MESSAGES:
                        # Would exceed limit, stop here
                        truncated = True
                        break
                    
                    # Add execution results first (since we are reversed)
                    # Note: tool_results are [Latest, Older]. reversed(tool_results) -> [Older, Latest]
                    # We want to append to msgs_to_add: [Later, Older, Asst] ?
                    # Let's trace carefully:
                    # History: Asst -> Tool_Older -> Tool_Newer
                    # Reversed: Tool_Newer -> Tool_Older -> Asst
                    # Loop finds Tool_Newer then Tool_Older.
                    # tool_results = [Tool_Newer, Tool_Older]
                    # We append to msgs_to_add: [Tool_Newer, Tool_Older]
                    # Then we append Asst: [Tool_Newer, Tool_Older, Asst]
                    
                    # Later we reverse msgs_to_add: [Asst, Tool_Older, Tool_Newer]
                    # This is correct chronological order!
                    
                    for tr in tool_results:
                         msgs_to_add.append(self._compact_message_for_context(tr))
                    msgs_to_add.append(self._compact_message_for_context(assistant_msg))
                    
                    count += 1 
                    i += 1
                else:
                    # Orphaned tool result? Skip to avoid API error.
                    pass
                    
            elif role == "assistant" and msg.get("tool_calls"):
                # An assistant message with tool calls, but we didn't see tool results immediately before (in reversed order).
                # This implies the tool results were missing (e.g. crash before result).
                # We should SKIP this to avoid "assistant with tool call but no result" error.
                i += 1
                
            else:
                # Regular user or assistant message
                msgs_to_add.append(self._compact_message_for_context(msg))
                count += 1
                i += 1

        if i < len(reversed_history):
            truncated = True

        # Restore order
        context_msgs = list(reversed(msgs_to_add))
        
        if truncated:
             older_count = len(self.history) - len(context_msgs)
             summary = f"[Previous {older_count} messages omitted. Key information saved to memory.]"
             # Insert summary after system prompt
             messages.append({"role": "system", "content": summary})
             
        messages.extend(context_msgs)

        return messages

    def _compact_message_for_context(self, msg: Dict) -> Dict:
        """Create a compact version of a message for context window.
        Preserves essential info while reducing token usage.
        """
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Only compact error messages - keep all other content intact
        if role == "tool" and content.startswith("Error:"):
            return {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": "[Tool execution failed - see memory files for details]"
            }

        return msg

    async def process_turn(self, user_input: str):
        # 1. Update History (no pruning - keep complete history in JSON)
        self.history.append({"role": "user", "content": self._clean_content(user_input)})

        # 2. Build Context (limited history for API call)
        messages = self._build_context_messages()
        logger.debug(f"Sending {len(messages)} messages to LLM (history: {len(self.history)} total)")

        # 3. LLM Call (Think)
        console.print("[dim]Thinking...[/dim]")
        
        try:
            # Main Agent Loop (Autonomous Tool Chaining)
            current_response = await self.provider.chat(messages, tools=self.tools.schemas)
            
            MAX_LOOPS = 10
            loop_count = 0
            
            while current_response.tool_calls and loop_count < MAX_LOOPS:
                loop_count += 1
                
                # Add the assistant's tool call message to history
                tool_call_msg = {
                    "role": "assistant",
                    "content": current_response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in current_response.tool_calls
                    ]
                }
                self.history.append(tool_call_msg)
                messages.append(tool_call_msg)

                for tool_call in current_response.tool_calls:
                    console.print(f"[cyan]Using Tool: {tool_call.function.name}[/cyan]")
                    result = await self.tools.execute(tool_call)
                    
                    # Check for repeated errors and inject correction if needed
                    if "Error: Missing required parameters: content" in result:
                        # Count recent write_file errors
                        recent_errors = sum(
                            1 for msg in self.history[-10:]
                            if msg.get("role") == "tool" and "Missing required parameters: content" in msg.get("content", "")
                        )
                        if recent_errors >= 2:
                            # Add a system message to correct the behavior
                            correction = {
                                "role": "system",
                                "content": "CRITICAL: You have called write_file multiple times without providing the 'content' parameter. STOP and think: You must provide the COMPLETE text content in the 'content' parameter. Do not call write_file until you have the full content ready."
                            }
                            messages.append(correction)
                            self.history.append(correction)
                    
                    # Add tool result to history
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self._clean_content(result)
                    }
                    self.history.append(tool_msg)
                    messages.append(tool_msg)

                # Follow up (Get next thought/action)
                console.print("[dim]Thinking...[/dim]")
                current_response = await self.provider.chat(messages, tools=self.tools.schemas)
            
            # Final text response
            if current_response.tool_calls and loop_count >= MAX_LOOPS:
                # Max loops reached with pending tool calls - add them to history first
                tool_call_msg = {
                    "role": "assistant",
                    "content": current_response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in current_response.tool_calls
                    ]
                }
                self.history.append(tool_call_msg)
                messages.append(tool_call_msg)
                
                for tool_call in current_response.tool_calls:
                    console.print(f"[cyan]Using Tool: {tool_call.function.name}[/cyan]")
                    result = await self.tools.execute(tool_call)
                    
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self._clean_content(result)
                    }
                    self.history.append(tool_msg)
                    messages.append(tool_msg)
                
                # Get final response after executing remaining tools
                console.print("[dim]Thinking...[/dim]")
                current_response = await self.provider.chat(messages, tools=None)
            
            await self._handle_final_response(current_response)

        except Exception as e:
            logger.error(f"Loop Error: {e}")
            console.print(f"[red]Error:[/red] {e}")

    # Patterns that indicate model tried to use tools but output them as text instead
    TOOL_CALL_PATTERNS = [
        # you could add your own tags such as "minimax:tool_call" for minimax model to detect if it outputs tool calls as text,
        "tool_call",
    ]

    def _detect_fake_tool_calls(self, content: str) -> bool:
        """Detect if model output looks like tool calls but wasn't properly formatted."""
        if not content:
            return False
        content_lower = content.lower()
        for pattern in self.TOOL_CALL_PATTERNS:
            if pattern.lower() in content_lower:
                return True
        return False

    async def _handle_final_response(self, response):
        content = self._clean_content(response.content)

        # Check if model output looks like tool calls but wasn't properly formatted
        if self._detect_fake_tool_calls(content):
            logger.warning(f"Detected fake tool call in response: {content[:200]}...")

            # Create a system message to correct the model
            correction_msg = {
                "role": "system",
                "content": (
                    "IMPORTANT: You just output tool calls as text instead of using the actual tool system. "
                    "When you want to use a tool, you must NOT output text like 'Using Tool: xxx' or 'minimax:tool_call'. "
                    "Instead, you should use the tool_calls mechanism provided by the API. "
                    "Please try again and use the proper tool format."
                )
            }

            # Add the incorrect response to history
            self.history.append({"role": "assistant", "content": content})

            # Build new messages with correction
            messages = self._build_context_messages()
            messages.append(correction_msg)

            console.print("[dim]Correcting tool call format...[/dim]")

            # Retry with correction
            corrected_response = await self.provider.chat(messages, tools=self.tools.schemas)

            # If it still has fake tool calls, just show the content with a warning
            if self._detect_fake_tool_calls(corrected_response.content or ""):
                console.print("[yellow]Warning: Model is still not using proper tool format. Showing raw output.[/yellow]")

            await self._handle_final_response(corrected_response)
            return

        if content:
            self.history.append({"role": "assistant", "content": content})
            console.print("\n[bold blue]Agent:[/bold blue]")
            console.print(Markdown(content))
