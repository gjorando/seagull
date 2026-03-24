import functools
import time
from typing import TYPE_CHECKING

from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable


def timed_execution(
    func_: Callable | None = None, *, msg: str | None = None
) -> Callable:
    """Decorator that logs the execution time of a function.

    :param func_: Function to wrap.
    :param msg: Optional override for the message that reports the execution time.
    Available format parameters are all the local variables of
    `timed_execution.decorator.wrapper`.
    """

    def decorator[T, **P](func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
            func_name = func.__name__
            start_time = time.time()
            return_value = func(*args, **kwargs)
            end_time = time.time()
            exec_time = end_time - start_time
            # FIXME use another print function like click.echo
            logger.info(msg.format(**locals()))
            return return_value

        return wrapper

    # Default message
    if msg is None:
        msg = "{func_name} took {exec_time:.2f} seconds."

    if func_:
        return decorator(func_)
    return decorator
