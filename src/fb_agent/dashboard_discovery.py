from __future__ import annotations

import json
import socket
import time
from typing import Any


DISCOVERY_PORT = 7355


def discover_dashboard(agent_id: str, agent_port: int, timeout: float = 5.0) -> dict[str, Any] | None:
    """
    Broadcast UDP discovery packet and wait for dashboard reply.
    Returns dashboard info dict or None if not found.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    
    try:
        # Broadcast discovery packet matching dashboard protocol
        packet = json.dumps({
            "type": "fb-agent.hello",
            "agent_id": agent_id,
            "port": agent_port,
        }).encode()
        sock.sendto(packet, ("255.255.255.255", DISCOVERY_PORT))
        
        # Wait for reply
        data, addr = sock.recvfrom(4096)
        reply = json.loads(data.decode())
        
        if reply.get("type") == "fb.dashboard.offer":
            return {
                "base_url": reply.get("dashboard_url", ""),
                "token": reply.get("token", ""),
            }
    except (socket.timeout, json.JSONDecodeError, KeyError):
        return None
    finally:
        sock.close()
    
    return None

