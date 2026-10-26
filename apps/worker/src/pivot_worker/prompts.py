"""Load the versioned prompts in `apps/worker/prompts/*.md` (architecture §6.4).

Prompts are Markdown files with `{{name}}` placeholders. The hash of the rendered text goes
into `AgentTrace.prompt_hash`, so every trace says exactly which prompt produced it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    text: str

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:12]


@cache
def _template(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text()


def render(name: str, **values: str) -> Prompt:
    """Fill every placeholder; a missing or unused value is a bug, so both raise."""
    template = _template(name)
    wanted = set(_PLACEHOLDER.findall(template))
    if missing := wanted - values.keys():
        raise KeyError(f"prompt {name} needs {sorted(missing)}")
    if extra := values.keys() - wanted:
        raise KeyError(f"prompt {name} has no placeholder for {sorted(extra)}")
    return Prompt(name, _PLACEHOLDER.sub(lambda m: values[m.group(1)], template))
