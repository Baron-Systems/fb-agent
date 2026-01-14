from __future__ import annotations

import shutil
from pathlib import Path


def find_fm_binary() -> Path | None:
    """
    Discover fm binary via PATH.
    Returns None if not found.
    """
    fm_path = shutil.which("fm")
    if fm_path:
        return Path(fm_path)
    return None

