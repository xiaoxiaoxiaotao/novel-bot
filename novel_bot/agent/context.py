from novel_bot.agent.memory import MemoryStore
from novel_bot.agent.skills import SkillsLoader
from loguru import logger
from rich.console import Console

from novel_bot.config import settings

console = Console()

class ContextBuilder:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store
        self.skills = SkillsLoader(memory_store.workspace)

    def build_system_prompt(self) -> str:
        
        prompt_parts = [
            "# IDENTITY",
            "You are an expert novel writer agent.",
            "Your goal is to write a cohesive, engaging long-form story based on the user's instructions.",
        ]

        CONFIGURED_LEN = 20

        # Static Story Context
        settings = self.memory.read("SETTINGS.md")
        settings_configured = bool(settings and len(settings.strip()) > CONFIGURED_LEN)
        if settings_configured:
            prompt_parts.append(f"\n## SETTINGS\n{settings}")

        chars = self.memory.read("CHARACTERS.md")
        chars_configured = bool(chars and len(chars.strip()) > CONFIGURED_LEN)
        if chars_configured:
            prompt_parts.append(f"\n## CHARACTERS\n{chars}")

        world = self.memory.read("WORLD.md")
        world_configured = bool(world and len(world.strip()) > CONFIGURED_LEN)
        if world_configured:
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
        summary_configured = bool(summary and len(summary.strip()) > CONFIGURED_LEN)
        if summary_configured:
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
        outline_configured = bool(outline and len(outline.strip()) > CONFIGURED_LEN)
        if outline_configured:
            prompt_parts.append(f"\n## STORY OUTLINE\n{outline}")

        # Add progress tracking info
        progress_info = self.memory.get_writing_progress()
        if progress_info:
            prompt_parts.append(f"\n{progress_info}")

        # Check if memory sync is needed
        memory_sync_reminder = self._get_memory_sync_reminder()
        if memory_sync_reminder:
            prompt_parts.append(f"\n{memory_sync_reminder}")

        prompt_parts.append("\n## INSTRUCTIONS")

        missing_critical = []
        if not settings_configured: missing_critical.append("SETTINGS.md")
        if not chars_configured: missing_critical.append("CHARACTERS.md")
        if not world_configured: missing_critical.append("WORLD.md")
        if not outline_configured: missing_critical.append("OUTLINE.md")
        if not summary_configured: missing_critical.append("STORY_SUMMARY.md")
        
        if missing_critical:
            prompt_parts.append(f"0. **CRITICAL CONFIGURATION NEEDED**: The following files are missing or unconfigured: {', '.join(missing_critical)}.")
            prompt_parts.append("   - Your PRIMARY GOAL is to establish these story elements before writing chapters.")
            prompt_parts.append("   - **USE THE 'story-design' SKILL**: Read the skill file first with `read_file` on 'skills/story-design/SKILL.md', then follow its guidance to create all missing configuration files.")
            prompt_parts.append("   - The story-design skill will guide you through creating: SETTINGS.md (persona & style), CHARACTERS.md, WORLD.md, and OUTLINE.md.")
            prompt_parts.append(f"   - **MANDATORY**: Use `write_file` tool to save the configuration. Content must be detailed (>{CONFIGURED_LEN} characters) to be considered configured.")

        prompt_parts.append("1. Always stay in character as defined in CHARACTERS.md and the tone defined in SETTINGS.md. Do NOT break character or tone under any circumstances.")
        prompt_parts.append("2. Maintain consistency with CHARACTERS.md, WORLD.md, and OUTLINE.md")
        prompt_parts.append("3. Use the 'read_file' tool to check specific details if unsure.")
        prompt_parts.append("4. **CRITICAL: NEVER output long content directly to the user. ALWAYS use the 'write_file' tool to save content to files.**")
        prompt_parts.append("   - When writing chapters, outlines, character sheets, or any substantial text: DO NOT output it in your response.")
        prompt_parts.append("   - Instead, call the 'write_file' tool with BOTH the filename AND content parameters.")
        prompt_parts.append("   - **MANDATORY**: The 'content' parameter MUST contain the complete text. NEVER call write_file without providing the full content.")
        prompt_parts.append("   - **JSON ESCAPING CRITICAL**: When providing 'content' in the tool call, you MUST properly escape it for JSON:")
        prompt_parts.append("     * Replace all backslashes (\\) with double backslashes (\\\\)")
        prompt_parts.append("     * Replace all double quotes (\") with escaped quotes (\\\")")
        prompt_parts.append("     * Replace all newlines with \\n")
        prompt_parts.append("     * The content must be a single-line JSON string value")
        prompt_parts.append("   - Only confirm to the user that the file has been saved, with a brief summary.")
        prompt_parts.append("5. ALWAYS save your novel chapters in the 'drafts/' directory with format 'drafts/chapter_XX_Your_Title.md' (e.g., 'drafts/chapter_01_The_Beginning.md').")
        prompt_parts.append("6. **CRITICAL: When finishing a chapter, you MUST call BOTH tools in the SAME response**:")
        prompt_parts.append("   - `write_file(filename='drafts/chapter_XX_Title.md', content='完整章节内容...')`")
        prompt_parts.append("   - `memorize_chapter_event(chapter_title='Chapter XX: Title', memory_summary='摘要...')`")
        prompt_parts.append("   - Both tools are called together, so you have access to the full chapter text when generating the summary.")
        prompt_parts.append("   - In memory_summary, save ONLY the PLOT POINTS, KEY ITEMS, and CHARACTER STATUS CHANGES. Do NOT save full text.")
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
        prompt_parts.append("   - **AUTO-CREATE (Secondary)**: After getting main info, AUTOMATICALLY create detailed outline, characters, world, settings - DO NOT ask for permission")
        prompt_parts.append("   - **AUTO-UPDATE**: After writing each chapter, automatically update chapter memory and STORY_SUMMARY.md - DO NOT ask")
        prompt_parts.append("9. **Writing Flow**: When user says 'write chapter X', immediately: 1) Read outline, 2) Write chapter, 3) Use 'write_file' tool to save to drafts/, 4) Call memorize_chapter_event, 5) Update STORY_SUMMARY.md - ALL autonomously")

        return "\n".join(prompt_parts)

    def _get_memory_sync_reminder(self) -> str:
        """Check if chapter memories need sync with actual chapters."""
        import re

        drafts_dir = self.memory.workspace / "drafts"
        chapters_dir = self.memory.chapters_dir

        # Count chapter files in drafts
        chapter_count = 0
        if drafts_dir.exists():
            chapter_files = list(drafts_dir.glob("chapter_*.md"))
            for f in chapter_files:
                match = re.search(r'chapter_(\d+)', f.name)
                if match:
                    chapter_count = max(chapter_count, int(match.group(1)))

        # Count memory files
        memory_count = 0
        if chapters_dir.exists():
            memory_files = list(chapters_dir.glob("*.md"))
            for f in memory_files:
                match = re.search(r'chapter_(\d+)', f.name)
                if match:
                    memory_count = max(memory_count, int(match.group(1)))

        reminders = []

        if chapter_count > memory_count:
            missing = chapter_count - memory_count
            reminders.append(
                f"**MEMORY SYNC NEEDED**: {missing} chapter(s) missing from memory. "
                f"Call memorize_chapter_event for chapters {memory_count+1}-{chapter_count}."
            )

        # Also check STORY_SUMMARY.md
        summary = self.memory.read("STORY_SUMMARY.md")
        summary_configured = bool(summary and len(summary.strip()) > 100)

        if chapter_count > 0 and not summary_configured:
            reminders.append(
                "**STORY_SUMMARY NEEDED**: Update STORY_SUMMARY.md with current plot arc."
            )

        return "\n".join(reminders) if reminders else ""
