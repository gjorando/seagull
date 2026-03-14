from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from seagull.contents.seagull_object import SeagullObject

if TYPE_CHECKING:
    from typing import Any

    from seagull.contents.article import Article


@dataclass
class Taxonomy(SeagullObject):
    """Base class for taxonomy objects.

    A taxonomy object is an object which is used as an attribute for articles.
    """

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        *SeagullObject.MANDATORY_FIELDS,
        "title",
        "lang",
        "template",
    )

    articles: list[Article] = field(default_factory=list, compare=False, repr=False)
    """List of articles in the taxonomy."""

    @property
    def jinja_context(self) -> dict[str, Any]:
        return super().jinja_context | {
            # This allows to overrides the base context's articles
            "articles": self.articles,
        }

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
