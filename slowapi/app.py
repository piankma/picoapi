import asyncio as aio
import json
import time
import os

from slowapi.request import Request
from slowapi.response import Response, send_file


class SlowAPI:
    def __init__(self, debug: bool = False):
        self.debug: bool = debug
        self.routes: dict[tuple[str, str], callable] = {}
        self.static_routes: dict[str, str] = {}

    def route(self, path: str, methods: set[str] = None):
        def wrapper(handler):
            methods_set = methods or {"GET"}

            # all endpoints should support OPTIONS and HEAD
            methods_set.add("OPTIONS")
            methods_set.add("HEAD")

            # Register the handler for each method
            for method in methods_set:
                if method not in (
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "OPTIONS",
                    "HEAD",
                ):
                    raise ValueError(f"Invalid method {method} for route {path}")

                if self.debug:
                    print(f"Registering route {method} {path} -> {handler.__name__}()")
                self.routes[(method, path)] = handler

            return handler

        return wrapper

    def serve_static(
        self,
        request: Request,
        prefix: str,
        directory: str,
    ):
        return send_file(
            os.path.join(directory, request.path[len(prefix):]),
        )


    def add_static_route(self, prefix: str, directory: str):
        if not prefix.endswith("/"):
            prefix += "/"
        self.static_routes[prefix] = directory

        print(f"Registering static route {prefix} -> {directory}")

    async def handle_request(self, reader, writer):
        if self.debug:
            loop_start = aio.get_event_loop().time()
            real_start = time.time()

        # Read the request
        request = await Request.from_stream(reader)
        request.source_ip, request.source_port = writer.get_extra_info("peername")

        for prefix, directory in self.static_routes.items():
            if request.path.startswith(prefix):
                resp = self.serve_static(request, prefix, directory)
                await resp.send(writer)

        # Find the handler for this request
        handler = self.routes.get((request.method, request.path))
        if not handler:
            resp = Response("Not found", 404)
        else:
            # Create a response object
            resp = await handler(request)
            if isinstance(resp, tuple):
                resp = Response(*resp)
            elif isinstance(resp, str):
                resp = Response(resp, headers={"Content-Type": "text/plain"})
            elif isinstance(resp, (dict, list)):
                resp = Response(
                    json.dumps(resp), headers={"Content-Type": "application/json"}
                )
            else:
                raise ValueError(f"Invalid response type {type(resp)}")

        await resp.send(writer)

        log_string = (
            f"{request.source_ip}:{request.source_port}: "
            f"{request.method} {request.path} {resp.status}"
        )
        if self.debug:
            loop_end = aio.get_event_loop().time() - loop_start
            real_end = time.time() - real_start
            log_string += f" (loop {loop_end:.4f}s /" f" real {real_end:.4f}s)"
            resp.headers[
                "Server-Timing"
            ] = f"slowapi;dur={real_end:.4f}, loop;dur={loop_end:.4f}"

        print(log_string)

    def run(self, host: str = "127.0.0.1", port: int = 8000):
        print(f"Starting server on {host}:{port}...")

        # Create a new asyncio event loop
        loop = aio.get_event_loop()
        loop.create_task(aio.start_server(self.handle_request, host, port))
        loop.run_forever()
