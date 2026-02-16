import asyncio
import json
import typer
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

    def __init__(self, session_id: str = None):
        self.memory = MemoryStore(settings.workspace_path)
        self.context = ContextBuilder(self.memory)
        self.provider = LLMProvider()
        self.tools = ToolRegistry(self.memory)
        self.history: List[Dict] = []
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        if session_id:
             self._load_specific_session(session_id)
        else:
             self._load_session()

    def _load_specific_session(self, session_id: str):
         """Load a specific session by ID."""
         sessions_dir = self.memory.workspace / "memory" / "sessions"
         session_path = sessions_dir / f"session_{session_id}.json"
         if session_path.exists():
            try:
                with open(session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.session_id = data.get("session_id", self.session_id)
                    logger.info(f"Loaded session: {session_path.name}")
                    console.print(f"[dim]Loaded session: {session_path.name} ({len(self.history)} messages)[/dim]")
            except Exception as e:
                logger.warning(f"Failed to load session: {e}")


    def _get_session_path(self) -> Path:
        """Get path for current session file."""
        sessions_dir = self.memory.workspace / "memory" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir / f"session_{self.session_id}.json"

    def _load_session(self):
        """Try to load most recent session if exists."""
        sessions_dir = self.memory.workspace / "memory" / "sessions"
        if sessions_dir.exists():
            # filter out sync sessions unless they are the only ones
            all_sessions = sorted(sessions_dir.glob("session_*.json"))
            if not all_sessions:
                return

            # Prefer non-sync sessions for default load
            regular_sessions = [f for f in all_sessions if "_sync" not in f.name]
            
            if regular_sessions:
                latest = regular_sessions[-1]
            else:
                latest = all_sessions[-1]
                
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
                    
                    # Session selection on exit
                    if typer.confirm("Do you want to start a new session or load an existing one?"):
                        # List available sessions
                        sessions_dir = self.memory.workspace / "memory" / "sessions"
                        if sessions_dir.exists():
                            session_files = sorted(sessions_dir.glob("session_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
                            if session_files:
                                console.print("\n[bold]Available Sessions:[/bold]")
                                for i, f in enumerate(session_files[:5]):
                                    console.print(f"{i+1}. {f.name} ({datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')})")
                                console.print("N. New Session")
                                
                                choice = typer.prompt("Select session (number/N)", default="N")
                                if choice.upper() == "N":
                                    # Start new session
                                    console.print("[green]Starting new session...[/green]")
                                    # Reset agent state
                                    self.__init__(session_id=None)
                                    # Re-print welcome
                                    console.print(f"Session ID: {self.session_id}")
                                    continue
                                else:
                                    try:
                                        idx = int(choice) - 1
                                        if 0 <= idx < len(session_files):
                                            selected = session_files[idx]
                                            # Parse session ID from filename
                                            # session_2023... .json
                                            sid = selected.stem.replace("session_", "")
                                            console.print(f"[green]Loading session {sid}...[/green]")
                                            self.__init__(session_id=sid)
                                            console.print(f"Session ID: {self.session_id}")
                                            continue
                                    except ValueError:
                                        pass
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
        """Build messages for LLM context, keeping effective conversation history.
        
        Strategy:
        1. Always include system prompt
        2. Keep recent user/assistant messages (up to MAX_CONTEXT_MESSAGES)
        3. Keep non-write_file tool calls and results (compact form)
        4. Exclude: write_file tool calls/results (chapter content too large)
        """
        system_prompt = self._clean_content(self.context.build_system_prompt())
        messages = [{"role": "system", "content": system_prompt}]

        # Filter and compact history
        compacted = []
        skip_next_tools = False
        
        for msg in self.history:
            role = msg.get("role")
            
            # Skip system messages (corrections, etc.)
            if role == "system":
                continue
                
            # Handle write_file and memorize_chapter_event tool calls - replace with summary
            if role == "assistant" and msg.get("tool_calls"):
                # Check if any tool call needs content filtering
                tool_names = [tc.get("function", {}).get("name") for tc in msg.get("tool_calls", [])]
                is_content_tool = any(name in ("write_file", "memorize_chapter_event") for name in tool_names)

                if is_content_tool:
                    skip_next_tools = True
                    # Add summary instead of skipping entirely
                    file_paths = []
                    for tc in msg.get("tool_calls", []):
                        tool_name = tc.get("function", {}).get("name")
                        if tool_name in ("write_file", "memorize_chapter_event"):
                            try:
                                args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                                if tool_name == "write_file":
                                    file_paths.append(args.get("filename", "unknown"))
                                else:
                                    file_paths.append(f"memory: {args.get('chapter_title', 'unknown')}")
                            except:
                                pass
                    compacted.append({
                        "role": "assistant",
                        "content": f"[Saved content to: {', '.join(file_paths)}]"
                    })
                    continue
                # Keep other tool calls in compact form
                compacted.append({
                    "role": "assistant",
                    "content": f"[Using tools: {', '.join(tc.get('function', {}).get('name') for tc in msg.get('tool_calls', []))}]"
                })
                continue

            # Handle tool results for write_file
            if role == "tool":
                if skip_next_tools:
                    # Add summary for write_file result
                    content = msg.get("content", "")
                    if content.startswith("Error:"):
                        compacted.append({
                            "role": "assistant",
                            "content": "[write_file failed]"
                        })
                    else:
                        compacted.append({
                            "role": "assistant",
                            "content": "[write_file completed successfully]"
                        })
                    continue
                # Compact other tool results
                content = msg.get("content", "")
                if content.startswith("Error:"):
                    compacted.append({
                        "role": "assistant",
                        "content": "[Tool error occurred]"
                    })
                else:
                    compacted.append({
                        "role": "assistant",
                        "content": "[Tool executed successfully]"
                    })
                continue
            
            # Reset skip flag when we see a non-tool message
            skip_next_tools = False
            
            # Keep user and plain assistant messages
            if role in ("user", "assistant"):
                compacted.append(msg)

        # Take last MAX_CONTEXT_MESSAGES
        context_msgs = compacted[-self.MAX_CONTEXT_MESSAGES:]
        
        if len(compacted) > self.MAX_CONTEXT_MESSAGES:
            summary = f"[Previous {len(compacted) - len(context_msgs)} turns omitted. Key info in memory.]"
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

                normalized_tool_calls = []
                for tc in current_response.tool_calls:
                    normalized_arguments = tc.function.arguments
                    try:
                        parsed_args = self.tools.parse_arguments(tc.function.arguments, tool_name=tc.function.name)
                        normalized_arguments = json.dumps(parsed_args, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(
                            f"Using raw tool arguments for {tc.function.name} due to parse failure: {e}"
                        )
                    normalized_tool_calls.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": normalized_arguments
                        }
                    })
                
                # Add the assistant's tool call message to history
                tool_call_msg = {
                    "role": "assistant",
                    "content": current_response.content or "",
                    "tool_calls": normalized_tool_calls
                }
                self.history.append(tool_call_msg)
                messages.append(tool_call_msg)

                for tool_call in current_response.tool_calls:
                    console.print(f"[cyan]Using Tool: {tool_call.function.name}[/cyan]")
                    result = await self.tools.execute(tool_call)
                    
                    # Check for write_file content errors and inject correction immediately
                    if "Error:" in result and "write_file" in result and ("content" in result or "filename" in result):
                        # Add immediate correction for this specific error
                        correction = {
                            "role": "system",
                            "content": "CRITICAL ERROR: You called write_file but did not provide all required parameters. You MUST provide BOTH 'filename' AND 'content' parameters in a single tool call. The 'content' must contain the COMPLETE text you want to write. Do not call write_file again until you have prepared the full content."
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
                normalized_tool_calls = []
                for tc in current_response.tool_calls:
                    normalized_arguments = tc.function.arguments
                    try:
                        parsed_args = self.tools.parse_arguments(tc.function.arguments, tool_name=tc.function.name)
                        normalized_arguments = json.dumps(parsed_args, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(
                            f"Using raw tool arguments for {tc.function.name} due to parse failure: {e}"
                        )
                    normalized_tool_calls.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": normalized_arguments
                        }
                    })

                # Max loops reached with pending tool calls - add them to history first
                tool_call_msg = {
                    "role": "assistant",
                    "content": current_response.content or "",
                    "tool_calls": normalized_tool_calls
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



