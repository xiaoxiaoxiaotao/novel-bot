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
        2. Prioritize essential messages (user, assistant responses)
        3. Compact non-essential messages (errors, long tool results)
        4. Include tool calls/results only for recent interactions
        """
        system_prompt = self._clean_content(self.context.build_system_prompt())

        # Always include system prompt
        messages = [{"role": "system", "content": system_prompt}]

        # Separate essential and non-essential messages
        essential_msgs = [m for m in self.history if self._is_essential_message(m)]
        
        # If we have more essential messages than the limit, summarize older ones
        if len(essential_msgs) > self.MAX_CONTEXT_MESSAGES:
            # Keep recent essential messages
            recent_essential = essential_msgs[-self.MAX_CONTEXT_MESSAGES:]
            older_count = len(essential_msgs) - self.MAX_CONTEXT_MESSAGES
            summary = f"[Previous {older_count} conversation turns are stored in session memory. Key information has been saved to memory files.]"
            messages.append({"role": "system", "content": summary})
            
            # Add recent tool context (last 2 tool interactions) for continuity
            tool_msgs = [m for m in self.history if m.get("role") == "tool"][-4:]
            tool_call_msgs = [m for m in self.history if m.get("role") == "assistant" and m.get("tool_calls")][-2:]
            
            # Build context with tool calls before their results
            context_msgs = []
            for msg in recent_essential:
                if msg in tool_call_msgs or msg.get("role") in ["user", "assistant"]:
                    context_msgs.append(self._compact_message_for_context(msg))
                    
            # Add corresponding tool results
            for msg in tool_msgs:
                # Only add if the corresponding tool_call is in context
                tool_call_id = msg.get("tool_call_id", "")
                if any(tc.get("id") == tool_call_id for m in tool_call_msgs for tc in m.get("tool_calls", [])):
                    context_msgs.append(self._compact_message_for_context(msg))
                    
            messages.extend(context_msgs)
        else:
            # Compact all messages but keep them
            for msg in self.history:
                messages.append(self._compact_message_for_context(msg))

        return messages

    def _is_essential_message(self, msg: Dict) -> bool:
        """Check if a message is essential for context understanding.
        
        Essential messages: user input, assistant responses, tool calls with results
        Non-essential: error messages, debug info, system summaries
        """
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        # User messages are always essential
        if role == "user":
            return True
            
        # Assistant messages without tool calls are essential (actual responses)
        if role == "assistant":
            # If it has tool_calls, it's part of a tool chain - keep it
            if msg.get("tool_calls"):
                return True
            # If it's a text response, keep it
            if content and not content.startswith("["):
                return True
            return False
            
        # Tool results - keep them as they contain actual data
        if role == "tool":
            # Filter out error messages that are too verbose
            if content and content.startswith("Error:"):
                # Keep error but mark as non-essential for context window
                return False
            return True
            
        return False

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

    async def _handle_final_response(self, response):
        content = self._clean_content(response.content)
        if content:
            self.history.append({"role": "assistant", "content": content})
            console.print("\n[bold blue]Agent:[/bold blue]")
            console.print(Markdown(content))
