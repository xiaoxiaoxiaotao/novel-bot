```skill
---
name: story-design
description: Comprehensive story planning and design skill. Use when starting a new novel, when the user wants to plan the overall story structure, or when current settings feel insufficient and need expansion. Guides through scope definition, plot planning, world-building, character design, and writing style establishment.
---

# Story Design Skill

This skill guides comprehensive novel planning from concept to detailed blueprint. Use this when the user wants to start a new story, or when the current story design feels incomplete.

## When to Use

- Starting a brand new novel project
- User says the story feels "directionless" or "lacking depth"
- Need to establish or revise core story elements
- Current world-building or character development feels insufficient

## Phase 1: Scope & Requirements Gathering

**CRITICAL - MUST ASK USER**: Before any creative work, gather these requirements:

### 1.1 Word Count & Scope (REQUIRED - ASK USER)
Ask the user to specify:
- **Chapter length**: e.g., 2000-3000 words per chapter
- **Total chapters**: e.g., 500 chapters for a epic, 30 for a novella
- **Total estimated word count**: Calculate and confirm

### 1.2 Genre & Tone (REQUIRED - ASK USER)
- **Primary genre**: Fantasy, Sci-Fi, Romance, Mystery, Thriller, etc.
- **Overall tone**: Dark/gritty, lighthearted, epic, intimate, humorous

**AFTER getting scope info, AUTOMATICALLY create all planning documents without asking.**

## Phase 2: Core Story Architecture

### 2.1 Main Plot Design (The Spine)

Guide the user through defining:

**Central Conflict**
- What is the protagonist's ultimate goal?
- What/who stands in their way? (Antagonist force)
- What happens if they fail? (Stakes)

**Core Conspiracy/Mystery** (if applicable)
- What secret drives the plot?
- Who knows the truth?
- How is it gradually revealed?

**Three-Act Structure Overview**
```
Act 1 (Setup ~25%):
- Opening hook
- Inciting incident
- First plot point (point of no return)

Act 2 (Confrontation ~50%):
- Rising action with complications
- Midpoint twist/escalation
- Progressive complications leading to...

