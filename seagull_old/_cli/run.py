from platform import python_version

import click_extra as clickx

from seagull._cli.config import CoreConfig
from seagull._cli.utils import pass_config, seagull_version
from seagull.logging import logger

from .main import main


@main.group(
    "run",
    invoke_without_command=True,
    params=[
        clickx.ConfigOption(
            default="seagull.toml",
            type=clickx.path(exists=True, dir_okay=False),
            config_schema=CoreConfig.from_config_dict,
            included_params=(),
        ),
        clickx.ValidateConfigOption(),
    ],
)
@pass_config
@clickx.pass_context
def run(ctx: clickx.Context, config: CoreConfig) -> None:
    """Generate a Seagull static site."""
    # Some debug information
    logger.debug(f"Seagull version {seagull_version()}.")
    logger.debug(f"Python version {python_version()}.")
    logger.debug(f"Settings file: '{ctx.meta[clickx.context.CONF_SOURCE]}'.")
    # We run Seagull
    config.execute(
        progress=bool(ctx.meta[clickx.context.PROGRESS]),
        timer=clickx.context.START_TIME in ctx.meta,
    )
