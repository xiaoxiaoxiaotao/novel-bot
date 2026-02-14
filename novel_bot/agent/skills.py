"""Skills loader for agent capabilities."""

import os
import re
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
import yaml
from loguru import logger

# Built-in skills directory (relative to this file)
SKILLS_DIR = Path(__file__).parent.parent / "skills"

class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.

    Skills are loaded from: novel_bot/skills/ (package directory)
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.skills_dir = SKILLS_DIR
    
    def list_skills(self, filter_unavailable: bool = True) -> List[Dict[str, str]]:
        """
        List all available skills.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts.
        """
        skills = []
        loaded_names = set()

        # Load from built-in skills directory
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        name = skill_dir.name
                        # Try to get name from frontmatter if possible
                        meta = self._get_metadata_from_file(skill_file)
                        if meta and meta.get("name"):
                            name = meta["name"]

                        if name not in loaded_names:
                            skills.append({"name": name, "path": str(skill_file), "source": "builtin"})
                            loaded_names.add(name)
        else:
            logger.warning(f"Skills directory not found: {self.skills_dir}")

        # Filter by requirements
        if filter_unavailable:
            available = [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
            return available
        return skills

    def load_skill(self, name: str) -> Optional[str]:
        """
        Load a skill by name.
        """
        # Search in built-in skills directory
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        # Check dir name first
                        if skill_dir.name == name:
                            logger.info(f"Loading skill: {name}")
                            content = skill_file.read_bytes()
                            return content.decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")

                        # Check frontmatter name
                        meta = self._get_metadata_from_file(skill_file)
                        if meta and meta.get("name") == name:
                            logger.info(f"Loading skill: {name}")
                            content = skill_file.read_bytes()
                            return content.decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")
        logger.warning(f"Skill not found: {name}")
        return None

    def load_skills_for_context(self, skill_names: List[str]) -> str:
        """
        Load specific skills for inclusion in agent context.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        
        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""
        
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(self._get_skill_description(s["name"]))
            skill_meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)
            
            lines.append(f"  <skill available=\"{str(available).lower()}\">")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")
            
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")
            
            lines.append(f"  </skill>")
        lines.append("</skills>")
        
        return "\n".join(lines)

    def get_always_skills(self) -> List[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
            # Check 'always' in both top-level and nanobot metadata
            if str(skill_meta.get("always")).lower() == "true" or str(meta.get("always")).lower() == "true":
                result.append(s["name"])
        return result

    def get_skill_metadata(self, name: str) -> Optional[Dict]:
        """Get metadata from a skill's frontmatter."""
        content = self.load_skill(name)
        if not content:
            return None
        return self._get_metadata_from_content(content)

    def _get_metadata_from_file(self, file_path: Path) -> Optional[Dict]:
        try:
            content = file_path.read_bytes().decode("utf-8", errors="surrogatepass").encode("utf-8", errors="ignore").decode("utf-8")
            return self._get_metadata_from_content(content)
        except Exception:
            return None

    def _get_metadata_from_content(self, content: str) -> Optional[Dict]:
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                try:
                    return yaml.safe_load(match.group(1))
                except yaml.YAMLError:
                    return None
        return None

    def _get_skill_description(self, name: str) -> str:
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name

    def _strip_frontmatter(self, content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def _parse_nanobot_metadata(self, raw: Any) -> Dict:
        if isinstance(raw, dict): return raw
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
                return data.get("nanobot", {}) if isinstance(data, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def _check_requirements(self, skill_meta: Dict) -> bool:
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True

    def _get_skill_meta(self, name: str) -> Dict:
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))
    
    def _get_missing_requirements(self, skill_meta: Dict) -> str:
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)
