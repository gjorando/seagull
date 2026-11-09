from functools import partial
import logging
from string import Formatter
from typing import TYPE_CHECKING

import click_extra as clickx
from rich.console import Console
from rich.logging import RichHandler

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence, Sized
    from pathlib import Path

console = Console(stderr=False)

handler = RichHandler(
    rich_tracebacks=True,
    tracebacks_suppress=[clickx],
    console=console,
    markup=True,
)
handler.setFormatter(
    logging.Formatter(
        "[bold]%(message)s[/]",
        datefmt="[%X]",
    )
)
logger = logging.getLogger("seagull")
logger.addHandler(handler)


class PluralFormatter(Formatter):
    """A small helper class to format pluralized strings in a Python f-string.

    Format spec looks like this: `"plural,"val1[,val2[,val3]]`.
    - If only `val1` is defined, it gives a replacement if the value is not 1.
    - If `val2` is defined as well, `val1` gives a replacement if the value is 1. `val2`
    gives a replacement otherwise.
    - If `val3` is defined as well, it gives a replacement if the value is greater than
    one, `val2` if the value is 1, and `val1` otherwise.

    This works on integer, and objects which define a `__len__` method.

    Based on https://tobywf.com/2015/12/sane-pluralisation/.
    """

    def format_field(self, value: int | Sized, format_spec: str) -> str:
        if format_spec.startswith("plural,"):
            replacement_specs = format_spec.split(",")[1:]
            replacement_values = [""] * 3
            match len(replacement_specs):
                case 1:
                    replacement_values[0] = replacement_values[2] = replacement_specs[0]
                case 2:
                    replacement_values[0] = replacement_values[2] = replacement_specs[1]
                    replacement_values[1] = replacement_specs[0]
                case 3:
                    replacement_values = replacement_specs
                case _:
                    raise ValueError(f"Invalid pluralizer format '{format_spec}'.")
            # If the value is not int, we try to assume it has a length, and use it
            if not isinstance(value, int):
                value = len(value)

            if value > 1:
                return replacement_values[2]
            if value == 1:
                return replacement_values[1]
            return replacement_values[0]
        return super().format_field(value, format_spec)


def log_with_paths[**P](
    log_callable: Callable,
    msg: str,
    *args: P.args,
    paths: Sequence[Path],
    **kwargs: P.kwargs,
) -> None:
    """Log a message with one or more paths attached to it.

    :param log_callable: A callable object that logs a message, typically one of the
    log methods from a `Logger` instance.
    :param msg: Message format string.
    :param args: Arguments merged into `msg`.
    :param paths: Paths to report.
    :param kwargs: Other keyword arguments for `log_callable`.
    """
    # Add the list of paths to the format string
    msg += "\n * '%s'" * len(paths)
    # Extend the arguments with the list of string representations of each path
    log_callable(msg, *(args + tuple(str(p) for p in paths)), **kwargs)


# Shorthands for log_with_paths using the seagull logger
debug_with_paths = partial(log_with_paths, logger.debug)
info_with_paths = partial(log_with_paths, logger.info)
warning_with_paths = partial(log_with_paths, logger.warning)
error_with_paths = partial(log_with_paths, logger.error)
critical_with_paths = partial(log_with_paths, logger.critical)
exception_with_paths = partial(log_with_paths, logger.exception)
