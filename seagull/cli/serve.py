from pathlib import Path
from typing import TYPE_CHECKING

import click_extra as clickx
from livereload import Server

from seagull.cli.utils import (
    IPAddressType,
    PyConfigOption,
    default_watched_files,
    seagull_run,
)
from seagull.logging import PluralFormatter, debug_with_paths

from .run import run

if TYPE_CHECKING:
    from collections.abc import Callable
    from ipaddress import IPv4Address, IPv6Address


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
    "--watch",
    "-w",
    "watched_files",
    type=clickx.path(exists=True),
    multiple=True,
    default=default_watched_files,
    show_default="settings file, theme path, content path, template overrides",
    help="Paths to watch for.",
)
@clickx.option(
    "--open-browser", "-o", is_flag=True, help="Automatically open the web browser."
)
@clickx.pass_context
def serve(
    ctx: clickx.Context,
    address: IPv4Address | IPv6Address,
    port: int,
    watched_files: tuple[Path, ...],
    *,
    open_browser: bool,
) -> None:
    """Run the development HTTP server.

    The server automatically re-runs seagull when it detects content updates.
    """
    config_path: Path = Path(ctx.meta[clickx.context.CONF_SOURCE])

    def make_callback(watched: Path) -> Callable[[], None]:
        def callback() -> None:
            # The context must have a parent
            if not isinstance(ctx.parent, clickx.Context):
                return
            clickx.echo()
            # If the settings were changed, try to find the config option from the
            # parent command and use it to reload the settings object
            if watched.samefile(config_path):
                # We look for the PyConfigOption param of the parent ('run') command
                for param in ctx.parent.command.params:
                    if isinstance(param, PyConfigOption):
                        clickx.echo(
                            "Reloading the settings file and re-generating the site..."
                        )
                        # Reload the configuration
                        param.load_conf(ctx.parent, param, config_path)
                        break
                else:
                    clickx.echo("Couldn't reload the settings.", err=True)
                    return
            else:
                clickx.echo("Detected changes, re-generating the site...")
            # We re-run Seagull
            seagull_run(
                clickx.get_tool_config(ctx),
                progress=bool(ctx.meta[clickx.context.PROGRESS]),
                timer=clickx.context.START_TIME in ctx.meta,
            )

        return callback

    clickx.echo(f"Serving site at 'http://{address}:{port}'...")
    debug_with_paths(
        PluralFormatter().format(
            "Watching {len_paths} path{paths:plural,s}.",
            paths=watched_files,
            len_paths=len(watched_files),
        ),
        paths=watched_files,
    )

    server = Server()
    for watched_file in watched_files:
        server.watch(str(watched_file), make_callback(watched_file))

    try:
        server.serve(
            host=str(address),
            port=port,
            root=clickx.get_tool_config(ctx).output_path,
            open_url_delay=0.5 if open_browser else None,
        )
    except OSError as e:
        ctx.fail(f"Couldn't listen on '{address}:{port}' ({e}).")
