from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def parse_fm_list_output(output: str) -> list[dict[str, Any]]:
    """
    Parse `fm list` output robustly.
    
    Expected format (example):
        Stack: production
        Sites:
          - site1.example.com
          - site2.example.com
        
        Stack: staging
        Sites:
          - site3.example.com
    
    Returns normalized JSON list:
    [
      {"stack": "production", "site": "site1.example.com"},
      {"stack": "production", "site": "site2.example.com"},
      {"stack": "staging", "site": "site3.example.com"},
    ]
    """
    result: list[dict[str, Any]] = []
    current_stack: str | None = None
    
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        
        # Match "Stack: <name>"
        stack_match = re.match(r"^Stack:\s*(.+)$", line, re.IGNORECASE)
        if stack_match:
            current_stack = stack_match.group(1).strip()
            continue
        
        # Match site list items: "- <site>" or "  - <site>"
        site_match = re.match(r"^[-•]\s*(.+)$", line)
        if site_match and current_stack:
            site = site_match.group(1).strip()
            if site:
                result.append({"stack": current_stack, "site": site})
    
    return result


def list_sites(fm_binary: Path) -> list[dict[str, Any]]:
    """
    Execute `fm list` and parse output.
    Raises on execution failure.
    """
    proc = subprocess.run(
        [str(fm_binary), "list"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return parse_fm_list_output(proc.stdout)

