import logging
import multiprocessing
import sys
import traceback
from pathlib import Path
from platform import python_version
from typing import NamedTuple

import click_extra as clickx

from seagull.cli.autoreload import Autoreload
from seagull.cli.click import (
    CliVerboseOption,
    CliVerbosityOption,
    IPAddressType,
    JsonKeyValueType,
    do_print_settings,
    parse_overrides,
)
from seagull.cli.dev_http_server import DevHTTPServer
from seagull.decorators import timed_execution
from seagull.log import logger
from seagull.settings import Settings


class ProcessExceptionData(NamedTuple):
    process_name: str
    exception: Exception
    traceback: str


class ProcessWithExceptions(multiprocessing.Process):
    """A process that handles exceptions.

    From `https://stackoverflow.com/a/33599967`.
    """

    def __init__[**P](
        self, excqueue: multiprocessing.Queue, log_level: int, **kwargs: P.kwargs
    ):
        super().__init__(**kwargs)
        self.excqueue = excqueue
        self._exception: ProcessExceptionData | None = None
        self.log_level = log_level

    def run(self) -> None:
        try:
            logger.setLevel(self.log_level)
            super().run()
            # No exception
            self.excqueue.put(None)
        except Exception as e:  # noqa: BLE001
            # Send the exception and traceback
            self.excqueue.put(
                ProcessExceptionData(
                    process_name=self.name,
                    exception=e,
                    traceback=traceback.format_exc(),
                )
            )

    @property
    def exception(self) -> ProcessExceptionData | None:
        if e := self.excqueue.get():
            self._exception = e
        return self._exception


# TODO this could be done with click chained commands
def autoreload_run(settings_path: Path, **overrides: dict) -> None:
    """Run an `Autoreload` instance, watching for file changes.

    :param settings_path: Path to the settings file.
    :param overrides: Overrides for the settings.
    """
    settings = Settings.from_settings_file(settings_path, **overrides)
    auto_reloader = Autoreload(settings)
    log_watched_files = ", ".join(
        f"'{p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p}'"
        for p in auto_reloader.watched_files
    )
    clickx.echo(f"Autoreload watching for changes in {log_watched_files}.")
    auto_reloader.run()


def single_run(settings_path: Path, **overrides: dict) -> None:
    """Execute a single seagull run.

    :param settings_path: Path to the settings file.
    :param overrides: Overrides for the settings.
    """
    settings = Settings.from_settings_file(settings_path, **overrides)
    seagull = settings.seagull_class(settings)
    clickx.echo("Generating...")
    timed_run = timed_execution(
        seagull.run,
        msg="Generation took {exec_time:.2f} seconds to complete.",
    )
    timed_run()
    clickx.echo("Done!")


def serve(settings_path: Path, **overrides: dict) -> None:
    """Run the development server.

    :param settings_path: Path to the settings file.
    :param overrides: Overrides for the settings.
    """
    # Load the settings, but temporarily silence non-critical logs so that they don't
    # repeat with the other process' logs
    log_level = logger.level
    logger.setLevel(level=logging.CRITICAL)
    settings = Settings.from_settings_file(settings_path, **overrides)
    addr = str(settings.bind)
    port = settings.port
    output_path = settings.output_path
    logger.setLevel(log_level)
    try:
        server = DevHTTPServer(addr, port, output_path)
    except OSError:
        logger.error(f"Couldn't listen on '{addr}:{port}'.")
        raise

    try:
        clickx.echo(f"Serving site at 'http://{addr}:{port}'.")
        server.serve_forever()
    except KeyboardInterrupt:
        clickx.echo("Shutting down server.")
        server.socket.close()
        raise


