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
    
    ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    for line in output.splitlines():
        # Remove ANSI color/control sequences before parsing.
        line_clean = ansi_escape.sub("", line)
        line_stripped = line_clean.strip()
        if not line_stripped:
            continue

        # Skip common table border lines (unicode/ascii).
        if (
            any(char in line_stripped for char in ["┏", "┃", "┗", "┓", "┛", "┣", "┫", "╋", "━", "┳", "┻", "╇", "┡", "└"])
            or re.fullmatch(r"[-+|= ]+", line_stripped)
        ):
            in_table = True
            continue

        # Parse table rows in either unicode "│" or ascii "|" format.
        # Examples:
        #   │ al.com │ Active │ /path │
        #   | al.com | Active | /path |
        for sep in ("│", "|"):
            if sep in line_stripped and line_stripped.startswith(sep):
                parts = [p.strip() for p in line_stripped.split(sep) if p.strip()]
                if parts:
                    site = parts[0].strip()
                    # Skip headers/separators
                    if site and site.lower() not in {"site", "sites"} and "━" not in site and "─" not in site:
                        result.append({"stack": "default", "site": site})
                        in_table = True
                        break
        else:
            # Not a table row; continue with old-format parsing below.
            pass
        if in_table and result:
            # Row already parsed as table format.
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

