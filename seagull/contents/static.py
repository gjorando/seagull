from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from seagull.contents.seagull_object import SeagullObject
from seagull.utils import PluralFormatter

if TYPE_CHECKING:
    from pathlib import Path

    from seagull.context import Context


@dataclass
class Static(SeagullObject):
    """Seagull static content."""

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        "source_path",
        *SeagullObject.MANDATORY_FIELDS,
    )

    def update_intrasite_links(self, context: Context) -> None:
        # This is a no-op for static files: static files don't have rendered content
        # that needs to be updated
        pass

    @classmethod
    def printable_name(cls, count: int = 1) -> str:
        return PluralFormatter().format("static file{count:plural,s}", count=count)

    @property
    def _save_as(self) -> Path:
        # Static files retain the directory structure relative to the base path.
        return self.relative_source_path

    @property
    def _url(self) -> str:
        return str(self._save_as)