Act 3 (Resolution ~25%):
- Darkest moment
- Climax confrontation
- Resolution and aftermath
```

### 2.2 Subplot Design (The Ribs)

Plan these supporting storylines:

**Romance Arc** (if applicable)
- Love interest introduction timing
- Relationship development milestones
- How romance complicates or aids main plot

**Friendship/Ally Arcs**
- Key companions and their roles
- Betrayals and loyalties
- Character growth through relationships

**Mini-Boss / Arc Antagonists**
- Each major section needs its own antagonist
- How mini-bosses relate to the main villain
- What the protagonist learns from each defeat/victory

**Personal Growth Arc**
- Protagonist's internal flaw
- How external plot forces internal change
- Transformation by the end

Use the `write_file` tool to save plot outline to `OUTLINE.md`.

## Phase 3: World Building

Use the **GRAPES+** method:

### Geography
- Physical landscape and climate
- Important locations (cities, dungeons, wilderness)
- How geography affects plot

### Religion & Beliefs
- Gods, spirits, or cosmic forces
- Religious organizations and power
- How belief systems create conflict

### Achievements
- Technology or magic level
- Unique arts, crafts, or knowledge
- What makes this world special

### Politics
- Government structures
- Laws and enforcement
- Factions and their conflicts

### Economics
- Currency and trade
- Class systems and wealth distribution
- Resources worth fighting over

### Social Structure
- Family and clan systems
- Gender roles and customs
- Taboos and traditions

### + History (The Plus)
- Major historical events that shaped the present
- Ancient civilizations or lost knowledge
- How past events echo in current plot

Use the `write_file` tool to save world building to `WORLD.md`.

## Phase 4: Character Design

### 4.1 Protagonist

```markdown
# [Protagonist Name]
- **Role**: Primary Protagonist
- **Archetype**: [The Chosen One, The Reluctant Hero, etc.]
- **External Goal**: [What they want to achieve]
- **Internal Need**: [What they actually need to learn]
- **Core Flaw**: [What's holding them back]
- **Motivation**: [Why they can't give up]
- **Character Arc**: [How they change from start to end]
- **Voice**: [Speech patterns, vocabulary level, mannerisms]
```

### 4.2 Supporting Cast

For each major character, define:
- **Relationship to protagonist**: Ally, rival, mentor, love interest
- **Their own goal**: What do they want independently?
- **Secret or flaw**: What makes them interesting?
- **Role in plot**: How do they advance the story?

### 4.3 Antagonist(s)

- **Motivation**: Why do they oppose the protagonist? (Make it understandable)
- **Resources**: What power do they wield?
- **Weakness**: How can they be defeated?
- **Minions**: Who serves them and why?

Use the `write_file` tool to save character info to `CHARACTERS.md`.

## Phase 5: Writing Settings Guide

Create a comprehensive `SETTINGS.md` file that combines:
1. **Agent Persona** (formerly SOUL.md) - Who the agent is as a writer
2. **Writing Style** (formerly TONE.md) - How the prose should feel
3. **User Requirements** (formerly USER.md) - What the user specifically wants

### 5.1 Agent Persona Section

Define the agent's writing identity:

```markdown
## Agent Persona

**Role**: [e.g., Master Novelist, Genre Specialist, Literary Architect]
**Voice**: [e.g., Eloquent and perceptive, gritty and raw, warm and intimate]
**Approach**: [e.g., Balance artistic integrity with engaging storytelling]

### Literary Philosophy
- [Core principles that guide the writing]
- [e.g., Show don't tell, economy of words, emotional truth]

### Creative Priorities
- [What matters most in this story]
```

### 5.2 Writing Style Section

**Point of View**
- First person (I/me) - intimate, limited
- Third person limited (he/she, one character at a time)
- Third person omniscient (knows all)
- Multiple POV - which characters get chapters?

**Tense**
- Past tense (traditional)
- Present tense (immediate, cinematic)

**Prose Characteristics**

Guide the user to define:

**Description Level**
- Minimal (action-focused)
- Moderate (balanced)
- Lush (atmospheric, sensory-rich)

**Dialogue Style**
- Realistic/Naturalistic (um, ah, interruptions)
- Polished (clean, purposeful)
- Stylized (accents, dialects, formal/informal markers)

**Pacing Preference**
- Fast-paced (short chapters, quick scenes)
- Moderate (balanced scene/summary ratio)
- Slow-burn (detailed, contemplative)

**Language Register**
- Simple/Accessible (shorter words, clear sentences)
- Literary (complex structures, vocabulary)
- Genre-appropriate (technical terms for sci-fi, archaic for fantasy)

**Sentence Architecture**
- Varied rhythm, subordinate clauses, fragmentary power

### 5.3 User Requirements Section

Record specific user requests:

```markdown
## User Requirements

**Target Audience**: [Who is this story for?]
**Content Boundaries**: [What to avoid or emphasize]
**Special Requests**: [Any specific elements the user wants]
**Reference Works**: [Books/styles to emulate or avoid]
```

Use the `write_file` tool to save all settings to `SETTINGS.md`.

## Phase 6: Chapter-by-Chapter Blueprint

Create a high-level chapter list:

```markdown
# Chapter Blueprint

## Book 1: [Title]
- Ch 1: [One-sentence summary]
- Ch 2: [One-sentence summary]
...

## Book 2: [Title]
...
```

Include for each chapter:
- POV character
- Main plot point advanced
- Subplot developments
- Location
- Emotional tone

Use the `write_file` tool to save chapter blueprint to `OUTLINE.md`.

## File Management Rules

**CRITICAL: Use preset files only. DO NOT create duplicate or alternative files.**

The workspace already contains predefined files for story information. You MUST use these exact filenames:

| Content Type | Required Filename | Notes |
|-------------|-------------------|-------|
| World Building | `WORLD.md` | **ONLY** this file for world settings. Do NOT create `worldreview.md`, `worldview.md`, etc. |
| Characters | `CHARACTERS.md` | **ONLY** this file for character info. Do NOT create `characters.md` (lowercase), etc. |
| Story Summary | `STORY_SUMMARY.md` | **ONLY** this file for plot synopsis. |
| Writing Settings | `SETTINGS.md` | **ONLY** this file for style, tone, persona, and user requirements. |

### Workflow for File Updates

1. **Check First**: Use `read_file` to check if the preset file exists and read its current content
2. **Update, Don't Replace**: Append or update the existing preset file rather than creating a new one
3. **No Duplicates**: Never create files with similar names like `WORLD_review.md`, `world_new.md`, etc.

## Workflow

1. **Assess Current State**: Check existing files (SOUL.md, WORLD.md, CHARACTERS.md, OUTLINE.md)
2. **Ask Scope Questions**: Get word count per chapter and total chapters from user
3. **AUTO-CREATE Planning Docs**: WITHOUT asking permission:
   - Create OUTLINE.md with full chapter-by-chapter breakdown
   - Create CHARACTERS.md with protagonist, supporting cast, antagonist
   - Create WORLD.md with setting details
   - Create SETTINGS.md combining persona, style, and user requirements
4. **Summarize**: Present the complete plan to user for approval

## Success Criteria

Before finishing, ensure:
- [ ] Word count and scope defined
- [ ] Main plot has clear goal, opposition, and stakes
- [ ] At least 2-3 subplots identified
- [ ] World has unique, plot-relevant elements
- [ ] Protagonist has clear arc and flaw
- [ ] Antagonist has understandable motivation
- [ ] SETTINGS.md created with persona, style, and user requirements
- [ ] Chapter blueprint created
```
