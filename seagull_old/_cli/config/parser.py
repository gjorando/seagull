from attrs import define

from seagull.api.parsers import Parser

from .base import BaseConfig
from .utils import instance_class_field, instance_field


@define(kw_only=True)
class ParserConfig[T: Parser](BaseConfig):
    """Configuration schema for a Seagull `Parser` object."""

    instance_class: type[T] = instance_class_field(
        default=Parser,
        base_module="seagull.api.parsers",
    )
    instance: Parser = instance_field(flattened=True)
