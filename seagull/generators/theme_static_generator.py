from typing import TYPE_CHECKING

from seagull.contents.static import Static
from seagull.generators.static_generator import StaticGenerator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class ThemeStaticGenerator[T: Static](StaticGenerator):
    """Static generator for the static files of the theme."""

    @property
    def valid_paths(self) -> Iterable[Path]:
        return self.settings.theme_static_paths

    @property
    def excluded_paths(self) -> Iterable[Path]:
        # There is no theme_static_excludes
        return []

    @property
    def _extra_files(self) -> set[Path]:
        # No extra static path, this avoids reprocessing the discovered static links
        return set()

    @property
    def base_path(self) -> Path:
        # The base path of theme static files is the theme path
        return self.settings.theme
