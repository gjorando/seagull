from functools import partial
from typing import TYPE_CHECKING

from click_extra import new_extra_logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from logging import Logger
    from pathlib import Path

# TODO use rich handler instead
logger: Logger = new_extra_logger(
    name="seagull", format="{asctime} {levelname} | {message}", datefmt="[%H:%M:%S]"
)


def log_with_paths[**P](
    log_callable: Callable,
    msg: str,
    *args: P.args,
    paths: list[Path],
    **kwargs: P.kwargs,
) -> None:
    """Log a message with one or more paths attached to it.

    :param log_callable: A callable object that logs a message, typically one of the
    log methods from a `Logger` instance.
    :param msg: Message format string.
    :param args: Arguments merged into `msg`.
    :param paths: List of paths to report.
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
