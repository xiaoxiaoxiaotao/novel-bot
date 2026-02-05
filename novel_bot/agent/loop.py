import asyncio
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
    def __init__(self):
        self.memory = MemoryStore(settings.workspace_path)
        self.context = ContextBuilder(self.memory)
        self.provider = LLMProvider()
        self.tools = ToolRegistry(self.memory)
        self.history: List[Dict] = []

    async def start(self):
        """Start the interactive loop."""
        console.print("[bold green]Novel Writer Agent Started.[/bold green]")
        console.print(f"Workspace: {settings.workspace_path}")
        
        # Ensure workspace has basic files
        if not (self.memory.workspace / "SOUL.md").exists():
            console.print("[yellow]Warning: SOUL.md not found. Run 'init' command first.[/yellow]")

        while True:
            try:
                user_input = await asyncio.to_thread(input, "\nEditor > ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                await self.process_turn(user_input)
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")

    async def process_turn(self, user_input: str):
        # 1. Update History
        self.history.append({"role": "user", "content": user_input})

        # 2. Build Context (System Prompt)
        system_prompt = self.context.build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.history

        # 3. LLM Call (Think)
        console.print("[dim]Thinking...[/dim]")
        
        try:
            response = await self.provider.chat(messages, tools=self.tools.schemas)
            
            # 4. Handle Response
            if response.tool_calls:
                # Add the assistant's tool call message to history
                self.history.append(response)
                messages.append(response)

                for tool_call in response.tool_calls:
                    console.print(f"[cyan]Using Tool: {tool_call.function.name}[/cyan]")
                    result = await self.tools.execute(tool_call)
                    
                    # Add tool result to history
                    tool_msg = {
                        "role": "tool", 
                        "tool_call_id": tool_call.id, 
                        "content": result
                    }
                    self.history.append(tool_msg)
                    messages.append(tool_msg)

                # Follow up after tool use (Get final answer)
                final_response = await self.provider.chat(messages, tools=self.tools.schemas)
                
                # Check for recursive tool calls? For now, just 1 level of recursion or handle it?
                # A simple loop handles multiple tool calls until text is produced.
                # But here we just did one round trip. 
                # Let's support one more recursion automatically if needed, or simply output.
                # If the final_response has tool calls again, this simplified loop won't handle it.
                # Ideally process_turn should be a while loop.
                
                await self._handle_final_response(final_response)

            else:
                await self._handle_final_response(response)

        except Exception as e:
            logger.error(f"Loop Error: {e}")
            console.print(f"[red]Error:[/red] {e}")

    async def _handle_final_response(self, response):
        content = response.content
        if content:
            self.history.append({"role": "assistant", "content": content})
            console.print("\n[bold blue]Agent:[/bold blue]")
            console.print(Markdown(content))