# TODO in help, defaults that are displayed in the help should show the Settings object default values (actual defaults must still be `None`, except if there's a way to check if the value comes an explicit command line override, or a default)
@clickx.command(
    "seagull",
    params=[  # basic click_extra options
        clickx.ColorOption(),
        CliVerbosityOption(default_logger=logger),
        CliVerboseOption(default_logger=logger),
        clickx.ExtraVersionOption(),
    ],
)
@clickx.argument(
    "path",
    type=clickx.path(exists=True, file_okay=False),
    default=None,
    help="Path where to find the content files.",
)
@clickx.option(
    "--theme-path",
    "-t",
    "THEME",
    type=clickx.path(exists=True, file_okay=False),
    default=None,
    help="Path where to find the theme templates.",
)
@clickx.option(
    "--output",
    "-o",
    "OUTPUT_PATH",
    type=clickx.path(file_okay=False),
    default=None,
    help="Where to output the generated files.",
)
@clickx.option(
    "--cache-path",
    "CACHE_PATH",
    type=clickx.path(file_okay=False),
    default=None,
    help="Directory in which to store cache files.",
)
@clickx.option(
    "--delete-output-directory",
    "-d",
    "DELETE_OUTPUT_DIRECTORY",
    is_flag=True,
    default=None,
    help="Delete the output directory.",
)
@clickx.option(
    "--relative-urls",
    "RELATIVE_URLS",
    is_flag=True,
    default=None,
    help="Use relative urls in output, useful for site development.",
)
@clickx.option(
    "--port",
    "-p",
    "PORT",
    type=clickx.IntRange(0, 2**16, max_open=True),
    default=None,
    help="Port for the development HTTP server.",
)
@clickx.option(
    "--bind",
    "-b",
    "BIND",
    type=IPAddressType(),
    default=None,
    help="IP to bind to when the development HTTP server is enabled.",
)
@clickx.option(
    "--extra-settings",
    "-e",
    type=JsonKeyValueType(),
    callback=JsonKeyValueType.option_callback,
    multiple=True,
    help="Specify one or more SETTING=VALUE pairs to override settings. VALUE must be "
    'in JSON notation: specify string values as SETTING="some string"; booleans '
    "as SETTING=true or SETTING=false; None as SETTING=null.",
)
@clickx.option(
    "--settings",
    "-s",
    "settings_path",
    type=clickx.path(exists=True, dir_okay=False),
    default="pelicanconf.py",
    help="The settings of the application.",
)
# Non-settings related options go after the --settings/-s option
@clickx.option(
    "--print-settings",
    is_flag=True,
    expose_value=False,
    callback=do_print_settings,
    help="Print current configuration settings and exit.",
)
@clickx.option(
    "--ignore-cache",
    is_flag=True,
    help="Ignore content cache from previous runs by not loading cache files.",
)
@clickx.option(
    "--autoreload",
    "-r",
    is_flag=True,
    help="Rerun seagull each time a modification occurs on the content files.",
)
@clickx.option(
    "--listen",
    "-l",
    is_flag=True,
    help="Run the development HTTP server.",
)
def main(
    settings_path: Path,
    *,
    ignore_cache: bool = False,
    autoreload: bool = False,
    listen: bool = False,
    **overrides: dict,
) -> None:
    """A tool to generate a static blog, with restructured text input files.

    \f
    :param settings_path: Path to the settings file.
    :param ignore_cache: If `True`, the cache is ignored from previous runs is ignored.
    :param autoreload: If `True`, the output is regenerated each time a content file is
    modified.
    :param listen: If `True`, start the HTTP development server.
    :param overrides: Settings overrides.
    """
    # Use click_extra's version option to retrieve the package version
    version_options = [
        p
        for p in clickx.get_current_context().command.params
        if isinstance(p, clickx.ExtraVersionOption)
    ]
    ver = version_options[0].version if version_options else "(unknown)"
    # Some debug information
    logger.debug(f"Seagull version {ver}.")
    logger.debug(f"Python version {python_version()}.")
    logger.debug(f"Settings sourced from '{settings_path}'.")
    if ignore_cache:
        raise NotImplementedError("Caching")

    # Process the cli overrides
    parse_overrides(settings_path, overrides)

    try:
        run = autoreload_run if autoreload else single_run
        # Run the HTTP server in parallel with the run call if listen is on
        if listen:
            excqueue = multiprocessing.Queue()
            run_process = ProcessWithExceptions(
                target=run,
                args=(settings_path,),
                kwargs=overrides,
                name="seagull runner",
                excqueue=excqueue,
                log_level=logger.level,
            )
            server_process = ProcessWithExceptions(
                target=serve,
                args=(settings_path,),
                name="development server",
                excqueue=excqueue,
                # Ensure we have at least log level of INFO
                log_level=min(logger.level, logging.INFO),
            )

            try:
                run_process.start()
                server_process.start()
                exc: ProcessExceptionData
                while True:
                    if exc := excqueue.get():
                        logger.error(
                            f"'{exc.process_name}' raised a "
                            f"{type(exc.exception).__name__} exception."
                        )
                        logger.error(exc.traceback)
                        raise exc.exception
            finally:
                # Terminate our running processes
                run_process.terminate()
                server_process.terminate()
        # Otherwise, if listen is off, simply run
        else:
            run(settings_path)
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt received. Exiting.")
    except Exception as e:  # noqa: BLE001
        # Log the exception and terminate
        logger.critical(f"{type(e)}: {e}", exc_info=logger.level == logging.DEBUG)
        sys.exit(1)
