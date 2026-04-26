"""Jinja-based prompt registry.

- StrictUndefined so missing variables fail loud
- SHA-256 of rendered template registered into prompt_versions table
- Few-shot examples loaded from sibling YAML files
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default location: <repo>/prompts/, sibling to src/
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "prompts"


class PromptRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or DEFAULT_ROOT).resolve()
        if not self.root.exists():
            raise RuntimeError(f"Prompt root does not exist: {self.root}")
        self.env = Environment(
            loader=FileSystemLoader(str(self.root)),
            undefined=StrictUndefined,
            autoescape=select_autoescape(disabled_extensions=("j2", "jinja", "txt")),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )
        self.env.globals["load_examples"] = self._load_examples

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, template: str, /, **vars: Any) -> str:
        """Render a Jinja template by relative path (e.g. 'classification/ticket_classify_v1.j2')."""
        tpl = self.env.get_template(template)
        return tpl.render(**vars)

    def hash(self, template: str) -> str:
        """SHA-256 of the raw template source — stable across renders, used for prompt_version_id."""
        path = self.root / template
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def read_meta(self, template_dir: str) -> dict[str, Any]:
        meta_path = self.root / template_dir / "prompt.meta.yaml"
        if not meta_path.exists():
            return {}
        return yaml.safe_load(meta_path.read_text()) or {}

    # ------------------------------------------------------------------
    # Jinja globals
    # ------------------------------------------------------------------

    def _load_examples(self, dir_: str, file: str = "few_shot.yaml") -> list[dict[str, Any]]:
        path = self.root / dir_ / "examples" / file
        if not path.exists():
            logger.warning("examples_file_missing", path=str(path))
            return []
        data = yaml.safe_load(path.read_text()) or {}
        return list(data.get("examples", []))


@lru_cache(maxsize=1)
def get_registry() -> PromptRegistry:
    return PromptRegistry()
