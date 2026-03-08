from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from seagull.contents.seagull_object import SeagullObject

if TYPE_CHECKING:
    from seagull.contents.article import Article


@dataclass(repr=False)
class Taxonomy(SeagullObject):
    """Base class for taxonomy objects.

    A taxonomy object is an object which is used as an attribute for content objects.
    """

    articles: list[Article] = field(default_factory=list)

    @property
    def jinja_context(self) -> dict[str, Any]:
        return super().jinja_context | {
            "articles": self.articles,
            "dates": None,  # TODO
        }

    @property
    def name(self) -> str:
        """Alias for `title` attribute."""
        return self.title

    @name.setter
    def name(self, value: str) -> None:
        self.title = value
