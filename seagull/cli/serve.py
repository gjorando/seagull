import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import click_extra as clickx

from seagull.cli.click import IPAddressType, pass_output_path
from seagull.cli.run import run
from seagull.log import logger

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address


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

    def __init__(self, address: str, port: int, output_path: Path):
        """Initialize the development server

        :param address: Address to listen to.
        :param port: Port to listen on.
        :param output_path: Path to serve.
        """
        super().__init__(
            server_address=(address, port),
            RequestHandlerClass=lambda req, addr, server: DevHTTPRequestHandler(
                req, addr, server, directory=output_path
            ),
        )


@run.command("serve")
@clickx.option(
    "--bind",
    "-b",
    "address",
    type=IPAddressType(),
    default="127.0.0.1",
    help="IP to bind to when the development HTTP server is enabled.",
)
@clickx.option(
    "--port",
    "-p",
    type=clickx.IntRange(0, 2**16, max_open=True),
    default=8000,
    help="Port for the development HTTP server.",
)
@clickx.option(
    "--open-browser", "-o", is_flag=True, help="Automatically open the web browser."
)
@pass_output_path
@clickx.pass_obj
def serve(
    thread_list: list,
    output_path: Path,
    address: IPv4Address | IPv6Address,
    port: int,
    *,
    open_browser: bool,
) -> None:
    """Run the development HTTP server."""

    def process() -> None:
        try:
            server = DevHTTPServer(str(address), port, output_path)
        except OSError:
            clickx.get_current_context().fail(f"Couldn't listen on '{address}:{port}'.")

        clickx.echo(f"Serving site at 'http://{address}:{port}'.")

        if open_browser:
            webbrowser.open(f"http://{address}:{port}")

        server.serve_forever()

    t = threading.Thread(target=process, daemon=True)
    thread_list.append(t)
