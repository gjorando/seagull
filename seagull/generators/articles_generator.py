from typing import TYPE_CHECKING

from seagull.contents import Article
from seagull.generators.generator import Generator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class ArticlesGenerator[T: Article](Generator):
    """Generate article pages."""

    content_class: type[T] = Article

    # TODO archives

    @property
    def base_path(self) -> Path:
        return self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return self.settings.article_paths

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return self.settings.article_excludes
