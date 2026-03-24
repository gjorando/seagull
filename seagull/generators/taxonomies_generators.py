from typing import TYPE_CHECKING

from seagull.contents import Author, Category, Tag, Taxonomy
from seagull.generators.generator import Generator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class TaxonomiesGenerator[T: Taxonomy](Generator):
    """A special generator class for pre-processing taxonomies."""

    content_class: type[T] = Taxonomy

    def link_translations(self) -> None:
        # Before linking translations, we need to update the generated content with
        # taxonomies that were created by the articles generator
        for obj in self.context.taxonomies.get(self.content_class, []):
            if obj not in self.all_content:
                self.all_content.append(obj)
        super().link_translations()

    @property
    def base_path(self) -> Path:
        return self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return getattr(self.settings, f"{self.content_class.__name__.lower()}_paths")

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return getattr(self.settings, f"{self.content_class.__name__.lower()}_excludes")


class TagsGenerator[T: Tag](TaxonomiesGenerator):
    """The taxonomy generator for tags handles optional filters as well."""

    content_class: type[T] = Tag

    def link_translations(self) -> None:
        # Perform the filtering
        for tag in self.all_content:
            tag.filter_and_update(self.context.articles)
        # No need to worry about tags created by articles as they cannot have a filter
        super().link_translations()


class CategoriesGenerator[T: Category](TaxonomiesGenerator):
    """Categories generator."""

    content_class: type[T] = Category


class AuthorsGenerator[T: Author](TaxonomiesGenerator):
    """Authors generator."""

    content_class: type[T] = Author
