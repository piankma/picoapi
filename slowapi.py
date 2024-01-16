try:
    import asyncio as aio
except ImportError:
    import uasyncio as aio

try:
    import ujson as json
except ImportError:
    import json

try:
    import utime as time
except ImportError:
    import time

import gc

from micropython import const

CONTENT_TYPES = {
    "html": "text/html",
    "css": "text/css",
    "js": "text/javascript",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "json": "application/json",
}
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


class Response:
    def __init__(self, data, status_code=200, headers=None):
        """
        Create a new response object.

        Args:
            data: The data to send to the client. Will be converted to bytes if needed.
            status_code (int): The status code to use. Defaults to 200.
            headers (dict): The headers to send to the client. Defaults to an empty dict.
        """
        self.data = data
        self.status_code = status_code
        self.headers = headers or {}
        self.http_version = "HTTP/1.1"

    def redirect(self, location, status_code=302):
        """
        Redirect to a different location.

        Args:
            location (str): The location to redirect to. Can be relative.
            status_code (int): The status code to use. Defaults to 302.

        Returns:
            None
        """
        self.headers["Location"] = location
        self.status_code = status_code

    def set_cookie(
        self,
        key,
        value,
        max_age=None,
        expires=None,
        path="/",
    ):
        """
        Adds a cookie to the response.

        Args:
            key (str): The name of the cookie.
            value (str): The value of the cookie.
            max_age (int): The maximum age of the cookie in seconds.
            expires (datetime.datetime): The expiration date of the cookie.
            path (str): The path of the cookie. Defaults to "/".

        Returns:
            None
        """
        # TODO: sanitize input

        cookie = f"{key}={value}"
        if max_age:
            cookie += f"; Max-Age={max_age}"
        if expires:
            cookie += "; Expires=" + expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        if path:
            cookie += f"; Path={path}"

        if "Set-Cookie" in self.headers:
            self.headers["Set-Cookie"] += f", {cookie}"
        else:
            self.headers["Set-Cookie"] = cookie

    async def send(self, writer: aio.StreamWriter, encoding="utf-8"):
        """
        Send the response to the client using the given writer.
        Closes the writer after sending the response. Therefore, this method will close the connection.

        Args:
            writer: Socket writer to use.
            encoding (str): The encoding to use. Defaults to utf-8.
        """

        writer.write(f"{self.http_version} {self.status_code}\r\n".encode(encoding))

        # Write the headers
        _ = [
            writer.write(f"{key}: {value}\r\n".encode(encoding))
            for key, value in self.headers.items()
        ]

        # Write the body
        writer.write(b"\r\n")
        if self.data:
            if isinstance(self.data, str):
                writer.write(self.data.encode(encoding))
            else:
                writer.write(self.data)

        # Flush the writer to close the request
        writer.write("\r\n".encode(encoding))
        await writer.drain()
        writer.close()


def send_file(path, mimetype=None, download_name=None):
    """
    Send a file to the client.

    Args:
        path (str): The path to the file to send.
        mimetype (str): The mimetype to use. If not provided, try to guess it from the file extension.
            Defaults to application/octet-stream.
        download_name (str): The name of the file to send to the client.
            If not provided, the original file name will be used.

    Returns:
        Response: The response object.
    """
    if ".." in path:
        return Response("Not found", 404)

    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return Response("Not found", 404)

    # Get the content type
    if not mimetype:
        mimetype = "application/octet-stream"
        extension = path.split(".")[-1].lower()
        if extension in CONTENT_TYPES:
            mimetype = CONTENT_TYPES[extension]
        else:
            print(f"Unknown content type for file {path}")

    # Set the headers
    headers = dict()
    headers["Content-Length"] = str(len(data))
    headers["Content-Type"] = mimetype
    if download_name:
        headers["Content-Disposition"] = f'attachment; filename="{download_name}"'

    return Response(data, 200, headers=headers)


class Request:
    def __init__(self):
        """
        Create a new request object.
        """
        self.method = None
        self.path = None
        self.version = None
        self.headers = {}
        self.body = None
        self.json = None
        self.form = {}
        self.query = {}
        self.cookie = None
        self.source = None
        self.user_agent = None

    @staticmethod
    def parse_query_string(query):
        """
        Parse a query string into a dict.
        Args:
            query: The query string to parse.

        Returns:
            dict: The parsed query string stored as a key=value dict.

        """
        result = {}
        for qi in query.split("&"):
            try:
                key, value = qi.split("=")
            except ValueError:
                key = qi
                value = None
            result[key] = value
        return result

    @classmethod
    async def from_stream(cls, reader):
        """
        Read a request from the given reader and return a Request instance.

        Args:
            reader (asyncio.StreamReader): The object to read from.

        Returns:
            Request: The parsed request.
        """

        # Create a new instance of this class
        self = cls()

        encoding = "utf-8"  # TODO: Guess encoding from headers

        # Read the first line of HTTP request
        request_line = await reader.readline()
        self.method, self.path, self.version = request_line.decode(encoding).split()

        # Read the headers
        while True:
            header = await reader.readline()
            if header == b"\r\n":
                break

            if header.startswith(b"Cookie: "):
                self.cookie = self.parse_query_string(
                    header.decode(encoding).split(": ")[1].strip()
                )
                continue

            if header.startswith(b"User-Agent: "):
                self.user_agent = header.decode(encoding).split(": ")[1].strip()
                continue

            key, value = header.decode(encoding).split(": ")
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


class SlowAPI:
    def __init__(self, debug=False):
        """
        Entry point for the SlowAPI framework.

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
                print("Registering route %s -> %s()" % (path, getattr(handler, "__name__", "function")))

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
                return send_file(path)

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
            real_start = time.ticks_ms()

        # Read the request
        request = await Request.from_stream(reader)
        try:
            request.source_ip, request.source_port = writer.get_extra_info("peername")
        except ValueError:
            request.source_ip, request.source_port = (None, None)

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
            real_end = time.ticks_ms() - real_start
            log_string += f" ({real_end}ms)"
            response.headers["Server-Timing"] = f"req;dur={real_end}ms"

            print(log_string)
            print(gc.mem_alloc(), gc.mem_free())


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

        gc.collect()
        if self.debug:
            print(gc.mem_alloc(), gc.mem_free())

        loop = aio.get_event_loop()
        loop.create_task(aio.start_server(self.handle_request, host, port))
        loop.run_forever()
