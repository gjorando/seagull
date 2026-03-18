from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar

from seagull.exceptions import InvalidObjectError, SkippedFileError

if TYPE_CHECKING:
    from seagull.contents.article import Article


class ObjectStatus(StrEnum):
    """Status of a seagull object."""

    PUBLISHED = auto()
    HIDDEN = auto()
    DRAFT = auto()
    SKIP = auto()


@dataclass
class HasStatus:
    """Objects that have a publication status."""

    ALLOWED_STATUSES: ClassVar[tuple[ObjectStatus, ...]] = tuple(
        status for status in ObjectStatus
    )
    """Allowed status for the object."""

    status: ObjectStatus = field(
        default=ObjectStatus.PUBLISHED, compare=False, repr=False
    )
    """Publication status of the content."""

    def __post_init__(self) -> None:
        # Parse the status, raising an InvalidObjectError if it's not a valid status
        try:
            self.status = ObjectStatus(self.status)
        except ValueError as e:
            raise InvalidObjectError(f"'{self.status}': not a valid status.") from e
        if self.status not in self.ALLOWED_STATUSES:
            raise InvalidObjectError(
                f"'{self.status}': not a valid status for "
                f"objects of type '{type(self).__name__}'."
            )
        # We skip objects with a skip status
        if self.status == ObjectStatus.SKIP:
            raise SkippedFileError

        if post_init := getattr(super(), "__post_init__", None):
            post_init()


@dataclass
class ArticlesContainer:
    """Objects that contain a list of articles."""

    articles: list[Article] = field(default_factory=list, compare=False, repr=False)
    """List of articles in the object."""

    @property
    def jinja_context(self) -> dict[str, Any]:
        return getattr(super(), "jinja_context", {}) | {
            # This allows to override the base context's articles
            "articles": self.articles,
        }
