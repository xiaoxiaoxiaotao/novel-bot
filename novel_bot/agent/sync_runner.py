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

    async def run(self):
        """Run sync command: check files, compare progress, and guide LLM to fix gaps."""
        console.print("[bold cyan]Running sync...[/bold cyan]")
        console.print(f"Session ID: {self.session_id}")

        # Build sync-specific context
        sync_prompt = self._build_sync_prompt()
        console.print(f"[dim]Sync Prompt Length: {len(sync_prompt)} chars[/dim]")
        
        # We start with a system message
        messages = [{"role": "system", "content": sync_prompt}]
        self.history = list(messages) # Copy to history
        self._save_session()

        # One-shot LLM call with tools
        try:
            console.print("[dim]Analyzing workspace...[/dim]")
            response = await self.provider.chat(messages, tools=self.tools.schemas)

            # Handle tool calls if any
            if response.tool_calls:
                # Add assistant message
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
                messages.append(assistant_msg)
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
                    messages.append(tool_msg)
                    self.history.append(tool_msg)
                    self._save_session()

                # Follow up
                console.print("[dim]Processing results...[/dim]")
                final_response = await self.provider.chat(messages, tools=self.tools.schemas)

                # Add final response
                if final_response.content:
                    final_msg = {
                        "role": "assistant",
                        "content": self._clean_content(final_response.content)
                    }
                    self.history.append(final_msg)
                    self._save_session()

                # Display final response
                if final_response.content:
                    console.print("\n[bold blue]Sync Result:[/bold blue]")
                    console.print(Markdown(final_response.content))
            else:
                # Direct response
                if response.content:
                    assistant_msg = {
                        "role": "assistant",
                        "content": self._clean_content(response.content)
                    }
                    self.history.append(assistant_msg)
                    self._save_session()
                    
                    console.print("\n[bold blue]Sync Result:[/bold blue]")
                    console.print(Markdown(response.content))

            console.print(f"[dim]Sync complete. Session saved: session_{self.session_id}.json[/dim]")

        except Exception as e:
            logger.error(f"Sync error: {e}")
            console.print(f"[red]Sync failed:[/red] {e}")
