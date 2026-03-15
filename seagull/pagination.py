from collections.abc import Sequence
from math import ceil
from pathlib import Path
from typing import TYPE_CHECKING, Self, overload

if TYPE_CHECKING:
    from typing import Any

    from seagull.contents import Article, SeagullObject


# FIXME maybe PaginationElement should be a SeagullObject?
class PaginationElement[T: Article](Sequence[T]):
    """A single page for a `Paginator`."""

    def __init__(self, articles: list[T], paginator: Paginator):
        """
        :param articles: Articles in the page.
        :param paginator: The paginator from which the page comes from.
        """
        self.articles = articles
        self.paginator = paginator
        self.obj = self.paginator.obj

    def _format_paginated_field(self, field_name: str) -> str | None:
        """Retrieve the actual `save_as` or `url` value for the page.

        :param field_name: Name of the field to format.
        :return: Formatted value of the field based on the pagination patterns. If no
        rule could be applied, `None` is returned.
        """
        # Try to find a suitable pagination rule
        pagination_rule = None
        for pattern in self.obj.settings.pagination_patterns:
            # min_page == -1 is the rule for the last page
            if pattern.min_page < 0:
                # We pick this rule if we have a previous page, but no next page
                if self.previous_page and not self.next_page:
                    pagination_rule = pattern
                    break
            elif pattern.min_page <= self.number:
                # We do not break because the uppermost min_page value is selected
                # (pagination_patterns were sorted by min_page in the settings)
                pagination_rule = pattern
        pattern = getattr(pagination_rule, field_name, None)
        if not pattern:
            return None
        return pattern.format(
            number=self.number, **self.paginator.paginated_field_context
        )

    @property
    def jinja_context(self) -> dict[str, Any]:
        """Context dictionary for pagination."""
        # Update the relative URL to reflect the 'siteurl' context key
        if not self.obj.settings.relative_urls:
            relative_url = self.obj.settings.siteurl
        else:
            relative_url = str(Path(".").relative_to(self.save_as.parent, walk_up=True))
        return {
            "articles_paginator": self.paginator,
            "articles_page": self,
            "save_as": self.save_as,
            "url": self.url,
            "siteurl": relative_url,
        }

    @property
    def number(self) -> int:
        """1-indexed page number.

        :raise ValueError: If the page is not an element in `self.paginator`.
        """
        return self.page_id + 1

    @property
    def page_id(self) -> int:
        """0-indexed page number.

        :raise ValueError: If the page is not an element in `self.paginator`.
        """
        return self.paginator.index(self)

    @property
    def has_other_pages(self) -> bool:
        """Whether there are other pages."""
        return len(self.paginator) > 1

    @property
    def previous_page(self) -> Self | None:
        """Get the previous page, or `None` if there is no previous page."""
        return self.paginator[self.page_id - 1] if self.page_id > 0 else None

    @property
    def next_page(self) -> Self | None:
        """Get the next page, or `None` if there is no next page."""
        return (
            self.paginator[self.page_id + 1]
            if self.page_id + 1 < len(self.paginator)
            else None
        )

    @property
    def save_as(self) -> Path:
        return Path(self._format_paginated_field("save_as"))

    @property
    def url(self) -> str:
        return self._format_paginated_field("url")

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...

    def __getitem__(self, index):
        """Get the n-th article in the page."""
        return self.articles[index]

    def __len__(self) -> int:
        """Number of articles in the page."""
        return len(self.articles)

    def __repr__(self) -> str:
        return f"<Page {self.number} of {len(self.paginator)}>"


class Paginator[T: PaginationElement](Sequence[T]):
    """A class to handle paginated lists of articles."""

    def __init__(self, obj: SeagullObject, articles: list[Article]):
        """Initialize the paginator.

        :param obj: Object that's being rendered.
        :param articles: Sequence of articles to paginate.
        """
        self.obj = obj
        self.articles = articles
        # Precompute the context for our pages' save_as and url values
        self.paginated_field_context = {
            "save_as": obj.save_as,
            "url": obj.url,
            "name": obj.save_as.stem,
            # Remove a trailing index.htm(l) if present
            "base_name": obj.save_as.parent
            if obj.save_as.name in ("index.html", "index.htm")
            else obj.save_as,
            "extension": obj.save_as.suffix,
        }
        # Number of items per page
        self.per_page = (
            self.obj.settings.paginated_templates[self.obj.template]
            or self.obj.settings.default_pagination
        )
        # Minimum number of articles on the last page
        self.orphans = self.obj.settings.default_orphans
        # If per_page is 0, the paginator has a single page w/ the full list of articles
        # (This effectively disables pagination)
        if self.per_page <= 0:
            self.per_page = len(articles)
            self.orphans = 0

        self._pages: list[PaginationElement] = []
        # Deduce the number of pages we need to create
        num_pages = ceil(max(1, len(self.articles) - self.orphans) / self.per_page)
        # Create our pages
        for i in range(num_pages):
            # Compute our range of articles for the page
            start = i * self.per_page
            stop = start + self.per_page
            if stop + self.orphans >= len(self.articles):
                stop = len(self.articles)
            self._pages.append(
                PaginationElement(articles=self.articles[start:stop], paginator=self)
            )

    @property
    def articles_count(self) -> int:
        """Total number of articles."""
        return len(self.articles)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...

    def __getitem__(self, index):
        """Retrieve a page or slice of pages.

        This method is 0-indexed.
        """
        return self._pages[index]

    def __len__(self) -> int:
        """Number of pages."""
        return len(self._pages)
