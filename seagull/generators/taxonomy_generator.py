from typing import TYPE_CHECKING

from seagull.contents import Taxonomy
from seagull.generators.generator import Generator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from seagull.context import Context
    from seagull.settings import Settings


class TaxonomyGenerator[T: Taxonomy](Generator):
    """A special generator class for pre-processing taxonomies."""

    def __init__(self, settings: Settings, context: Context, content_class: type[T]):
        """
        :param content_class: The actual taxonomy that the generator creates.
        """
        super().__init__(settings, context)
        self._content_class = content_class

    def link_translations(self) -> None:
        # Before linking translations, we need to update the generated content with
        # taxonomies that were created by the article generator, and that are not empty
        for obj in self.context.taxonomies[self.content_class]:
            if obj not in self.all_content and obj.articles:
                self.all_content.append(obj)
        super().link_translations()

    @property
    def content_class(self) -> type[T]:
        """Type of object created by the generator."""
        return self._content_class

    @property
    def base_path(self) -> Path:
        return self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return getattr(self.settings, f"{self.content_class.__name__.lower()}_paths")

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return getattr(self.settings, f"{self.content_class.__name__.lower()}_excludes")
