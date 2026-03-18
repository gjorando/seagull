from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, ClassVar, Self

from seagull.contents.composable_classes import (
    ArticlesContainer,
    HasStatus,
    ObjectStatus,
)
from seagull.contents.seagull_object import SeagullObject
from seagull.filter_parser import FilterValidation

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from seagull.contents.article import Article
    from seagull.context import Context
    from seagull.settings import Settings


@dataclass
class Taxonomy(ArticlesContainer, HasStatus, SeagullObject):
    """Base class for taxonomy objects.

    A taxonomy object is an object which stores a list of articles.
    """

    ALLOWED_STATUSES: ClassVar[tuple[ObjectStatus, ...]] = (
        ObjectStatus.PUBLISHED,
        ObjectStatus.HIDDEN,
    )
    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        "title",
        "lang",
        "template",
        *SeagullObject.MANDATORY_FIELDS,
    )

    @property
    def name(self) -> str:
        """Alias for `title` attribute."""
        return self.title

    @name.setter
    def name(self, value: str) -> None:
        self.title = value


@dataclass
class Category(Taxonomy):
    """Each article has a unique category."""


@dataclass
class Author(Taxonomy):
    """Each article is written by at least one author."""


@dataclass
class Tag(Taxonomy):
    """Each article can optionally have tags."""

    filter: Callable[[Article, Self], bool] | None = field(
        default=None, compare=False, repr=False
    )
    """Optional filter function for the articles.

    If a tag has a filter, it will be used to add articles that pass that filter to the
    taxonomy. It can be seen as a filtered view on all generated articles.

    Articles that manually add the tag will still be in the tag's list of articles.
    """

    @classmethod
    def from_parsed_metadata(
        cls,
        settings: Settings,
        context: Context,
        content: str,
        source_path: Path,
        base_path: Path,
        **metadata: object | str,
    ) -> Self:
        # We convert the filter into a callable
        # TODO allow a specifier for a function that was created in, say, the settings
        if (raw_filter := metadata.get("filter")) and isinstance(raw_filter, str):
            metadata["filter"] = FilterValidation(raw_filter)
        return super().from_parsed_metadata(
            settings, context, content, source_path, base_path, **metadata
        )

    def filter_and_update(self, articles: list[Article]) -> None:
        """Apply the filter to the articles.

        It adds the articles that were not filtered out to the list of articles in the
        tag object, and adds the tag object to the tag list of these articles (if the
        tag is not a hidden tag).

        :param articles: List of articles to filter.
        """
        # No-op if the tag doesn't have a filter
        if not self.filter:
            return
        for article in filter(partial(self.filter, tag=self), articles):
            if article not in self.articles:
                self.articles.append(article)
            if self not in article.tags and self.status == ObjectStatus.PUBLISHED:
                article.tags.append(self)
