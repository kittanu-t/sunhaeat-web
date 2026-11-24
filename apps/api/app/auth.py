"""HMAC check on every request: only the web server may call this API."""
import hashlib
import hmac
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

MAX_SKEW_S = 60
MAX_BODY_BYTES = 16_384


def sign(secret: str, ts: str, method: str, target: str, session: str, ip: str, body: bytes) -> str:
    """target is the percent-decoded path plus "?" and the raw query string, if any."""
    message = "\n".join([ts, method, target, session, ip, hashlib.sha256(body).hexdigest()])
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _is_exempt(path: str) -> bool:
    return path == "/healthz" or path.startswith("/internal/")  # /internal checks its own bearer secret


def install_auth(app: FastAPI) -> None:
    @app.middleware("http")
    async def require_signature(request: Request, call_next):
        declared = request.headers.get("content-length", "0")
        if not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "body_too_large"}, 413)
        if _is_exempt(request.url.path):
            return await call_next(request)
        secret = request.app.state.settings.api_hmac_secret
        if not secret:
            return JSONResponse({"detail": "not_configured"}, 503)
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "body_too_large"}, 413)
        h = request.headers
        ts, session, ip = h.get("x-she-timestamp", ""), h.get("x-she-session", ""), h.get("x-she-ip", "")
        query = request.scope["query_string"].decode("latin-1")
        target = request.scope["path"] + (f"?{query}" if query else "")
        expected = sign(secret, ts, request.method, target, session, ip, body)
        fresh = ts.isascii() and ts.isdigit() and abs(time.time() - int(ts)) <= MAX_SKEW_S
        # Compare bytes: compare_digest rejects non-ASCII strings with an exception.
        if not fresh or not hmac.compare_digest(expected.encode(), h.get("x-she-signature", "").encode()):
            return JSONResponse({"detail": "unauthorized"}, 401)
        request.state.session, request.state.ip = session, ip
        return await call_next(request)
