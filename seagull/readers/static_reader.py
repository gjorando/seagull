from typing import TYPE_CHECKING, Any

from seagull.exceptions import InvalidObject
from seagull.readers import Reader

if TYPE_CHECKING:
    from pathlib import Path


class StaticReader(Reader):
    """Static files reader class.

    Static files aren't actually loaded in memory, but the reader returns a `Static`
    object nonetheless.
    """

    # None indicates this reader is suitable for static files
    file_extensions = [None]

    def _parse_data(self, path: Path) -> tuple[str, dict[str, Any]]:
        # A static file must exist in order to be valid
        if not path.exists():
            raise InvalidObject(f"Static file '{path}' doesn't exist.")
        metadata = {"title": path.stem}
        return "", metadata
