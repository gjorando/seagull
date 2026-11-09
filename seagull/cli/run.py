from pathlib import Path
from platform import python_version

from attrs import fields_dict
import click_extra as clickx

from seagull import Seagull
from seagull.cli.utils import PyConfigOption, pass_seagull, seagull_run, seagull_version
from seagull.logging import logger
from seagull.readers import BaseReader

from .main import main


def bootstrap_seagull_from_script(config_dict: dict[str, object]) -> Seagull:
    """Instantiate a Seagull instance from a configuration script."""
    # Register the readers, falling back to the default reader configuration
    try:
        readers = config_dict.pop("readers")
        readers: list
        _ = iter(readers)
    except KeyError:
        logger.warning("No readers defined in the configuration module.")
        readers = []
    except TypeError:
        raise TypeError("'readers' variable is not iterable") from None
    for i, reader in enumerate(readers):
        if not isinstance(reader, BaseReader):
            raise TypeError(f"'readers[{i}]' variable is not a reader object")
        reader.registered = True

    # If we have an instance variable, simply use it
    if instance := config_dict.get("seagull"):
        if not isinstance(instance, Seagull):
            raise TypeError("'instance' variable is not a 'Seagull' object")
        return instance
    # Otherwise, filter-out invalid keys
    valid_init_keys = [k for k, v in fields_dict(Seagull).items() if v.init]
    # TODO put other keys in a Seagull.metadata attribute
    init_dict = {k: v for k, v in config_dict.items() if k in valid_init_keys}
    # And instantiate the Seagull object
    return Seagull(**init_dict)


@main.group(
    "run",
    invoke_without_command=True,
    params=[
        PyConfigOption(
            config_schema=bootstrap_seagull_from_script,
        )
    ],
)
@pass_seagull
@clickx.pass_context
def run(ctx: clickx.Context, seagull: Seagull) -> None:
    """Generate a Seagull static site."""
    # Some debug information
    settings_path = Path(ctx.meta[clickx.context.CONF_SOURCE]).relative_to(
        Path.cwd(),
        walk_up=True,
    )
    logger.debug(f"Seagull version {seagull_version()}.")
    logger.debug(f"Python version {python_version()}.")
    logger.debug(f"Settings file: '{settings_path}'.")
    seagull_run(
        seagull,
        progress=bool(ctx.meta[clickx.context.PROGRESS]),
        timer=clickx.context.START_TIME in ctx.meta,
    )
