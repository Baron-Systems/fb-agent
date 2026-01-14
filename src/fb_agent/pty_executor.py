from __future__ import annotations

import os
import pty
import select
import subprocess
import time
from pathlib import Path
from typing import Any


def execute_backup_via_fm_shell(fm_binary: Path, site: str, timeout: int = 600) -> dict[str, Any]:
    """
    Execute backup via PTY:
    
    fm shell <site>
    bench --site <site> backup
    exit
    
    Captures output and detects success by markers.
    Returns structured result.
    """
    master_fd, slave_fd = pty.openpty()
    
    try:
        # Start fm shell in PTY
        proc = subprocess.Popen(
            [str(fm_binary), "shell", site],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
        )
        
        # Send commands via master
        
        commands = [
            f"bench --site {site} backup\n",
            "exit\n",
        ]
        
        output_lines: list[str] = []
        error_lines: list[str] = []
        
        # Write commands and read output
        for cmd in commands:
            os.write(master_fd, cmd.encode("utf-8"))
            time.sleep(0.1)  # Small delay between commands
        
        # Read output with timeout
        start_time = time.time()
        while proc.poll() is None:
            if time.time() - start_time > timeout:
                proc.kill()
                return {
                    "ok": False,
                    "error": "timeout",
                    "output": "\n".join(output_lines),
                    "stderr": "\n".join(error_lines),
                }
            
            if select.select([master_fd], [], [], 0.1)[0]:
                try:
                    data = os.read(master_fd, 4096).decode("utf-8", errors="replace")
                    if data:
                        output_lines.append(data)
                except OSError:
                    break
        
        # Wait for process to finish
        proc.wait(timeout=5)
        
        full_output = "\n".join(output_lines)
        
        # Detect success markers
        success_markers = [
            "backup completed",
            "backup successful",
            "backup created",
            "backup finished",
        ]
        
        error_markers = [
            "error",
            "failed",
            "exception",
            "traceback",
        ]
        
        output_lower = full_output.lower()
        has_success = any(marker in output_lower for marker in success_markers)
        has_error = any(marker in output_lower for marker in error_markers)
        
        ok = proc.returncode == 0 and has_success and not has_error
        
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "output": full_output,
            "stderr": "\n".join(error_lines),
        }
    
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "timeout",
            "output": "",
            "stderr": "",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "output": "",
            "stderr": "",
        }
    finally:
        try:
            os.close(master_fd)
            os.close(slave_fd)
        except Exception:
            pass

