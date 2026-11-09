from typing import TYPE_CHECKING

from attrs import define, field

from seagull.logging import logger
from seagull.objects import BaseObject, Index

from .generator import Generator

if TYPE_CHECKING:
    from pathlib import Path


@define
class IndexesGenerator[T: Index](Generator):
    """Special generator for indexes."""

    object_class: type[Index] = field(default=Index)
    auto_index: set[type[BaseObject]] = field(factory=set, converter=set)
    """Object types for which an index should be auto-generated."""

    def __call__(
        self,
        content_path: Path,
        processed_paths: dict[Path, bool] | None = None,
        /,
        *,
        default_values: dict[str, object] | None = None,
    ) -> list[T]:
        indexes: list[T] = super().__call__(
            content_path,
            processed_paths,
            default_values=default_values,
        )

        # TODO all languages?
        # Generate auto indexes that haven't been manually created
        for auto_idx_class in self.auto_index - {o.object_class for o in indexes}:
            name = auto_idx_class.printable_name(count=2)
            obj = self.object_class(
                name=name.capitalize(),
                slug=name,
                content="",
                object_class=auto_idx_class,
            )
            indexes.append(obj)
            logger.debug(
                f"Auto-generated the {self.object_class.printable_name()} '{obj.name}'."
            )

        return indexes
