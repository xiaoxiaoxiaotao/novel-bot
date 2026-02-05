# Novel Bot

An intelligent novel writing agent powered by LLMs. It adopts the "Filesystem as Memory" design philosophy, interacting with the user through a continuous Agent Loop to maintain the coherence of long-form novels.

[中文文档](README_zh-CN.md)

## Key Features

- **Agent Architecture**: Not just a linear script, but a continuous process capable of thinking and self-reflection.
- **Filesystem as Database**: All Memory, Persona (Soul), and Settings (World) are stored directly as Markdown files in `workspace/`, making it easy for users to manually intervene and modify at any time.
- **Dual Memory System**:
    - **Global Memory**: Records worldview changes and important plot nodes (`memory/MEMORY.md`).
    - **Chapter Memory**: Records detailed summaries of recent chapters (`memory/chapters/`) to prevent context overflow.
- **OpenAI Compatibility**: Supports models compatible with the OpenAI API.

## Installation

### 1. Prerequisites

Ensure your Python version is >= 3.10.

```bash
git clone https://github.com/xiaoxiaoxiaotao/novel-bot.git
cd novel-bot
git checkout develop
```

### 2. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure Model

Create a `.env` file in the project root directory and fill in your API Key and Base URL (you can refer to the `.env.example` file).

The author uses the API from [Try NVIDIA NIM APIs](https://build.nvidia.com/), employing the `moonshotai/kimi-k2.5` model.

```env
NVIDIA_API_KEY=your_nvidia_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
MODEL_NAME=moonshotai/kimi-k2.5
```

## Usage

### 1. Initialize Workspace

When running for the first time, you need to initialize the workspace. This will create the `workspace` directory and necessary setting files (SOUL.md, WORLD.md, etc.).

```bash
python -m novel_bot init
```

*Tip: You can directly edit the Markdown files under `workspace/` to modify the AI's persona or the novel's outline.*

### 2. Start Agent

Launch the interactive writing interface:

```bash
python -m novel_bot start
```

### 3. Interaction Example

Command the Agent to write as an "Editor" in the terminal:

```text
Editor > I want to write a story from a zombie apocalypse perspective where humans can awaken superpowers. Please write some settings for characters, style, and plot, and generate a worldview and outline.

Thinking...
Agent: [Generated content...]

Editor > Great. Now start writing the first chapter. Focus on describing the cold and gloomy environment.

Thinking...
Agent: [Generated text saved to file]
```

## Directory Structure

```text
novel_bot/          # Core Code
  agent/            # Agent Logic (Loop, Memory, Tools)
  cli/              # CLI Entry Point
  config/           # Configuration Loading
workspace/          # [Auto-Generated] Novel Data Storage (Git Ignored)
  drafts/           # Novel Drafts (e.g. drafts/chapter_01.md)
  SOUL.md           # AI Persona / Writing Style
  WORLD.md          # Worldview Settings
  CHARACTERS.md     # Character Cards
  STORY_SUMMARY.md  # Full Story Plot Summary
  memory/           # Automatically Managed Memory System
```

## Acknowledgements

- Portions of this project were inspired by and adapt code from [nanobot](https://github.com/HKUDS/nanobot.git).

