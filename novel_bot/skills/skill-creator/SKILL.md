````skill
---
name: skill-creator
description: Create or update AgentSkills. Use when designing, structuring, or packaging skills with scripts, references, and assets.
---

# Skill Creator

This skill provides guidance for creating effective skills.

## about Skills

Skills are modular, self-contained packages that extend the agent's capabilities by providing
specialized knowledge, workflows, and tools. Think of them as "onboarding guides" for specific
domains or tasks—they transform the agent from a general-purpose agent into a specialized agent
equipped with procedural knowledge that no model can fully possess.

### Anatomy of a Skill

Every skill consists of a required SKILL.md file and optional bundled resources.
In `novel_bot`, skills are folders in `novel_bot/skills/` or `workspace/skills/`.

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be read by the agent
    └── assets/           - Files used in output
```

## Creating a new skill

1. Create a directory in `workspace/skills/` or `novel_bot/skills/` with the skill name.
2. Create `SKILL.md` inside that directory.
3. Add YAML frontmatter:
   ```yaml
   ---
   name: my-skill
   description: A short description of what this skill does and when to use it.
   ---
   ```
4. Add instructions in Markdown.
   - Triggers: When should this skill be used?
   - Instructions: How to perform the task.
   - Tools: Which tools to use.

## Example

If you want to create a `weather` skill:

1. `mkdir -p skills/weather`
2. Create `skills/weather/SKILL.md`:

```markdown
---
name: weather
description: Check weather forecasts and conditions.
---

# Weather Skill

Use this skill when the user asks about the weather.

## Instructions
1. Use `curl htps://wttr.in/Location` (using run_in_terminal) to get weather.
```

## Best Practices

- **Concise**: Only include what the assigned agent needs to know.
- **Progressive**: If the skill is complex, put details in `references/topic.md` and tell the agent to read it only if needed.
````