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
                elif user_input.lower() == "sync":
                    await self._run_sync()
                    continue

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

    async def _run_sync(self):
        """Run sync command: check files, compare progress, and guide LLM to fix gaps.

        This is a one-off operation that does NOT record to session history.
        """
        console.print("[bold cyan]Running sync...[/bold cyan]")

        # Build sync-specific context
        sync_prompt = self._build_sync_prompt()
        messages = [{"role": "system", "content": sync_prompt}]

        # One-shot LLM call with tools
        try:
            console.print("[dim]Analyzing workspace...[/dim]")
            response = await self.provider.chat(messages, tools=self.tools.schemas)

            # Handle tool calls if any
            if response.tool_calls:
                # Add assistant message
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in response.tool_calls
                    ]
                })

                # Execute tools
                for tool_call in response.tool_calls:
                    console.print(f"[cyan]Sync Tool: {tool_call.function.name}[/cyan]")
                    result = await self.tools.execute(tool_call)

                    # Add tool result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self._clean_content(result)
                    })

                # Follow up
                console.print("[dim]Processing results...[/dim]")
                final_response = await self.provider.chat(messages, tools=self.tools.schemas)

                # Display final response
                if final_response.content:
                    console.print("\n[bold blue]Sync Result:[/bold blue]")
                    console.print(Markdown(final_response.content))
            else:
                # Direct response
                if response.content:
                    console.print("\n[bold blue]Sync Result:[/bold blue]")
                    console.print(Markdown(response.content))

            console.print("[dim]Sync complete. (Not saved to session)[/dim]")

        except Exception as e:
            logger.error(f"Sync error: {e}")
            console.print(f"[red]Sync failed:[/red] {e}")

    def _build_sync_prompt(self) -> str:
        """Build the sync prompt with file checks and progress comparison."""
        prompt_parts = ["# SYNC MODE - Workspace Analysis"]
        prompt_parts.append("You are in SYNC mode. Your task is to analyze the workspace and fix any inconsistencies.")
        prompt_parts.append("")

        CONFIGURED_LEN = 20

        # Check critical files
        critical_files = {
            "SETTINGS.md": "Story settings, tone, and style",
            "CHARACTERS.md": "Character definitions and relationships",
            "WORLD.md": "World building and setting details",
            "OUTLINE.md": "Story outline and chapter plan",
            "STORY_SUMMARY.md": "High-level story progress summary"
        }

        prompt_parts.append("## File Status Check")
        missing_or_empty = []

        for filename, description in critical_files.items():
            content = self.memory.read(filename)
            is_configured = bool(content and len(content.strip()) > CONFIGURED_LEN)
            status = "✓ OK" if is_configured else "✗ MISSING/EMPTY"
            prompt_parts.append(f"- {filename}: {status} ({description})")
            if not is_configured:
                missing_or_empty.append(filename)

        if missing_or_empty:
            prompt_parts.append("")
            prompt_parts.append(f"**ACTION REQUIRED**: Create or complete these files: {', '.join(missing_or_empty)}")
            prompt_parts.append("Use write_file to create detailed content for each missing file.")

        prompt_parts.append("")
        prompt_parts.append("## Progress Comparison")

        # Get actual progress
        progress_info = self.memory.get_writing_progress()
        prompt_parts.append(progress_info)

        # Check for chapter/memory mismatches
        import re
        from pathlib import Path

        drafts_dir = self.memory.workspace / "drafts"
        chapters_dir = self.memory.chapters_dir

        chapter_files = []
        if drafts_dir.exists():
            chapter_files = sorted([f for f in drafts_dir.glob("chapter_*.md") if re.search(r'chapter_(\d+)', f.name)])

        memory_files = []
        if chapters_dir.exists():
            memory_files = sorted([f for f in chapters_dir.glob("*.md") if re.search(r'chapter_(\d+)', f.name)])

        # Extract chapter numbers
        def extract_chapter_num(path):
            match = re.search(r'chapter_(\d+)', path.name)
            return int(match.group(1)) if match else 0

        chapter_nums = {extract_chapter_num(f) for f in chapter_files}
        memory_nums = {extract_chapter_num(f) for f in memory_files}

        missing_memories = chapter_nums - memory_nums
        orphan_memories = memory_nums - chapter_nums

        if missing_memories:
            prompt_parts.append("")
            prompt_parts.append(f"**MISSING CHAPTER MEMORIES**: Chapters {sorted(missing_memories)} have drafts but no memory summaries.")
            prompt_parts.append("For each missing chapter:")
            prompt_parts.append("1. Use read_file to read the chapter content from drafts/")
            prompt_parts.append("2. Use memorize_chapter_event to create a summary")

        if orphan_memories:
            prompt_parts.append("")
            prompt_parts.append(f"**ORPHAN MEMORIES**: Chapters {sorted(orphan_memories)} have memories but no draft files.")

        # Check STORY_SUMMARY.md against actual progress
        summary = self.memory.read("STORY_SUMMARY.md")
        latest_chapter = max(chapter_nums) if chapter_nums else 0

        if latest_chapter > 0:
            summary_chapter = 0
            if summary:
                # Try to find chapter reference in summary
                matches = re.findall(r'[Cc]hapter\s*(\d+)', summary)
                if matches:
                    summary_chapter = max(int(m) for m in matches)

            if summary_chapter < latest_chapter:
                prompt_parts.append("")
                prompt_parts.append(f"**STORY_SUMMARY OUTDATED**: Latest written chapter is {latest_chapter}, but summary only references up to chapter {summary_chapter}.")
                prompt_parts.append("Use write_file to update STORY_SUMMARY.md with current plot progress.")

        prompt_parts.append("")
        prompt_parts.append("## Instructions")
        prompt_parts.append("1. Review the status above")
        prompt_parts.append("2. Use tools to fix any issues found")
        prompt_parts.append("3. If chapter memories are missing, read the chapter file first, then call memorize_chapter_event")
        prompt_parts.append("4. Confirm what actions you took")

        return "\n".join(prompt_parts)
