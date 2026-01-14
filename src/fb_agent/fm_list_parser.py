from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def parse_fm_list_output(output: str) -> list[dict[str, Any]]:
    """
    Parse `fm list` output robustly.
    
    Supports both formats:
    1. Table format (new):
        ┃ Site                 ┃ Status   ┃ Path    ┃
        │ dev.mby-solution.vip │ Inactive │ /path   │
    
    2. List format (old):
        Stack: production
        Sites:
          - site1.example.com
    
    Returns normalized JSON list:
    [
      {"stack": "default", "site": "dev.mby-solution.vip"},
    ]
    """
    result: list[dict[str, Any]] = []
    current_stack: str | None = None
    in_table = False
    
    for line in output.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # Check if this is a table row with site (starts with │)
        if line_stripped.startswith("│"):
            # Parse table row: │ site │ status │ path │
            parts = [p.strip() for p in line_stripped.split("│") if p.strip()]
            if parts and len(parts) >= 1:
                site = parts[0].strip()
                # Skip header rows that contain "Site" or "━"
                if site and site.lower() != "site" and "━" not in site and "─" not in site:
                    result.append({"stack": "default", "site": site})
                    in_table = True
            continue
        
        # Check for table borders (skip them)
        if any(char in line_stripped for char in ["┏", "┃", "┗", "┓", "┛", "┣", "┫", "╋", "━", "┳", "┻", "╇", "┡", "└"]):
            in_table = True
            continue
        
        # Match "Stack: <name>" (old format)
        stack_match = re.match(r"^Stack:\s*(.+)$", line_stripped, re.IGNORECASE)
        if stack_match:
            current_stack = stack_match.group(1).strip()
            continue
        
        # Match site list items: "- <site>" or "  - <site>" (old format)
        site_match = re.match(r"^[-•]\s*(.+)$", line_stripped)
        if site_match:
            site = site_match.group(1).strip()
            if site:
                stack = current_stack or "default"
                result.append({"stack": stack, "site": site})
    
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

