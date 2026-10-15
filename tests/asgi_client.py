import asyncio
import json as jsonlib
from urllib.parse import urlsplit


class Response:
    def __init__(self, status_code: int, headers: dict[str, str], content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    def json(self):
        return jsonlib.loads(self.content)


class MiniClient:
    def __init__(self, app, headers: dict[str, str] | None = None):
        self.app = app
        self.headers = headers or {}

    async def arequest(self, method, path, *, headers=None, json=None, content=None) -> Response:
        parts = urlsplit(path)
        body = content if content is not None else b""
        merged = {**self.headers, **(headers or {})}
        if json is not None:
            body = jsonlib.dumps(json).encode()
            merged.setdefault("content-type", "application/json")
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": parts.path,
            "raw_path": parts.path.encode(),
            "query_string": parts.query.encode(),
            "root_path": "",
            "headers": [(k.lower().encode(), v.encode()) for k, v in merged.items()],
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8765),
        }
        sent = False
        status, resp_headers, chunks = 500, {}, []

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.sleep(3600)

        async def send(message):
            nonlocal status, resp_headers
            if message["type"] == "http.response.start":
                status = message["status"]
                resp_headers = {k.decode().lower(): v.decode() for k, v in message["headers"]}
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        await self.app(scope, receive, send)
        return Response(status, resp_headers, b"".join(chunks))

    def request(self, method, path, **kwargs) -> Response:
        return asyncio.run(self.arequest(method, path, **kwargs))

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def patch(self, path, **kw):
        return self.request("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)


def multipart(files: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = "----nmwfmtestboundary"
    out = b""
    for field, filename, data in files:
        out += (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + data
            + b"\r\n"
        )
    out += f"--{boundary}--\r\n".encode()
    return out, f"multipart/form-data; boundary={boundary}"
