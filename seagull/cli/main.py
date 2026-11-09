import click_extra as clickx

from seagull.cli.utils import (
    SeagullVerboseOption,
    SeagullVerbosityOption,
)
from seagull.logging import logger


@clickx.group(
    "seagull",
    params=[
        clickx.TimerOption(),
        clickx.AccessibleOption(),
        clickx.ColorOption(),
        clickx.NoColorOption(),
        clickx.ProgressOption(),
        clickx.TableFormatOption(),
        SeagullVerbosityOption(default_logger=logger),
        SeagullVerboseOption(default_logger=logger),
        clickx.QuietOption(default_logger=logger),
        clickx.VersionOption(),
    ],
)
def main() -> None:
    """A modular static site generator."""
