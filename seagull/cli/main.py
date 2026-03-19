import os
from platform import python_version
from typing import TYPE_CHECKING

import click_extra as clickx

from seagull import Settings
from seagull.cli.click import (
    pass_settings,
    seagull_verbose_option,
    seagull_verbosity_option,
    seagull_version,
)
from seagull.decorators import timed_execution
from seagull.log import logger

if TYPE_CHECKING:
    import threading


@clickx.group(
    "seagull",
    invoke_without_command=True,
    params=[],
    chain=True,
    config_schema=Settings,
)
@clickx.color_option
@clickx.show_params_option
@seagull_verbosity_option(default_logger=logger)
@seagull_verbose_option(default_logger=logger)
@clickx.version_option
@clickx.option_group(
    "Seagull settings",
    clickx.config_option(
        "--settings",
        "-s",
        default="seagull.toml",
        type=clickx.path(exists=True, dir_okay=False),
        file_format_patterns=[
            clickx.ConfigFormat.TOML,
            clickx.ConfigFormat.YAML,
            clickx.ConfigFormat.JSON,
            clickx.ConfigFormat.INI,
            clickx.ConfigFormat.PYPROJECT_TOML,
        ],
    ),
    clickx.option(
        "--content-path",
        "path",
        type=clickx.path(exists=True, file_okay=False),
        default=".",
        help="Path where to find the content files.",
        expose_value=False,
    ),
    clickx.option(
        "--theme-path",
        "-t",
        "theme",
        # TODO exists=True, resolving the theme path
        type=clickx.path(exists=False, file_okay=False),
        default=None,
        help="Path where to find the theme templates.",
        expose_value=False,
    ),
    clickx.option(
        "--output",
        "-o",
        "output_path",
        type=clickx.path(file_okay=False),
        default="output",
        help="Where to output the generated files.",
        expose_value=False,
    ),
    clickx.option(
        "--delete-output-directory",
        "-d",
        "delete_output_directory",
        is_flag=True,
        default=False,
        help="Delete the output directory.",
        expose_value=False,
    ),
    clickx.option(
        "--relative-urls",
        "relative_urls",
        is_flag=True,
        default=False,
        help="Use relative urls in output, useful for site development.",
        expose_value=False,
    ),
)
@pass_settings
@clickx.pass_context
def main(ctx: clickx.Context, settings: Settings) -> None:
    """A tool to generate a static blog, with restructured text input files."""
    # Prevent running the command if a chain command asked for the help page
    if any(
        help_opt in ctx.meta["click_extra.raw_args"]
        for help_opt in ctx.help_option_names
    ):
        return

    # The object stores subcommand threads
    ctx.ensure_object(list)

    # Paths are all relative to the configuration file
    # FIXME fix paths explicitly set in the command line or environment, they are relative to the user's cwd, not the settings path
    cwd = settings.settings_path.parent
    os.chdir(cwd)

    # Some debug information
    logger.debug(f"Seagull version {seagull_version()}.")
    logger.debug(f"Python version {python_version()}.")
    logger.debug(f"Settings sourced from '{settings.settings_path}'.")

    # And we run Seagull
    # FIXME handle failure in both single run and autoreload
    seagull = settings.seagull_class(settings)
    clickx.echo("Generating...")
    timed_run = timed_execution(
        seagull.run,
        msg="Generation took {exec_time:.2f} seconds to complete.",
    )
    timed_run()
    clickx.echo("Done!")


@main.result_callback()
@clickx.pass_obj
def run_threads(thread_list: list[threading.Thread], *_: None) -> None:
    """Wait for the subcommand threads to finish running."""
    for t in thread_list:
        t.start()
    for t in thread_list:
        t.join()
