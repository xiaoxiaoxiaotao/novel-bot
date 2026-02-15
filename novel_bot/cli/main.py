import typer
import asyncio
import os
import json
from datetime import datetime
from typing import Optional
from pathlib import Path
from rich.console import Console

from novel_bot.agent.loop import AgentLoop
from novel_bot.agent.sync_runner import SyncRunner
from novel_bot.config.settings import settings

app = typer.Typer()
console = Console()

@app.command()
def init(
    path: str = typer.Option("workspace", help="Path to create workspace")
):
    """Initialize a new Novel Writer workspace."""
    target = Path(path)
    if target.exists():
        console.print(f"[yellow]Workspace {target} already exists.[/yellow]")
        if not typer.confirm("Do you want to overwrite default files?"):
            return

    target.mkdir(parents=True, exist_ok=True)
    (target / "memory").mkdir(exist_ok=True)
    (target / "memory" / "chapters").mkdir(exist_ok=True)
    (target / "memory" / "sessions").mkdir(exist_ok=True)
    (target / "drafts").mkdir(exist_ok=True)

    defaults = {
        "SETTINGS.md": "",
        "CHARACTERS.md": "",
        "WORLD.md": "",
        "STORY_SUMMARY.md": "",
        "OUTLINE.md": "",
    }

    for filename, content in defaults.items():
        file_path = target / filename
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")
            console.print(f"Created [green]{filename}[/green]")
        else:
            console.print(f"Skipped [dim]{filename}[/dim] (exists)")

    console.print(f"\n[bold green]Workspace initialized at {target}[/bold green]")
    console.print("Run 'start' to begin.")

@app.command()
def start(
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to load")
):
    """Start the Novel Writer Agent."""
    if not settings.NVIDIA_API_KEY and not os.environ.get("NVIDIA_API_KEY"):
         console.print("[bold red]Error:[/bold red] NVIDIA_API_KEY not found in environment or .env file.")
         return

    loop = AgentLoop(session_id=session)
    asyncio.run(loop.start())

@app.command()
def sync():
    """Run workspace sync check with a new session."""
    if not settings.NVIDIA_API_KEY and not os.environ.get("NVIDIA_API_KEY"):
         console.print("[bold red]Error:[/bold red] NVIDIA_API_KEY not found in environment or .env file.")
         return

    # Create a new session for sync
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_sync"
    runner = SyncRunner(session_id=session_id)
    asyncio.run(runner.run())

if __name__ == "__main__":
    app()
