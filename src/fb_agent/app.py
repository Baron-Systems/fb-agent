from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

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
        body = b""
        if request.method in {"POST", "PUT", "PATCH"}:
            body_bytes = await request.body()
            body = body_bytes
        
        if not verify_request(
            secret=app.state.shared_secret,
            method=request.method,
            path=request.url.path,
            body=body,
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
        require_auth(request, x_signature, x_timestamp)
        
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
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    
    @app.get("/api/backup_artifacts/{site}")
    def api_backup_artifacts(
        site: str,
        request: Request,
        x_signature: str | None = Header(None, alias="X-Signature"),
        x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    ) -> JSONResponse:
        """
        Allowlisted action: list backup artifacts for a site.
        Used by dashboard to discover backup files after backup completes.
        """
        require_auth(request, x_signature, x_timestamp)
        
        # TODO: Discover backup artifacts from bench backup output
        # For now, return empty list
        return JSONResponse({"ok": True, "artifacts": []})
    
    return app

