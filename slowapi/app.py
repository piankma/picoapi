try:
    import asyncio as aio
except ImportError:
    import uasyncio as aio

try:
    import json
except ImportError:
    import ujson as json

import os
import time

from slowapi.request import Request
from slowapi.response import Response, send_file


class SlowAPI:
    def __init__(self, debug = False):
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

                self.routes[(method, path)] = handler

            if self.debug:
                print(f"Registering route {path} -> {handler.__name__}()")

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


    def add_static_route(self, prefix, directory):
        """
        Register a static route.

        Args:
            prefix (str): The URL prefix to match.
            directory (str): The directory to serve files from.

        Returns:
            None

        """
        if not prefix.endswith("/"):
            prefix += "/"
        self.static_routes[prefix] = directory

        if self.debug:
            print(f"Registering static route {prefix} -> {directory}")

    async def handle_static(self, request):
        """
        Handle a static file request.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object
            None: If no static route matches.

        """
        for prefix, directory in self.static_routes.items():
            if request.path.startswith(prefix):
                response = self.serve_static(request, prefix, directory)
                return response

        return None

    async def handle_route(self, request):
        """
        Handle a route request.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object
            None: If no route matches.
        """
        handler = self.routes.get((request.method, request.path))
        if not handler:
            return None

        # Create a response object
        response = Response(None)
        result = await handler(request, response)

        if isinstance(result, Response):
            # If the handler returned a response object, return it directly
            return response
        elif isinstance(result, tuple):
            # If the handler returned a tuple, unpack it
            # tuple may contain up to 3 items: data, status and headers.
            if len(result) == 3:
                data, status, headers = result
            elif len(result) == 2:
                data, status = result
                headers = {}
            else:
                data = result[0]
                status = 200
                headers = {}

            response.data = response.data or data
            response.status_code = response.status_code or status
            response.headers.update(headers)
        elif isinstance(result, str):
            response.data = response.data or result
            response.status_code = response.status_code or 200
            if not response.headers.get("Content-Type"):
                response.headers["Content-Type"] = "text/plain"
        elif isinstance(result, (dict, list)):
            response.data = response.data or json.dumps(result)
            response.status_code = response.status_code or 200
            if not response.headers.get("Content-Type"):
                response.headers["Content-Type"] = "application/json"
        else:
            raise ValueError(f"Invalid response type {type(result)}")

        return response

    async def handle_request(self, reader, writer):
        """
        Main handler for incoming requests.

        Args:
            reader (asyncio.StreamReader): The reader to read the request from.
            writer (asyncio.StreamWriter): The writer to write the response to.

        Returns:
            None
        """
        if self.debug:
            real_start = time.time()

        # Read the request
        request = await Request.from_stream(reader)
        request.source_ip, request.source_port = writer.get_extra_info("peername")

        # Handle static files.
        # If not matching, try to handle routes.
        # If still not matching, return 404.
        response = await self.handle_static(request)
        if not response:
            response = await self.handle_route(request)
        if not response:
            response = Response("Not found", status_code=404)

        if self.debug:
            log_string = f"{request.source_ip}:{request.source_port}: {request.method} {request.path} {response.status_code}"
            real_end = time.time() - real_start
            log_string += f" ({real_end:.4f}s)"
            response.headers[
                "Server-Timing"
            ] = f"req;dur={real_end:.4f}s"

            print(log_string)

        await response.send(writer)
        await writer.wait_closed()

    def run(self, host: str = "127.0.0.1", port: int = 8000):
        print(f"Starting server on {host}:{port}...")

        # Create a new asyncio event loop
        loop = aio.get_event_loop()
        loop.create_task(aio.start_server(self.handle_request, host, port))
        loop.run_forever()
