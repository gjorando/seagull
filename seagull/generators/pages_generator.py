from typing import TYPE_CHECKING

from seagull.contents import Page
from seagull.generators.generator import Generator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class PagesGenerator[T: Page](Generator):
    """Generate static pages."""

    content_class: type[T] = Page

    @property
    def base_path(self) -> Path:
        return self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return self.settings.page_paths

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return self.settings.page_excludes
