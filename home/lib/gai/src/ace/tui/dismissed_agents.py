"""Persistence for dismissed agent identities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.agent import AgentType

_DISMISSED_AGENTS_FILE = Path.home() / ".gai" / "tui" / "dismissed_agents.json"


def load_dismissed_agents() -> set[tuple[AgentType, str, str | None]]:
    """Load dismissed agent identities from disk."""
    from .models.agent import AgentType

    if not _DISMISSED_AGENTS_FILE.exists():
        return set()

    try:
        with open(_DISMISSED_AGENTS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        agents: set[tuple[AgentType, str, str | None]] = set()
        for entry in data:
            agent_type = None
            for at in AgentType:
                if at.value == entry["agent_type"]:
                    agent_type = at
                    break

            if agent_type:
                agents.add((agent_type, entry["cl_name"], entry.get("raw_suffix")))
        return agents
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


def save_dismissed_agents(agents: set[tuple[AgentType, str, str | None]]) -> None:
    """Save dismissed agent identities to disk."""
    tui_dir = Path.home() / ".gai" / "tui"
    tui_dir.mkdir(parents=True, exist_ok=True)

    data = []
    for agent_type, cl_name, raw_suffix in agents:
        data.append(
            {
                "agent_type": agent_type.value,
                "cl_name": cl_name,
                "raw_suffix": raw_suffix,
            }
        )

    try:
        with open(_DISMISSED_AGENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # Silently fail
