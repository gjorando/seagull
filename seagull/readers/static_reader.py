from typing import TYPE_CHECKING

from attrs import define

from seagull.objects import BaseObject

from .base_reader import BaseReader

if TYPE_CHECKING:
    from seagull.typeshed import StrPath


@define
class StaticReader[T: BaseObject](BaseReader):
    """Reader for static data."""

    def _parse_raw_data(self, text_or_bytes: str | bytes) -> dict[str, str | list[str]]:
        del text_or_bytes  # Unused argument
        # A static asset doesn't parse any content
        return {}

    def __call__(
        self,
        object_class: type[T],
        source_path: StrPath,
        /,
        *,
        default_values: dict[str, object] | None = None,
    ) -> T:
        default_values = default_values or {}
        default_values.setdefault("name", source_path)
        default_values.setdefault("source_path", source_path)

        # The static parser doesn't read a file, it simply records its source path
        return self.loads(object_class, "", default_values=default_values)
