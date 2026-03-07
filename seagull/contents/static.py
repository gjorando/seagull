from dataclasses import dataclass
from typing import TYPE_CHECKING

from seagull.contents.seagull_object import SeagullObject

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(repr=False)
class Static(SeagullObject):
    """Seagull static content."""

    template: str | None = None

    # TODO allow for customization through *_SAVE_AS and *_URL settings?
    def _save_as(self) -> Path | None:
        """Static files retain the directory structure relative to the base path."""
        return self.relative_source_path

    def _url(self) -> str:
        return str(self._save_as())
