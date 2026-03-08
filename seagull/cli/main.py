from dataclasses import asdict
from pathlib import Path
from platform import python_version
from pprint import pformat
from typing import TYPE_CHECKING

import click_extra as clickx

from seagull.cli.click import (
    CliVerboseOption,
    CliVerbosityOption,
    IPAddressType,
    JsonKeyValueType,
    SeagullSettingsType,
)
from seagull.decorators import timed_execution
from seagull.log import logger
from seagull.seagull import Seagull

if TYPE_CHECKING:
    from seagull.settings import Settings


# TODO in help, defaults should show the Settings object default values
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
    help=" IP to bind to when the development HTTP server is enabled.",
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
    type=SeagullSettingsType(),
    default="pelicanconf.py",
    help="The settings of the application.",
)
# Non-settings related options go after the --settings/-s option
@clickx.option(
    "--print-settings",
    is_flag=True,
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
@clickx.option("--listen", "-l", is_flag=True, help="Run the development HTTP server.")
def main(
    settings: Settings,
    *,
    print_settings: bool = False,
    ignore_cache: bool = False,
    autoreload: bool = False,
    listen: bool = False,
) -> None:
    """A tool to generate a static blog, with restructured text input files.

    \f
    :param settings: A loaded `Settings` object.
    :param print_settings: If `True`, print the settings and exit.
    :param ignore_cache: If `True`, the cache is ignored from previous runs is ignored.
    :param autoreload: If `True`, the output is regenerated each time a content file is
    modified.
    :param listen: If `True`, start the HTTP development server.
    """
    # Use clickx's version option to retrieve the package version
    version_options = [
        p
        for p in clickx.get_current_context().command.params
        if isinstance(p, clickx.ExtraVersionOption)
    ]
    ver = version_options[0].version if version_options else "(unknown)"
    # Some debug information
    logger.debug(f"Seagull version: {ver}")
    logger.debug(f"Python version: {python_version()}")
    logger.debug(f"Using theme '{settings.theme.name}'.")
    if ignore_cache:
        raise NotImplementedError("Caching")

    # Print settings and exit
    # TODO find a way to use a clickx callback instead
    if print_settings:
        settings_dict = asdict(settings)
        # TODO also report extra settings
        for k, v in settings_dict.items():
            if k.startswith("_"):
                continue
            match v:
                case dict() | list():
                    display_value = pformat(v)
                case Path() | str():
                    display_value = f"'{v}'"
                case _:
                    display_value = str(v)
            clickx.echo(f"{k.upper()}={display_value}")
        return

    try:
        if autoreload:
            raise NotImplementedError("Autoreload mode")
        if listen:
            raise NotImplementedError("Development server")

        seagull = Seagull(settings)
        clickx.echo("Generating...")

        timed_run = timed_execution(
            seagull.run, msg="Generation took {exec_time:.2f} seconds to complete."
        )
        timed_run()
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt received. Exiting.")
    except Exception as e:
        # Log the exception and re-raise it
        logger.critical(f"{e.__class__.__name__}: {e}", exc_info=True)
        raise
