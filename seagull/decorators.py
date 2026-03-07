import functools
import time
from dataclasses import fields
from typing import TYPE_CHECKING, dataclass_transform

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

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
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


def extra_dataclass[T](
    cls_: Callable | None = None, *, ignore_extra: bool = False
) -> Callable:
    """Decorator for dataclasses that accept an arbitrary number of extra arguments.

    This decorator must be put before the `dataclass` decorator. This decorator probably
    won't work with dataclasses who define a custom `__init__` method.

    The decorator adds a class attribute `__extra_dataclass__` set to `True`, so that
    a dataclass with this decorator can be identified later.

    :param cls_: Dataclass to wrap.
    :param ignore_extra: Whether to simply ignore extra arguments. If `False`, the
    decorator adds a `__extra_dataclass__attrs__` tuple attribute to the class. This
    allows the user to query the list of extra attributes. Extra arguments are stored
    as attributes in the instance, but they don't become dataclass fields. If `True`,
    extra arguments are simply ignored.
    :return: Updated dataclass.
    """

    @dataclass_transform()
    def decorator(cls: type[T]) -> type[T]:
        # Save the base __init__ method
        base_init = cls.__init__
        dataclass_fields = {f.name for f in fields(cls)}

        @functools.wraps(base_init)
        def init_wrapper(self, *args, **kwargs):
            # Accepted field arguments for the dataclass
            base_kwargs = {k: v for k, v in kwargs.items() if k in dataclass_fields}

            # Call the base __init__
            base_init(self, *args, **base_kwargs)
            # If extra arguments aren't simply ignored...
            if not ignore_extra:
                extra_kwargs = {
                    k: v for k, v in kwargs.items() if k not in dataclass_fields
                }
                # ... Set extra attributes
                for k, v in extra_kwargs.items():
                    setattr(self, k, v)
                self.__extra_dataclass__attrs__ = tuple(extra_kwargs.keys())

        cls.__init__ = init_wrapper
        # FIXME a bit hacky, do better
        cls.__extra_dataclass__ = True
        return cls

    if cls_:
        return decorator(cls_)
    return decorator
