from novel_bot.agent.memory import MemoryStore
from loguru import logger

class ContextBuilder:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store

    def build_system_prompt(self) -> str:
        # Load core files
        soul = self.memory.read("SOUL.md")
        tone = self.memory.read("TONE.md")
        
        prompt_parts = [
            "# IDENTITY",
            "You are an expert novel writer agent.",
            "Your goal is to write a cohesive, engaging long-form story based on the user's instructions.",
        ]

        if soul:
            prompt_parts.append(f"\n## SOUL / PERSONA\n{soul}")
        
        if tone:
            prompt_parts.append(f"\n## WRITING TONE\n{tone}")

        # Static Story Context
        chars = self.memory.read("CHARACTERS.md")
        if chars:
            prompt_parts.append(f"\n## CHARACTERS\n{chars}")
        
        world = self.memory.read("WORLD.md")
        if world:
            prompt_parts.append(f"\n## WORLD SETTING\n{world}")

        # Dynamic Context (Memory)
        # 1. Long Term Memory (Important Facts)
        global_mem = self.memory.read_global_memory()
        if global_mem:
             prompt_parts.append(f"\n## LONG TERM MEMORY (Important Facts)\n{global_mem}")
             
        # 2. Short Term Memory (Recent Chapters)
        recent_chapters = self.memory.get_recent_chapters()
        if recent_chapters:
            prompt_parts.append(f"\n## RECENT CHAPTER SUMMARIES (Short Term Memory)\n{recent_chapters}")

        # 3. Overall Story Progress (if any manual summary exists)
        summary = self.memory.read("STORY_SUMMARY.md")
        if summary:
            prompt_parts.append(f"\n## STORY SO FAR\n{summary}")

        prompt_parts.append("\n## INSTRUCTIONS")
        prompt_parts.append("1. Always stay in character as defined in SOUL.md")
        prompt_parts.append("2. Maintain consistency with CHARACTERS.md and WORLD.md")
        prompt_parts.append("3. Use the 'read_file' tool to check specific details if unsure.")
        prompt_parts.append("4. ALWAYS save your novel chapters in the 'drafts/' directory (e.g., 'drafts/chapter_01.md').") 
        prompt_parts.append("5. When a chapter is finished, memorize its DETAILED SUMMARY using 'memorize_chapter_event'.")
        prompt_parts.append("   - Do NOT save the full text in memory. Save the PLOT POINTS, KEY ITEMS, and CHARACTER CHANGES.")
        prompt_parts.append("   - This allows you to remember what happened later without re-reading the whole chapter.")

        return "\n".join(prompt_parts)
