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
    MAX_CONTEXT_MESSAGES = 10
    # Maximum messages to keep in stored history
    MAX_STORED_HISTORY = 100

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
        """Build messages for LLM context, limiting history to prevent token overflow."""
        system_prompt = self._clean_content(self.context.build_system_prompt())

        # Always include system prompt
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation summary if history is long
        if len(self.history) > self.MAX_CONTEXT_MESSAGES:
            # Add a summary message about older context
            older_count = len(self.history) - self.MAX_CONTEXT_MESSAGES
            summary = f"[Previous {older_count} messages are stored in session memory and not shown here to conserve context space. Key information has been saved to memory files.]"
            messages.append({"role": "system", "content": summary})
            # Only include recent messages
            recent_history = self.history[-self.MAX_CONTEXT_MESSAGES:]
        else:
            recent_history = self.history

        messages.extend(recent_history)
        return messages

    def _prune_history(self):
        """Prune history if it exceeds maximum stored size."""
        if len(self.history) > self.MAX_STORED_HISTORY:
            # Keep first message (if system-like) and last N messages
            self.history = self.history[-self.MAX_STORED_HISTORY:]
            logger.info(f"History pruned to {self.MAX_STORED_HISTORY} messages")

    async def process_turn(self, user_input: str):
        # 1. Update History
        self.history.append({"role": "user", "content": self._clean_content(user_input)})
        self._prune_history()

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
