from typing import TYPE_CHECKING

from attrs import define, field

from seagull.objects import Asset

from .generator import Generator

if TYPE_CHECKING:
    from seagull.readers import BaseReader


@define
class AssetsGenerator(Generator):
    """Special generator class for static assets."""

    object_class: type[Asset] = field(default=Asset)

    def _get_reader(self, extension: str | None) -> BaseReader:
        # Always look for a reader that accepts any extension (typically StaticReader)
        del extension  # Unused argument
        return super()._get_reader(None)
