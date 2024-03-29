import asyncio as aio


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

    @staticmethod
    async def send_file(path, mimetype=None, download_name=None):
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
            return Response("Forbidden", 403)

        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            return Response("Not Found", 404)

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

        return Response(data, headers=headers)

    @staticmethod
    async def redirect(location, status_code=302):
        """
        Redirect to a different location.

        Args:
            location (str): The location to redirect to. Can be relative.
            status_code (int): The status code to use. Defaults to 302.

        Returns:
            Response: The response object.
        """
        return Response(None, status_code, {"Location": location})

    async def send(self, writer: aio.StreamWriter, encoding="utf-8"):
        """
        Send the response to the client using the given writer.
        Closes the writer after sending the response. Therefore, this method will close the connection.

        Args:
            writer: Socket writer to use.
            encoding (str): The encoding to use. Defaults to utf-8.
        """

        writer.write(f"{self.http_version} {self.status_code}\r\n".encode(encoding))
        await writer.drain()

        # Write the headers
        _ = [
            writer.write(f"{key}: {value}\r\n".encode(encoding))
            for key, value in self.headers.items()
        ]
        await writer.drain()

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
