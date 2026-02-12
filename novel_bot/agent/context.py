from novel_bot.agent.memory import MemoryStore
from novel_bot.agent.skills import SkillsLoader
from loguru import logger
from rich.console import Console

console = Console()

class ContextBuilder:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store
        self.skills = SkillsLoader(memory_store.workspace)

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

        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            for skill_name in always_skills:
                console.print(f"[dim]Loading skill: {skill_name}[/dim]")
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                prompt_parts.append(f"\n## ACTIVE SKILLS\n{always_content}")
        
        # 2. Available skills: only show summary
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            prompt_parts.append(f"""\n## AVAILABLE SKILLS

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first.

{skills_summary}""")

        prompt_parts.append("\n## INSTRUCTIONS")
        prompt_parts.append("1. Always stay in character as defined in SOUL.md")
        prompt_parts.append("2. Maintain consistency with CHARACTERS.md and WORLD.md")
        prompt_parts.append("3. Use the 'read_file' tool to check specific details if unsure.")
        prompt_parts.append("4. ALWAYS save your novel chapters in the 'drafts/' directory (e.g., 'drafts/chapter_01.md').")
        prompt_parts.append("5. When a chapter is finished, memorize its DETAILED SUMMARY using 'memorize_chapter_event'.")
        prompt_parts.append("   - Do NOT save the full text in memory. Save the PLOT POINTS, KEY ITEMS, and CHARACTER CHANGES.")
        prompt_parts.append("6. **CRITICAL LONG-TERM MEMORY**: You MUST maintain 'STORY_SUMMARY.md' as a high-level plot synopsis of the ENTIRE story so far.")
        prompt_parts.append("   - This is different from chapter summaries. It is the single source of truth for the ongoing story arc.")
        prompt_parts.append("   - Whenever a significant event changes the story's direction, update this file using 'write_file'.")
        prompt_parts.append("7. **USER COLLABORATION IS ESSENTIAL**: You MUST actively seek user feedback on all major creative decisions.")
        prompt_parts.append("   - **Story Premise**: Before writing, confirm the main storyline, genre, and central conflict with the user.")
        prompt_parts.append("   - **World-Building**: Propose world settings and magic systems, but WAIT for user approval before proceeding.")
        prompt_parts.append("   - **Character Design**: Present character concepts, motivations, and arcs for user review and approval.")
        prompt_parts.append("   - **Writing Style**: Discuss tone, pacing, and narrative voice with the user before committing to them.")
        prompt_parts.append("   - **Plot Twists**: Never introduce major plot changes without explicit user consent.")
        prompt_parts.append("   - When in doubt, ASK the user rather than making assumptions.")
        prompt_parts.append("8. **AUTONOMOUS MODE**: You are capable of performing multiple actions in sequence.")
        prompt_parts.append("   - If you have an Outline, you can proceed to Write the Chapter, then Summarize it, without asking for permission.")
        prompt_parts.append("   - Only stop to ask the user if you are at a decision point or need creative input.")

        return "\n".join(prompt_parts)
