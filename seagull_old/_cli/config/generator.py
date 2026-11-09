from contextlib import suppress
import operator
from typing import TYPE_CHECKING

from attrs import define, field

from seagull import Seagull
from seagull.api.generators import Generator

from .base import BaseConfig
from .utils import (
    GeneratorPriority,
    base_config_field,
    instance_class_field,
    instance_field,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# TODO implement a better parser that accepts parenthesis, multiplications and divisions?
def _generator_priority_converter(value: str | int) -> int:
    """Converter for `GeneratorConfig.priority`.

    :param value: The value to convert. If it is a string, a very simple parsing
    operation is performed. The string must define an operation that only uses additions
    and substractions, no parenthesis, and where the operands are either integers or
    `GeneratorPriority` values.
    :return: Parsed integer priority.
    """

    def _parse(v: str) -> int:
        v = v.strip()
        # If v is empty, default to 0 (enable the use of a leading negative sign)
        if not v:
            return 0
        # Try to convert to an integer
        with suppress(ValueError):
            return int(v)
        # Otherwise, try to assume v is a GeneratorPriority
        try:
            return getattr(GeneratorPriority, v)
        except AttributeError:
            raise ValueError(
                f"Invalid priority: '{value}' ('{v}' is not a valid operand)"
            ) from None

    # If we already have an integer, return it
    if isinstance(value, int):
        return value
    # Valid operators
    operators: dict[str, Callable] = {"+": operator.add, "-": operator.sub}
    result = 0  # Accumulated result
    buffer = ""  # Next operand, unparsed
    # The first operator is an addition, which adds the
    # first operand to the initial value of result (0)
    next_operator = operators["+"]
    # We then go through the string one character at a time
    for c in value:
        # If we encounter a new operator, perform the operation and set the new operator
        if c in operators:
            result = next_operator(result, _parse(buffer))
            next_operator = operators[c]
            # We empty the buffer as well
            buffer = ""
        # Otherwise accumulate the current operand in the buffer
        else:
            buffer += c
    # If the buffer is empty after going through the
    # string, it means we have a trailing operator
    if not buffer:
        raise ValueError(f"'{value}': trailing operator '{value[-1]}'")
    # Otherwise we perform the final operation and return the result
    return next_operator(result, _parse(buffer))


def _generator_runtime_base_config(
    self: BaseConfig, value: dict[str, object]
) -> dict[str, object]:
    """Runtime base configuration for generators.

    It fetches the `Seagull` object from the root configuration object, and adds the
    default values of `Generator.content_path` and `Generator.output_path`.
    """
    if not isinstance(seagull := self.root_config.instance, Seagull):
        return value
    value |= {
        "content_path": seagull.content_path,
        "output_path": seagull.output_path,
    }
    return value


@define(kw_only=True)
class GeneratorConfig[T: Generator](BaseConfig):
    """Configuration schema for a Seagull `Generator` object."""

    _base_config: dict[str, object] = base_config_field(_generator_runtime_base_config)
    instance_class: type[T] = instance_class_field(
        default=Generator,
        base_module="seagull.api.generators",
    )
    instance: Generator = instance_field(flattened=True)
    enabled: bool = True
    """Whether to enable the generator."""
    priority: int = field(converter=_generator_priority_converter)
    """Used to sort the `GeneratorConfig` objects."""
