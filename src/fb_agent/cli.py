from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import uvicorn
from uvicorn import Config, Server

from .agent_id import generate_stable_agent_id
from .app import create_app
from .dashboard_discovery import discover_dashboard
from .fm_discovery import find_fm_binary
from .fm_list_parser import list_sites
from .paths import agent_db_path, agent_state_dir
from .security import sign_request


def main() -> None:
    """CLI entrypoint for pipx installation."""
    run()


def run() -> None:
    """
    Zero-config agent startup:
    - Discover fm binary
    - Generate stable agent_id
    - Discover dashboard via UDP
    - Register with dashboard
    - Start FastAPI server
    """
    fm_binary = find_fm_binary()
    if fm_binary is None:
        print("ERROR: fm binary not found. Ensure 'fm' is in PATH.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found fm: {fm_binary}")
    
    # Generate stable agent_id
    agent_id = generate_stable_agent_id()
    print(f"Agent ID: {agent_id}")
    
    # Discover dashboard
    print("Discovering dashboard...")
    dashboard_info = discover_dashboard(agent_id=agent_id, agent_port=8888, timeout=10.0)
    
    shared_secret: str | None = None
    
    if dashboard_info:
        print(f"Found dashboard: {dashboard_info['base_url']}")
        
        # Register with dashboard
        try:
            meta = {
                "hostname": __import__("socket").gethostname(),
                "fm_version": "unknown",  # Could parse from fm --version if needed
            }
            
            # Get sites for meta (group by stack)
            try:
                sites = list_sites(fm_binary)
                # Group sites by stack
                stacks_dict: dict[str, list[str]] = {}
                for site_info in sites:
                    stack = str(site_info.get("stack") or "default")
                    site = str(site_info.get("site") or "")
                    if site:
                        if stack not in stacks_dict:
                            stacks_dict[stack] = []
                        stacks_dict[stack].append(site)
                
                # Convert to expected format
                meta["stacks"] = [
                    {"stack": stack, "sites": sites_list}
                    for stack, sites_list in stacks_dict.items()
                ]
            except Exception:
                pass
            
            resp = httpx.post(
                f"{dashboard_info['base_url']}/api/agents/register",
                json={
                    "token": dashboard_info["token"],
                    "agent_id": agent_id,
                    "port": 8888,  # Default agent port
                    "meta": meta,
                },
                timeout=10.0,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                shared_secret = data.get("shared_secret")
                print("Registered with dashboard successfully")
            else:
                print(f"WARNING: Registration failed: {resp.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: Could not register with dashboard: {e}", file=sys.stderr)
    else:
        print("WARNING: Dashboard not found. Running in standalone mode.", file=sys.stderr)
    
    # Load persisted secret if available
    secret_file = agent_state_dir() / "shared_secret.txt"
    if shared_secret:
        secret_file.write_text(shared_secret, encoding="utf-8")
    elif secret_file.exists():
        shared_secret = secret_file.read_text(encoding="utf-8").strip()
    
    # Create and run app
    app = create_app(fm_binary=fm_binary, shared_secret=shared_secret)
    
    print("Starting agent API on http://0.0.0.0:8888")
    
    config = Config(app, host="0.0.0.0", port=8888, log_level="info")
    server = Server(config)
    server.run()

