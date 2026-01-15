from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .fm_discovery import find_fm_binary
from .fm_list_parser import list_sites
from .paths import agent_state_dir
from .pty_executor import execute_backup_via_fm_shell
from .security import verify_request


def create_app(*, fm_binary: Path | None, shared_secret: str | None) -> FastAPI:
    """
    Create FastAPI app with allowlisted actions only.
    """
    app = FastAPI(title="fb-agent", version=__version__)
    
    # Add CORS middleware to allow Dashboard to fetch agent time
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    
    if fm_binary is None:
        fm_binary = find_fm_binary()
    
    if fm_binary is None:
        raise RuntimeError("fm binary not found. Ensure 'fm' is in PATH.")
    
    app.state.fm_binary = fm_binary
    app.state.shared_secret = shared_secret or ""
    
    async def require_auth(request: Request, x_signature: str | None = None, x_timestamp: str | None = None) -> None:
        """
        Verify HMAC signature on all requests.
        """
        if not app.state.shared_secret:
            raise HTTPException(status_code=401, detail="not_registered")
        
        if not x_signature or not x_timestamp:
            raise HTTPException(status_code=401, detail="missing_signature")
        
        try:
            req_ts = int(x_timestamp)
        except ValueError:
            raise HTTPException(status_code=401, detail="invalid_timestamp")
        
        # Get body for signature verification
        # Dashboard signs JSON bodies with canonical formatting (sorted keys, no spaces)
        # For GET requests, body is empty {}
        body_bytes = b"{}"
        if request.method in {"POST", "PUT", "PATCH"}:
            raw_body = await request.body()
            if raw_body:
                try:
                    import json
                    body_obj = json.loads(raw_body)
                    # Normalize to match Dashboard format
                    body_bytes = json.dumps(body_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
                except Exception:
                    # If not JSON, use raw bytes
                    body_bytes = raw_body
            else:
                body_bytes = b"{}"
        # For GET requests, Dashboard signs with empty body {}
        # Path includes query params in signature (but we use path only for consistency)
        
        # Use path without query params for signature verification (Dashboard signs path only)
        path_for_sig = request.url.path
        
        if not verify_request(
            secret=app.state.shared_secret,
            method=request.method,
            path=path_for_sig,
            body=body_bytes,
            signature=x_signature,
            req_timestamp=req_ts,
        ):
            raise HTTPException(status_code=401, detail="invalid_signature")
    
    @app.get("/health")
    def health() -> dict[str, Any]:
        """Public health check."""
        return {"ok": True, "version": __version__}
    
    @app.get("/api/list_sites")
    async def api_list_sites(
        request: Request,
        x_signature: str | None = Header(None, alias="X-Signature"),
        x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    ) -> JSONResponse:
        """
        Allowlisted action: list sites via fm list.
        """
        await require_auth(request, x_signature, x_timestamp)
        
        try:
            sites = list_sites(app.state.fm_binary)
            return JSONResponse({"ok": True, "sites": sites})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    
    @app.post("/api/backup_site")
    async def api_backup_site(
        request: Request,
        x_signature: str | None = Header(None, alias="X-Signature"),
        x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    ) -> JSONResponse:
        """
        Allowlisted action: backup site via fm shell + bench.
        """
        await require_auth(request, x_signature, x_timestamp)
        
        try:
            payload = await request.json()
            site = str(payload.get("site") or "")
            stack = str(payload.get("stack") or "")
            
            if not site:
                return JSONResponse({"ok": False, "error": "site_required"}, status_code=400)
            
            # Validate site name (basic safety)
            if not all(c.isalnum() or c in "._-" for c in site):
                return JSONResponse({"ok": False, "error": "invalid_site"}, status_code=400)
            
            result = execute_backup_via_fm_shell(app.state.fm_binary, site)
            
            # Add stack/site context
            result["stack"] = stack
            result["site"] = site
            
            return JSONResponse(result, status_code=200 if result.get("ok") else 500)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({"ok": False, "error": str(e), "traceback": traceback.format_exc()}, status_code=500)
    
    @app.get("/api/backup_artifacts/{site}")
    async def api_backup_artifacts(
        site: str,
        request: Request,
        x_signature: str | None = Header(None, alias="X-Signature"),
        x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    ) -> JSONResponse:
        """
        Allowlisted action: list backup artifacts for a site.
        Used by dashboard to discover backup files after backup completes.
        """
        await require_auth(request, x_signature, x_timestamp)
        
        # TODO: Discover backup artifacts from bench backup output
        # For now, return empty list
        return JSONResponse({"ok": True, "artifacts": []})
    
    @app.get("/api/download_artifact")
    async def api_download_artifact(
        path: str,
        request: Request,
        x_signature: str | None = Header(None, alias="X-Signature"),
        x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    ):
        """
        Download a backup artifact file from agent.
        Path must be relative (e.g., ./site/private/backups/file.sql.gz)
        """
        from fastapi.responses import FileResponse
        import subprocess
        await require_auth(request, x_signature, x_timestamp)
        
        # Security: only allow paths starting with ./ (relative)
        if not path.startswith('./'):
            return JSONResponse({"ok": False, "error": "invalid_path"}, status_code=400)
        
        # Security: ensure path contains backup directory
        if 'private/backups' not in path:
            return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
        
        # Extract site name from path (e.g., ./dev.mby-solution.vip/private/backups/...)
        path_parts = path.lstrip('./').split('/')
        if len(path_parts) < 3:
            return JSONResponse({"ok": False, "error": "invalid_path"}, status_code=400)
        
        site_name = path_parts[0]
        
        # Get site's directory from fm list
        try:
            proc = subprocess.run(
                [str(app.state.fm_binary), "list"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            
            # Parse output to find site path
            # Note: fm list may truncate paths with '…', so we need to find the full path
            site_root = None
            truncated_path = None
            
            for line in proc.stdout.split('\n'):
                if site_name in line and '│' in line:
                    # Extract path from table: │ site │ status │ path │
                    parts = [p.strip() for p in line.split('│') if p.strip()]
                    if len(parts) >= 3 and parts[0] == site_name:
                        truncated_path = parts[2].rstrip('…').rstrip('.')
                        break
            
            # If path is truncated or doesn't exist, search for full path
            # Check if truncated_path exists and is valid
            if truncated_path:
                test_path = Path(truncated_path)
                if test_path.exists() and (test_path / "workspace" / "frappe-bench").exists():
                    site_root = test_path
                else:
                    # Path is truncated or invalid, search for full path
                    common_bases = [
                        Path("/home/baron/frappe/sites"),
                        Path("/opt/frappe/sites"),
                        Path("/srv/frappe/sites"),
                        Path.home() / "frappe" / "sites",
                    ]
                    
                    for base in common_bases:
                        if base.exists():
                            for site_dir in base.iterdir():
                                if site_dir.is_dir() and site_name in site_dir.name:
                                    # Check if this looks like the right site
                                    if (site_dir / "workspace" / "frappe-bench").exists():
                                        site_root = site_dir
                                        break
                            if site_root:
                                break
            else:
                # No path found in fm list, search anyway
                common_bases = [
                    Path("/home/baron/frappe/sites"),
                    Path("/opt/frappe/sites"),
                    Path("/srv/frappe/sites"),
                    Path.home() / "frappe" / "sites",
                ]
                
                for base in common_bases:
                    if base.exists():
                        for site_dir in base.iterdir():
                            if site_dir.is_dir() and site_name in site_dir.name:
                                if (site_dir / "workspace" / "frappe-bench").exists():
                                    site_root = site_dir
                                    break
                        if site_root:
                            break
            
            if not site_root or not site_root.exists():
                return JSONResponse({"ok": False, "error": "site_not_found", "tried": str(truncated_path)}, status_code=404)
            
            # Construct absolute path: site_root/workspace/frappe-bench/sites/ + relative path
            # Path from bench is relative to frappe-bench/sites directory
            bench_root = site_root / "workspace" / "frappe-bench" / "sites"
            file_path = bench_root / path.lstrip('./')
            
            if not file_path.exists() or not file_path.is_file():
                return JSONResponse({"ok": False, "error": "file_not_found", "tried": str(file_path)}, status_code=404)
            
            return FileResponse(path=str(file_path), filename=file_path.name)
            
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    
    @app.get("/api/time")
    async def api_time() -> JSONResponse:
        """Get current agent server time (no auth required)"""
        import time
        return JSONResponse({
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "timezone": time.strftime("%Z")
        })
    
    return app

