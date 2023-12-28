import asyncio as aio
import os
from typing import Any

CONTENT_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".xml": "application/xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain",
}


class Response:
    def __init__(self, data: Any, status: int = 200, headers: dict = None):
        self.data = data
        self.status = status
        self.headers = headers or {}

    def __repr__(self):
        return f"<Response {self.status}>"

    async def send(self, writer: aio.StreamWriter):
        # Write the status line
        writer.write(f"HTTP/1.0 {self.status}\n".encode("utf-8"))

        # Write the headers
        [
            writer.write(f"{key}: {value}\n".encode("utf-8"))
            for key, value in self.headers.items()
        ]

        # Write the body
        writer.write(b"\n")
        if self.data:
            if isinstance(self.data, str):
                writer.write(self.data.encode("utf-8"))
            else:
                writer.write(self.data)

        # Flush the writer to close the request
        writer.write(b"\r\n")
        await writer.drain()
        writer.close()


def redirect(location: str, status: int = 302) -> Response:
    """
    Redirect to a different location.

    Args:
        location (str): The location to redirect to. Can be relative.
        status (int): The status code to use. Default to 302.

    Returns:
        Response: The response object.
    """
    return Response(None, status=status, headers={"Location": location})


def send_file(path: str, mimetype: str = None, download_name: str = None) -> Response:
    """
    Send a file to the client.

    Args:
        path (str): The path to the file to send.
        mimetype (str): The mimetype to use. If not provided, it will be guessed from the file extension.
        download_name (str): The name of the file to send to the client.
            If not provided, the original file name will be used.

    Returns:
        Response: The response object.
    """
    if ".." in path or path.startswith("/"):
        return Response("Not found", 404)

    if not os.path.exists(path):
        return Response("Not found", 404)

    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return Response("Not found", 404)

    # Get the content type
    content_type = "application/octet-stream"
    if os.path.splitext(path)[1] in CONTENT_TYPES:
        content_type = CONTENT_TYPES[os.path.splitext(path)[1]]

    # Set the headers
    headers = dict()
    headers["Content-Length"] = str(len(data))
    headers["Content-Type"] = mimetype or content_type
    if download_name:
        headers["Content-Disposition"] = f'attachment; filename="{download_name}"'

    return Response(data, 200, headers=headers)
