from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

from seagull.contents.seagull_object import SeagullObject

if TYPE_CHECKING:
    from seagull.contents import Article


class FeedType(StrEnum):
    """Type of feed."""

    RSS = auto()
    ATOM = auto()


@dataclass
class Feed(SeagullObject):
    """An object describing feeds."""

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        *SeagullObject.MANDATORY_FIELDS,
        "feed_type",
        "lang",
        "articles",
    )

    feed_type: FeedType = field(default=FeedType.ATOM, compare=False, repr=False)
    """Type of feed generated."""
    feed_category: str = field(default="", compare=False, repr=False)
    """Category of feed (either "all", empty, or a taxonomy name)."""
    articles: list[Article] = field(default_factory=list, compare=False, repr=False)
    """List of articles associated to the feed."""

    def __post_init__(self) -> None:
        super().__post_init__()
        # Restrict the number of articles (if None, all articles are kept in the feed)
        self.articles = self.articles[: self.settings.feed_max_items]

    def _field_setting_key(self, field_name: str) -> str:
        # The title will be the first fragment, either "all", a taxonomy name, or an
        # empty string
        lang_fragment = "" if self.in_default_lang else "lang"
        return "_".join(
            f for f in (self.feed_category, "feed", lang_fragment, field_name) if f
        )

    @property
    def _url(self) -> str:
        return urljoin(self.settings.feed_domain, super()._url)
