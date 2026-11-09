from attrs import define, field

from seagull.api.objects import Asset
from seagull.api.parsers import Parser
from seagull.api.utils import object_class_field

from .generator import Generator


@define
class AssetsGenerator(Generator):
    """Special generator class for static assets."""

    object_class: type[Asset] = object_class_field(Asset, is_default=True)

    @staticmethod
    def _get_parser(extension: str) -> Parser:
        del extension  # Unused argument
        return Parser.from_extension(None)()

    @staticmethod
    def _is_valid_extension(extension: str) -> bool:
        # The assets generator accepts any extension
        del extension  # Unused
        return True
