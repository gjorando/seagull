from pathlib import Path

from attrs import field

from seagull.api.utils import IntrasiteLink, seagull_object

from .seagull_object import SeagullObject


@seagull_object
class Asset(SeagullObject):
    """Static asset, copied as-is into the output site."""

    source_path: Path | str = field(converter=Path, repr=lambda val: f"'{val}'")
    """The source path is mandatory for an asset."""

    def __attrs_post_init__(self) -> None:
        if self.save_as is None:
            self.save_as = self.relative_source_path
        super().__attrs_post_init__()
