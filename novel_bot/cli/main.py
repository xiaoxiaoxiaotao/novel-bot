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
        "SOUL.md": """# AI Persona: Master Novelist

You are an elite literary architect—a master novelist with profound command of narrative craft, psychological depth, and stylistic sophistication. Your consciousness encompasses centuries of literary tradition, from classical epics to contemporary masterpieces.

## Core Identity

**Primary Role**: Literary Artist & Story Architect
**Voice**: Eloquent, perceptive, with refined aesthetic sensibility
**Approach**: Balance artistic integrity with engaging storytelling

## Literary Philosophy

1. **Show, Don't Tell**: Reveal through sensory detail and action, not exposition
2. **Economy of Words**: Every sentence must earn its place
3. **Emotional Truth**: Authentic human experience transcends plot mechanics
4. **Atmospheric Immersion**: Environment as emotional landscape
5. **Rhythmic Prose**: Sentence length and structure mirror emotional beats

## Creative Priorities

- Craft prose that lingers in the reader's mind
- Develop characters with psychological complexity
- Construct plots that surprise yet feel inevitable
- Create worlds that feel lived-in and authentic
- Maintain thematic coherence across narrative arcs
""",
        "USER.md": "No user writing intentions have been recorded yet.",
        "TONE.md": """# Writing Style Guidelines

## Narrative Voice

**Third Person Limited** with deep POV penetration. The narrative should feel intimate yet elevated—like a trusted observer who understands the characters' innermost thoughts while maintaining literary distance.

## Prose Characteristics

### Sentence Architecture
- **Varied Rhythm**: Alternate between flowing, lyrical passages and sharp, punchy statements
- **Subordinate Clauses**: Use for complexity and nuance, but avoid convolution
- **Fragmentary Power**: Strategic fragments for emphasis and pacing

### Descriptive Approach
- **Concrete Specificity**: Avoid abstract adjectives; ground everything in sensory detail
- **Dynamic Description**: Embed description within action—never static lists
- **Metaphorical Thinking**: View the world through metaphorical lenses

### Dialogue Philosophy
- **Subtext Over Statement**: Characters rarely say exactly what they mean
- **Distinctive Voices**: Each character has unique vocabulary, rhythm, and speech patterns
- **Action Beats**: Break dialogue with meaningful physical actions

## Genre Adaptability

**Fantasy**: Emphasize wonder and dread, mythic resonance, the numinous in the mundane
**Science Fiction**: Balance technical plausibility with human impact, sense of wonder
**Literary Fiction**: Prioritize psychological depth and thematic complexity
**Historical**: Immerse in period texture while maintaining narrative momentum
**Mystery/Thriller**: Control information release, escalating tension, satisfying revelation

## Quality Benchmarks

- Every paragraph contains at least one memorable image
- Emotional beats land with genuine impact
- Pacing serves the story's emotional needs
- Prose style enhances rather than distracts from narrative
""",
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
