from __future__ import annotations

import os
from pathlib import Path


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def agent_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME") or os.environ.get("XDG_DATA_HOME")
    if xdg:
        return _ensure_dir(Path(xdg) / "fb-agent")
    return _ensure_dir(Path.home() / ".local" / "share" / "fb-agent")


def agent_db_path() -> Path:
    return agent_state_dir() / "agent.sqlite3"


