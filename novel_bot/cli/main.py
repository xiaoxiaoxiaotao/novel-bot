import typer
import asyncio
import os
from typing import Optional
from pathlib import Path
from rich.console import Console

from novel_bot.agent.loop import AgentLoop
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
    (target / "drafts").mkdir(exist_ok=True)
    
    defaults = {
        "SETTINGS.md": "No writing settings have been configured yet.",
        "CHARACTERS.md": "No characters have been created yet.",
        "WORLD.md": "No world-building has been done yet.",
        "STORY_SUMMARY.md": "No chapters have been written yet.",
        "OUTLINE.md": "No story outline has been created yet.",
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
def start():
    """Start the Novel Writer Agent."""
    if not settings.NVIDIA_API_KEY and not os.environ.get("NVIDIA_API_KEY"):
         console.print("[bold red]Error:[/bold red] NVIDIA_API_KEY not found in environment or .env file.")
         return

    loop = AgentLoop()
    asyncio.run(loop.start())

if __name__ == "__main__":
    app()
