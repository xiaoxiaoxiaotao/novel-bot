import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown

from novel_bot.agent.provider import LLMProvider
from novel_bot.agent.memory import MemoryStore
from novel_bot.agent.tools import ToolRegistry
from novel_bot.config.settings import settings

console = Console()

class SyncRunner:
    def __init__(self, session_id: Optional[str] = None):
        self.memory = MemoryStore(settings.workspace_path)
        self.provider = LLMProvider()
        self.tools = ToolRegistry(self.memory)
        self.history: List[Dict] = []
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_sync"
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
                # If specifically requested session, look for it
                if self.session_id and not self.session_id.endswith("_sync"): # Default sync session is new
                     target = sessions_dir / f"session_{self.session_id}.json"
                     if target.exists():
                         latest = target
                
                # For sync, we generally start fresh unless resuming? 
                # User requirement: "defaults to creating a NEW session". 
                # So we probably don't need to load old history for sync unless specified.
                # But let's keep the file loading logic capability in case.
                pass

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

    def _clean_content(self, content: str) -> str:
        """Remove surrogate characters that can't be encoded to UTF-8."""
        if content is None:
            return ""
        return content.encode("utf-8", errors="ignore").decode("utf-8")

    def _build_sync_prompt(self) -> str:
        """Build the sync prompt with file checks and progress comparison."""
        prompt_parts = ["# SYNC MODE - Workspace Analysis"]
        prompt_parts.append("You are in SYNC mode. Your task is to analyze the workspace and fix any inconsistencies.")
        prompt_parts.append("Do NOT read all chapter files unless necessary. Focus on structural integrity.")
        prompt_parts.append("")

        # 0. Check critical files (Settings, Characters, etc.)
        critical_files = {
            "SETTINGS.md": "Story settings, tone, and style",
            "CHARACTERS.md": "Character definitions and relationships",
            "WORLD.md": "World building and setting details",
            "OUTLINE.md": "Story outline and chapter plan",
            "STORY_SUMMARY.md": "High-level story progress summary"
        }

        prompt_parts.append("## 0. Critical File Status Check")
        missing_or_empty = []
        CONFIGURED_LEN = 20

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

        # 1. Compare Chapters vs Drafts
        prompt_parts.append("## 1. Chapter vs Draft Consistency Check")
        
        import re
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
        
        status_1 = "✓ Consistent"
        if missing_memories or orphan_memories:
            status_1 = "✗ Inconsistent"

        prompt_parts.append(f"Status: {status_1}")

        if missing_memories:
            prompt_parts.append(f"- **Thinking Required**: Found drafts without memories: {sorted(missing_memories)}")
            prompt_parts.append("  Action: You must read these specific draft files and use `memorize_chapter_event` to create summaries.")

        if orphan_memories:
            prompt_parts.append(f"- **Notice**: Found memories without drafts: {sorted(orphan_memories)}")
            prompt_parts.append("  Action: Check if these are stale or if drafts were deleted.")
            
        prompt_parts.append("")

        # 2. Check Progress vs Summary
        prompt_parts.append("## 2. Story Progress vs Summary Alignment")
        
        # Get actual progress
        progress_info = self.memory.get_writing_progress()
        prompt_parts.append(f"**Detected Progress**: {progress_info}")

        # Check STORY_SUMMARY.md
        summary_content = self.memory.read("STORY_SUMMARY.md")
        prompt_parts.append("")
        if summary_content:
            prompt_parts.append("**Current STORY_SUMMARY.md Content**:")
            prompt_parts.append("```markdown")
            prompt_parts.append(summary_content[:2000] + ("\n... (truncated)" if len(summary_content) > 2000 else ""))
            prompt_parts.append("```")
        else:
            prompt_parts.append("**Current STORY_SUMMARY.md**: [EMPTY/MISSING]")
            
        prompt_parts.append("")
        prompt_parts.append("## Instructions")
        prompt_parts.append("1. **First**, check '0. Critical File Status Check'. If critical files are missing, use `write_file` to create them.")
        prompt_parts.append("2. **Next**, address any inconsistencies in '1. Chapter vs Draft Consistency Check'.")
        prompt_parts.append("   - If memories are missing, read the corresponding draft and generate the memory.")
        prompt_parts.append("3. **Finally**, compare '2. Story Progress vs Summary Alignment'.")
        prompt_parts.append("   - If the summary is outdated (e.g., missing recent chapters), rewrite it using `write_file`.")
        prompt_parts.append("4. Confirm when synchronization is complete.")

        return "\n".join(prompt_parts)



    async def run(self):
        """Run sync command: check files, compare progress, and guide LLM to fix gaps."""
        console.print("[bold cyan]Running sync...[/bold cyan]")
        console.print(f"Session ID: {self.session_id}")

        # Build sync-specific context
        sync_prompt = self._build_sync_prompt()
        console.print(f"[dim]Sync Prompt Length: {len(sync_prompt)} chars[/dim]")
        
        # We start with a system message
        self.history = [{"role": "system", "content": sync_prompt}]
        self._save_session()

        try:
            console.print("[dim]Analyzing workspace...[/dim]")
            
            # Initial analysis (triggers tool usage based on prompt)
            await self._process_turn()

            # Enter interactive loop
            while True:
                user_input = await asyncio.to_thread(input, "\nSync > ")
                if user_input.lower() in ["exit", "quit"]:
                    self._save_session()
                    console.print(f"[dim]Session saved: session_{self.session_id}.json[/dim]")
                    break
                
                # Add user input
                self.history.append({"role": "user", "content": user_input})
                self._save_session()

                await self._process_turn()

        except KeyboardInterrupt:
            self._save_session()
            console.print(f"\n[dim]Session saved: session_{self.session_id}.json[/dim]")
        except Exception as e:
            logger.error(f"Sync error: {e}")
            console.print(f"[red]Sync failed:[/red] {e}")

    async def _process_turn(self, depth: int = 0):
        """Process a conversation turn, handling tool calls recursively."""
        if depth >= 10:
            console.print("[red]Max tool recursion depth reached. Stopping execution.[/red]")
            return

        response = await self.provider.chat(self.history, tools=self.tools.schemas)

        # Handle tool calls if any
        if response.tool_calls:
            # Add assistant message with tool calls
            assistant_msg = {
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
            }
            self.history.append(assistant_msg)
            self._save_session()

            # Execute tools
            for tool_call in response.tool_calls:
                console.print(f"[cyan]Sync Tool: {tool_call.function.name}[/cyan]")
                result = await self.tools.execute(tool_call)

                # Add tool result
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": self._clean_content(result)
                }
                self.history.append(tool_msg)
                self._save_session()

            # Recursively process the results (so the model can see tool output and respond/use more tools)
            # This handles the "continue running" part for multi-step tasks
            await self._process_turn(depth + 1)
        else:

            # Final text response
            if response.content:
                assistant_msg = {
                    "role": "assistant",
                    "content": self._clean_content(response.content)
                }
                self.history.append(assistant_msg)
                self._save_session()
                
                console.print("\n[bold blue]Sync Result:[/bold blue]")
                console.print(Markdown(response.content))

