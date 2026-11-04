import hmac
import json
import os

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def _hostname(host_header: str) -> str:
    if host_header.startswith("["):
        return host_header.split("]")[0] + "]"
    return host_header.split(":")[0]


def _rejection(status: int, code: str) -> tuple[int, bytes]:
    body = {"success": False, "data": None, "error": {"code": code, "message": "접근이 거부되었습니다"}}
    return status, json.dumps(body, ensure_ascii=False).encode()


class LocalAccessMiddleware:
    """실행마다 Electron이 정한 토큰을 가진 요청만 받는다. 토큰이 없으면 전부 거부한다"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rejection = self._check(dict(scope["headers"]))
        if rejection is None:
            await self.app(scope, receive, send)
            return
        status, body = rejection
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})

    def _check(self, headers: dict[bytes, bytes]) -> tuple[int, bytes] | None:
        # A forged Host is how DNS rebinding reaches a loopback server from a web page
        if _hostname(headers.get(b"host", b"").decode("latin-1")) not in _LOOPBACK_HOSTS:
            return _rejection(403, "HOST_NOT_ALLOWED")
        expected = os.environ.get("CLASP_API_TOKEN", "")
        provided = headers.get(b"x-clasp-token", b"").decode("latin-1")
        if not expected or not hmac.compare_digest(expected, provided):
            return _rejection(401, "UNAUTHORIZED")
        return None
