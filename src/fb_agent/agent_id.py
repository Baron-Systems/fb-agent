from __future__ import annotations

import hashlib
import platform
import socket
from pathlib import Path

from .paths import agent_state_dir


def generate_stable_agent_id() -> str:
    """
    Generate a stable agent_id based on hostname + MAC address.
    Persisted in state dir so it remains stable across restarts.
    """
    state_file = agent_state_dir() / "agent_id.txt"
    
    if state_file.exists():
        agent_id = state_file.read_text(encoding="utf-8").strip()
        if agent_id:
            return agent_id
    
    # Generate from hostname + MAC
    hostname = socket.gethostname()
    try:
        mac = ":".join([f"{i:02x}" for i in socket.gethostbyname(socket.gethostname()).encode()[:6]])
    except Exception:
        mac = platform.node()
    
    seed = f"{hostname}:{mac}:{platform.system()}"
    agent_id = hashlib.sha256(seed.encode()).hexdigest()[:16]
    
    state_file.write_text(agent_id, encoding="utf-8")
    return agent_id

