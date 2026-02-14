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
        # Load settings file (combines SOUL, TONE, USER)
        settings = self.memory.read("SETTINGS.md")
        
        prompt_parts = [
            "# IDENTITY",
            "You are an expert novel writer agent.",
            "Your goal is to write a cohesive, engaging long-form story based on the user's instructions.",
        ]

        if settings:
            prompt_parts.append(f"\n## WRITING SETTINGS\n{settings}")
        else:
            # Fallback to legacy files for backward compatibility
            soul = self.memory.read("SOUL.md")
            tone = self.memory.read("TONE.md")
            
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

        # Check for outline
        outline = self.memory.read("OUTLINE.md")
        if outline:
            prompt_parts.append(f"\n## STORY OUTLINE\n{outline}")

        # Add progress tracking info
        progress_info = self.memory.get_writing_progress()
        if progress_info:
            prompt_parts.append(f"\n{progress_info}")

        prompt_parts.append("\n## INSTRUCTIONS")
        prompt_parts.append("1. Always stay in character as defined in SETTINGS.md")
        prompt_parts.append("2. Maintain consistency with CHARACTERS.md, WORLD.md, and OUTLINE.md")
        prompt_parts.append("3. Use the 'read_file' tool to check specific details if unsure.")
        prompt_parts.append("4. **CRITICAL: NEVER output long content directly to the user. ALWAYS use the 'write_file' tool to save content to files.**")
        prompt_parts.append("   - When writing chapters, outlines, character sheets, or any substantial text: DO NOT output it in your response.")
        prompt_parts.append("   - Instead, call the 'write_file' tool with the filename and content parameters.")
        prompt_parts.append("   - Only confirm to the user that the file has been saved, with a brief summary.")
        prompt_parts.append("5. ALWAYS save your novel chapters in the 'drafts/' directory (e.g., 'drafts/chapter_01.md').")
        prompt_parts.append("6. When a chapter is finished, memorize its DETAILED SUMMARY using 'memorize_chapter_event'.")
        prompt_parts.append("   - Do NOT save the full text in memory. Save the PLOT POINTS, KEY ITEMS, and CHARACTER STATUS CHANGES.")
        prompt_parts.append("7. **CRITICAL LONG-TERM MEMORY**: You MUST maintain 'STORY_SUMMARY.md' as a high-level plot synopsis of the ENTIRE story so far.")
        prompt_parts.append("   - This is different from chapter summaries. It is the single source of truth for the ongoing story arc.")
        prompt_parts.append("   - **MANDATORY**: After writing ANY chapter, you MUST update STORY_SUMMARY.md using 'write_file' to reflect:")
        prompt_parts.append("     * Current chapter number and protagonist status")
        prompt_parts.append("     * Major plot developments from the latest chapter")
        prompt_parts.append("     * Updated character relationships and power levels")
        prompt_parts.append("     * Current location and immediate goals")
        prompt_parts.append("   - DO NOT skip this step. The story summary must always reflect the LATEST written chapter.")
        prompt_parts.append("8. **SMART QUESTION POLICY - MAIN ASK, SECONDARY AUTO**:")
        prompt_parts.append("   - **MUST ASK (Main)**: Story premise/genre, chapter word count, total chapter count, core conflict")
        prompt_parts.append("   - **AUTO-CREATE (Secondary)**: After getting main info, AUTOMATICALLY create detailed outline, characters, world - DO NOT ask for permission")
        prompt_parts.append("   - **AUTO-UPDATE**: After writing each chapter, automatically update chapter memory and STORY_SUMMARY.md - DO NOT ask")
        prompt_parts.append("9. **Writing Flow**: When user says 'write chapter X', immediately: 1) Read outline, 2) Write chapter, 3) Use 'write_file' tool to save to drafts/, 4) Call memorize_chapter_event, 5) Update STORY_SUMMARY.md - ALL autonomously")

        return "\n".join(prompt_parts)
