import asyncio as aio
import json


class Request:
    def __init__(self):
        self.method: str = None
        self.path: str = None
        self.version: str = None
        self.headers: dict[str, str] = {}
        self.body: bytes = None
        self.json: dict = None
        self.form: dict[str, str] = {}
        self.query: dict[str, str] = {}
        self.cookie: str = None
        self.source: tuple[str, int] = None
        self.user_agent: str = None

    def __repr__(self):
        return f"<Request {self.method} {self.path}>"

    @classmethod
    def parse_query_string(cls, query: str) -> dict:
        return dict(qc.split("=") for qc in query.split("&"))

    @classmethod
    async def from_stream(cls, reader: aio.StreamReader) -> "Request":
        # Create a new instance of this class
        self = cls()

        # Read the first line of HTTP request
        request_line = await reader.readline()
        self.method, self.path, self.version = request_line.decode("utf-8").split()

        # Read the headers
        while True:
            header = await reader.readline()
            if header == b"\r\n":
                break

            if header.startswith(b"Cookie: "):
                self.cookie = self.parse_query_string(header.decode("utf-8").split(": ")[1].strip())
                continue

            if header.startswith(b"User-Agent: "):
                self.user_agent = header.decode("utf-8").split(": ")[1].strip()
                continue

            key, value = header.decode("utf-8").split(": ")
            self.headers[key] = value.strip()

        # Read the full body
        if "Content-Length" in self.headers:
            self.body = await reader.read(int(self.headers["Content-Length"]))
        else:
            self.body = b""

        if self.headers.get("Content-Type") == "application/json":
            self.json = json.loads(self.body.decode("utf-8"))
        elif self.headers.get("Content-Type") == "application/x-www-form-urlencoded":
            self.form = self.parse_query_string(self.body.decode("utf-8"))

        # Parse the query string
        if "?" in self.path:
            self.path, qs = self.path.split("?")
            self.query = self.parse_query_string(qs)

        return self
