import asyncio as aio
import json
import time

try:
    from gc import collect

    from micropython import const
except ImportError:
    collect = None
    const = lambda x: x

from picoapi.request import Request
from picoapi.response import Response

HTTP_METHODS = const(
    (
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
        "HEAD",
    )
)


class Server:
    def __init__(self, debug=False):
        """
        Server entry point.

        Args:
            debug (bool): Whether to print debug messages. Defaults to False.
        """

        self.debug = debug
        self.routes = {}
        self.static_routes = {}

    def route(self, path, methods=None):
        """
        Decorator to register a route handler.

        Args:
            path (str): The URL path to match.
            methods (set[str]): The HTTP methods to match.
                Defaults to GET, but will also add match for OPTIONS and HEAD.
        """

        def wrapper(handler):
            methods_set = methods or {"GET"}

            # all endpoints should support OPTIONS and HEAD
            methods_set.add("OPTIONS")
            methods_set.add("HEAD")

            # Register the handler for each method
            for method in methods_set:
                if method not in HTTP_METHODS:
                    raise ValueError(f"Invalid method {method} for route {path}")

                self.routes[(method, path)] = handler

            if self.debug:
                callable_name = getattr(handler, "__name__", "function")
                print(f"Registering route {path} -> {callable_name}()")

            return handler

        return wrapper

    def add_static_route(self, prefix, directory):
        """
        Register a static route.

        Args:
            prefix (str): The URL prefix to match.
            directory (str): The directory to serve files from.
        """
        if not prefix.endswith("/"):
            prefix += "/"
        if not directory.endswith("/"):
            directory += "/"

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
                path = f"{directory}{request.path[len(prefix):]}"
                return await Response.send_file(path)

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
        """
        if self.debug:
            real_start = time.time()

        # Read the request
        request = await Request.from_stream(reader)
        peername = writer.get_extra_info("peername")
        if isinstance(peername, tuple):
            request.source_ip, request.source_port = writer.get_extra_info("peername")
        elif isinstance(peername, (bytes, bytearray)):
            import socket

            _, ip, request.source_port = socket.sockaddr(peername)
            request.source_ip = ".".join(str(b) for b in ip)

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
            real_end = (time.time() - real_start) * 1000
            log_string += f" ({real_end:.3f}ms)"
            response.headers["Server-Timing"] = f"req;dur={real_end}ms"

            print(log_string)

        await response.send(writer)
        await writer.wait_closed()

    def run(self, host="127.0.0.1", port=8000):
        """
        Starts the HTTP server. Will run forever until interrupted.

        Args:
            host (str): The host to listen on. Localhost by default.
            port (int): The port to listen on. Default: 8000
        """
        print(f"Starting server on {host}:{port}...")

        # run garbage collection if micropython is available
        if collect:
            collect()

        loop = aio.get_event_loop()
        loop.create_task(aio.start_server(self.handle_request, host, port))
        loop.run_forever()
