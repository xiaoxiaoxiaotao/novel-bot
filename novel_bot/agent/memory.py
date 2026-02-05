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
            return path.read_text(encoding="utf-8")
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
            return self.global_memory_file.read_text(encoding="utf-8")
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
            return path.read_text(encoding="utf-8")
        return ""

    def save_chapter_memory(self, chapter_title: str, content: str):
        """Saves short-term memory for a chapter."""
        safe_name = "".join([c for c in chapter_title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(" ", "_")
        path = self.chapters_dir / f"{safe_name}.md"
        path.write_text(content, encoding="utf-8")
        logger.info(f"Saved chapter memory: {safe_name}")
        return f"Chapter memory for '{chapter_title}' saved."
        
    def get_recent_chapters(self, limit: int = 3) -> str:
        """Get the contents of the most recent chapter memory files."""
        # Sort by modification time? Or name? 
        # Assuming names like chapter_01, chapter_02 helps sorting.
        files = sorted(self.chapters_dir.glob("*.md"))
        recent = files[-limit:]
        
        output = []
        for f in recent:
            output.append(f"### {f.stem}\n{f.read_text(encoding='utf-8')}\n")
        
        return "\n".join(output)
