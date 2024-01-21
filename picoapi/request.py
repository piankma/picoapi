import json


class Request:
    """Represents an HTTP request."""

    def __init__(self):
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
        self.source_ip = None
        self.source_port = None

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
