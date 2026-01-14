from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def unb64url(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sign_request(secret: str, method: str, path: str, body: dict | None = None, timestamp: int | None = None) -> dict[str, str]:
    """
    Generate HMAC signature for agent->dashboard requests.
    Matches dashboard signing format.
    Returns headers dict with X-Signature and X-Timestamp.
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    # Match dashboard format: ts + method + path + body_json
    body_bytes = json.dumps(body or {}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    message = b"\n".join([
        str(timestamp).encode("ascii"),
        method.upper().encode("ascii"),
        path.encode("utf-8"),
        body_bytes,
    ])
    
    # Dashboard uses base64url-encoded secrets, decode first
    secret_bytes = unb64url(secret)
    mac = hmac.new(secret_bytes, message, sha256).digest()
    signature = b64url(mac)
    
    return {
        "X-Signature": signature,
        "X-Timestamp": str(timestamp),
    }


def verify_request(secret: str, method: str, path: str, body: bytes, signature: str, req_timestamp: int, max_age: int = 300) -> bool:
    """
    Verify HMAC signature from dashboard->agent requests.
    Matches dashboard signing format: ts + method + path + body
    """
    now = int(time.time())
    if abs(now - req_timestamp) > max_age:
        return False
    
    # Match dashboard signing format
    message = b"\n".join([
        str(req_timestamp).encode("ascii"),
        method.upper().encode("ascii"),
        path.encode("utf-8"),
        body,
    ])
    
    # Dashboard uses base64url-encoded secrets, decode first
    secret_bytes = unb64url(secret)
    expected_bytes = hmac.new(secret_bytes, message, sha256).digest()
    expected = b64url(expected_bytes)
    
    return hmac.compare_digest(expected, signature)

