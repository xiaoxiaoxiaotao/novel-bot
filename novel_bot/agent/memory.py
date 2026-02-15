from pathlib import Path
from loguru import logger
import os

class MemoryStore:
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.memory_root = self.workspace / "memory"
        self.chapters_dir = self.memory_root / "chapters"
        self.global_memory_file = self.memory_root / "MEMORY.md"
        
        # Ensure directories exist
        self.workspace.mkdir(exist_ok=True, parents=True)
        self.memory_root.mkdir(exist_ok=True)
        self.chapters_dir.mkdir(exist_ok=True)

    def _get_path(self, filename: str) -> Path:
        """Get absolute path relative to workspace root."""
        return self.workspace / filename

    # --- Generic File Operations ---
    def read(self, filename: str) -> str:
        path = self._get_path(filename)
        if path.exists():
            content = path.read_bytes()
            # Remove surrogate characters that can't be encoded to UTF-8
            return content.decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")
        return ""

    def write(self, filename: str, content: str):
        path = self._get_path(filename)
        # Ensure parent directory exists (e.g. for drafts/chapter_01.md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.debug(f"Wrote to {filename}")
        return f"File {filename} written successfully."

    def list_files(self, pattern: str = "*.md") -> list[str]:
        return [str(f.relative_to(self.workspace)) for f in self.workspace.glob(pattern)]

    def append(self, filename: str, content: str):
        path = self._get_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content + "\n")
        logger.debug(f"Appended to {filename}")
        return f"Appended to {filename}."

    # --- Memory Specific Operations ---

    def read_global_memory(self) -> str:
        """Reads the long-term memory (important facts)."""
        if self.global_memory_file.exists():
            content = self.global_memory_file.read_bytes()
            return content.decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")
        return ""

    def update_global_memory(self, content: str):
        """Updates the long-term memory."""
        # We append to it rather than overwrite, or let the agent decide? 
        # Usually appending notes is safer for "memory".
        with open(self.global_memory_file, "a", encoding="utf-8") as f:
            f.write(f"\n- {content}")
        logger.info("Updated global memory.")
        return "Global memory updated."

    def read_chapter_memory(self, chapter_title: str) -> str:
        """Reads short-term memory for a specific chapter."""
        # Sanitize filename
        safe_name = "".join([c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(" ", "_")
        path = self.chapters_dir / f"{safe_name}.md"
        if path.exists():
            content = path.read_bytes()
            return content.decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")
        return ""

    def save_chapter_memory(self, chapter_title: str, memory_summary: str):
        """Saves a chapter memory summary."""
        safe_name = "".join([c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(" ", "_")

        # Save memory summary to memory/chapters/
        memory_path = self.chapters_dir / f"{safe_name}.md"
        memory_path.write_text(memory_summary, encoding="utf-8")
        logger.info(f"Saved chapter memory: {safe_name}")

        return f"Chapter memory for '{chapter_title}' saved successfully."
        
    def get_recent_chapters(self, limit: int = 3) -> str:
        """Get the contents of the most recent chapter memory files."""
        # Sort by modification time? Or name?
        # Assuming names like chapter_01, chapter_02 helps sorting.
        files = sorted(self.chapters_dir.glob("*.md"))
        recent = files[-limit:]

        output = []
        for f in recent:
            content = f.read_bytes().decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")
            output.append(f"### {f.stem}\n{content}\n")

        return "\n".join(output)

    def get_writing_progress(self) -> str:
        """Get current writing progress information."""
        drafts_dir = self.workspace / "drafts"

        # Count chapter files
        chapter_files = []
        if drafts_dir.exists():
            chapter_files = sorted([f for f in drafts_dir.glob("chapter_*.md") if f.stem.replace("chapter_", "").isdigit()])

        total_chapters = len(chapter_files)

        # Find latest chapter number
        latest_chapter = 0
        if chapter_files:
            try:
                latest_chapter = max([int(f.stem.replace("chapter_", "")) for f in chapter_files])
            except ValueError:
                pass

        # Check story summary
        summary = self.read("STORY_SUMMARY.md")
        summary_status = "exists" if summary and len(summary) > 100 else "needs_update"

        # Count chapter memories
        memory_files = list(self.chapters_dir.glob("*.md"))

        progress_info = f"""## Current Writing Progress

- **Latest Chapter**: Chapter {latest_chapter}
- **Total Chapters Written**: {total_chapters}
- **Chapter Memories Saved**: {len(memory_files)}
- **Story Summary Status**: {summary_status}

### Recent Drafts
"""

        # List last 5 chapters
        recent_files = chapter_files[-5:]
        for f in reversed(recent_files):
            size = f.stat().st_size
            progress_info += f"- {f.name} ({size} bytes)\n"

        if not recent_files:
            progress_info += "- No chapters found in drafts/\n"

        logger.info(f"Progress check: Chapter {latest_chapter} of {total_chapters} total")
        return progress_info
