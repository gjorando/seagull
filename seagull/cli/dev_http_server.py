from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import ClassVar

from seagull.log import logger


class DevHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Request handler for the development HTTP server."""

    extensions_map: ClassVar[dict[str, str]] = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".oft": "font/oft",
        ".sfnt": "font/sfnt",
        ".ttf": "font/ttf",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }

    def translate_path(self, path: str) -> str:
        original_path = Path(path)
        # Try multiple candidates for a raw path
        candidate_paths = [
            # Add .html to the name if it exists
            *((original_path.with_suffix(".html"),) if original_path.name else ()),
            # Or assume the path is a directory and try to get its index
            original_path / "index.html",
            # Or try the original path as is
            original_path,
        ]
        for candidate in candidate_paths:
            translated_path = Path(super().translate_path(str(candidate)))
            if translated_path.exists():
                return str(translated_path)
        log_candidates = ", ".join(f"'{p}'" for p in candidate_paths)
        logger.warning(f"Unable to find '{path}' or variations:\n{log_candidates}")
        return ""

    def log_message(self, msg_format: str, *args: list) -> None:
        logger.info(msg_format, *args)


class DevHTTPServer(HTTPServer):
    """Development HTTP server."""

    allow_reuse_address: bool = True

    def __init__(self, addr: str, port: int, output_path: Path):
        """Initialize the development server

        :param addr: Address to listen to.
        :param port: Port to listen on.
        :param output_path: Path to serve.
        """
        super().__init__(
            server_address=(addr, port),
            RequestHandlerClass=lambda req, addr, server: DevHTTPRequestHandler(
                req, addr, server, directory=output_path
            ),
        )
