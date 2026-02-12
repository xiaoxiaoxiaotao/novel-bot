# Novel Bot

[English Docs](README.md)

这是一个吸收了智能小说写作 Agent。它采用 "Filesystem as Memory"（文件即记忆）的设计理念，通过持续的 Agent Loop 与用户交互，能够维护长篇小说的连贯性。

## 核心特性

- **Agent 架构**：不再是线性的脚本，而是一个会思考、会自省的持续运行进程。
- **文件即数据库**：所有的记忆（Memory）、人设（Soul）、设定（World）都以 Markdown 文件直接存储在 `workspace/` 中，方便用户随时人工干预和修改。
- **双重记忆系统**：
    - **长期记忆 (Global Memory)**：记录世界观变迁、重要剧情节点 (`memory/MEMORY.md`)。
    - **短期记忆 (Chapter Memory)**：记录最近章节的详细摘要 (`memory/chapters/`)，防止上下文超长。
- **OpenAI 兼容性**：支持兼容 OpenAI 接口的模型。

## 部署安装

### 1. 环境准备

确保你的 Python 版本 >= 3.10。

```bash
git clone https://github.com/xiaoxiaoxiaotao/novel-bot.git
cd novel-bot
```

### 2. 安装依赖（推荐：uv）

**作者强烈推荐使用 [uv](https://github.com/astral-sh/uv) 进行依赖管理和运行。**

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步依赖（自动创建虚拟环境）
uv sync
```

**备选：pip**

```bash
python -m pip install -r requirements.txt
```

### 3. 配置模型

在项目根目录创建 `.env` 文件，填入你的 API Key 和 Base URL（可以参考.env.example文件）。

作者使用的是[Try NVIDIA NIM APIs](https://build.nvidia.com/)上的api，采用的moonshotai/kimi-k2.5模型。

```env
NVIDIA_API_KEY=your_nvidia_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
MODEL_NAME=moonshotai/kimi-k2.5
```

## 使用方法

### 1. 初始化工作区

首次运行时，需要初始化工作区。这将创建 `workspace` 目录和必要的设定文件（SOUL.md, WORLD.md 等）。

```bash
# 使用 uv（推荐）
uv run python -m novel_bot init

# 或使用 pip
python -m novel_bot init
```

*提示：你可以直接编辑 `workspace/` 下的 Markdown 文件来修改 AI 的人设或小说的大纲。*

### 2. 启动 Agent

启动交互式写作界面：

```bash
# 使用 uv（推荐）
uv run python -m novel_bot start

# 或使用 pip
python -m novel_bot start
```

### 3. 交互示例

在终端中作为 "Editor" (编辑) 指挥 Agent 写作：

```text
Editor > 我想撰写一个末日丧尸视角下的故事，人类可以觉醒异能，请你为小说撰写一些人物、风格、情节的设定，生成世界观和大纲。

Thinking...
Agent: [生成了...]

Editor > 很好，现在开始写第一章的正文，注意描写环境的阴冷。

Thinking...
Agent: [生成正文并保存到文件]
```

## 目录结构

```text
novel_bot/          # 核心代码
  agent/            # Agent 逻辑 (Loop, Memory, Tools)
  cli/              # 命令行入口
  config/           # 配置加载
workspace/          # [自动生成] 小说的数据存储位置 (Git 忽略)
  drafts/           # 小说正文草稿 (e.g. drafts/chapter_01.md)
  SOUL.md           # AI 的人设/写作风格
  WORLD.md          # 世界观设定
  CHARACTERS.md     # 角色卡
  STORY_SUMMARY.md  # 全书剧情梗概
  memory/           # 自动管理的记忆系统
```

## 致谢

- 本项目的部分代码参考和借鉴了 [nanobot](https://github.com/HKUDS/nanobot.git) 项目。

