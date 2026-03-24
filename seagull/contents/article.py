from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from seagull.contents.content import Content, ObjectStatus
from seagull.contents.taxonomies import Author, Category, Tag

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Self

    from seagull.contents.taxonomies import Taxonomy
    from seagull.context import Context
    from seagull.settings import Settings


def taxonomy_parser[T: Taxonomy](  # noqa: PLR0913
    raw_value: str | list,
    taxon_class: type[T],
    settings: Settings,
    context: Context,
    target_lang: str,
    *,
    multiple: bool = False,
) -> T | list[T]:
    """Convert a raw metadata value into a taxon (or list of taxa).

    We try to retrieve it from the context.

    :param raw_value: Raw value to convert If `self.multiple` is `True`, the value is
    converted into a list. If the value contains semicolons, it is split on semicolons;
    otherwise, it is split on commas. This allows you to write author lists in either
    "Jane Doe, John Doe" or "Doe, Jane; Doe, John" format.
    :param taxon_class: `Taxonomy` subclass to create upon processing.
    :param settings: Seagull settings.
    :param context: Shared context.
    :param target_lang: Lang of the article.
    :param multiple: If `True`, parse into multiple seagull objects.
    :return: A single taxon, or a list of taxa.
    """
    # If we don't already have a list
    values = raw_value
    if isinstance(raw_value, str):
        # Split the value if we are parsing multiple taxa
        if multiple:
            separator = ";" if ";" in raw_value else ","
            values = raw_value.split(separator)
        # Otherwise, assume a single taxon
        else:
            values = [raw_value]
    # Convert the values into taxa
    taxa = []
    for v in values:
        value = v.strip()
        # Skip empty values
        if not value:
            continue
        taxon = context.get_or_new_taxon(
            taxon_class,
            value,
            target_lang,
            settings=settings,
            title=value,
            lang=target_lang,
        )
        taxa.append(taxon)
    # If we were parsing a single taxon, return it instead of the list
    return taxa if multiple else taxa[0]


@dataclass
class Article(Content):
    """A seagull article object."""

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        "date",
        "base_path",
        "category",
        "authors",
        *Content.MANDATORY_FIELDS,
    )

    date: datetime | None = field(default=None, compare=False, repr=False)
    """Publication date for the article."""
    category: Category | None = field(default=None, compare=False, repr=False)
    """Category of the article."""
    tags: list[Tag] = field(default_factory=list, compare=False, repr=False)
    """List of tags."""
    authors: list[Author] = field(default_factory=list, compare=False, repr=False)
    """One or more authors."""

    def __post_init__(self) -> None:
        super().__post_init__()
        # If the article is published, add it to its taxonomies
        if self.status == ObjectStatus.PUBLISHED:
            self.category.articles.append(self)
            for tag in self.tags:
                tag.articles.append(self)
            for author in self.authors:
                author.articles.append(self)

    @classmethod
    def from_parsed_metadata(
        cls,
        settings: Settings,
        context: Context,
        content: str | list,
        source_path: Path,
        base_path: Path,
        **metadata: object | str,
    ) -> Self:
        # Parse the raw publication date if applicable
        raw_date = metadata.get("date")
        if raw_date and not isinstance(raw_date, datetime):
            metadata["date"] = datetime.fromisoformat(raw_date)

        # We need to know the lang of the article to retrieve the appropriate taxonomy
        target_lang = metadata.get("lang", settings.default_lang)
        # Parse our authors
        authors = []
        if raw_author := metadata.pop("author", None):
            authors.append(
                taxonomy_parser(raw_author, Author, settings, context, target_lang)
            )
        if raw_authors := metadata.get("authors"):
            authors.extend(
                taxonomy_parser(
                    raw_authors, Author, settings, context, target_lang, multiple=True
                )
            )
        metadata["authors"] = authors
        # Parse our tags
        tags = []
        if raw_tags := metadata.pop("tags", []):
            tags.extend(
                taxonomy_parser(
                    raw_tags, Tag, settings, context, target_lang, multiple=True
                )
            )
        metadata["tags"] = tags
        # Parse our category
        if raw_category := metadata.pop("category", ""):
            metadata["category"] = taxonomy_parser(
                raw_category, Category, settings, context, target_lang
            )

        return super().from_parsed_metadata(
            settings, context, content, source_path, base_path, **metadata
        )

    def _field_setting_key(self, field_name: str) -> str:
        # Special case for the article, "draft_*" instead of "draft_article_*"
        draft_fragment = "draft" if self.status == ObjectStatus.DRAFT else "article"
        lang_fragment = "" if self.in_default_lang else "lang"
        return "_".join(f for f in (draft_fragment, lang_fragment, field_name) if f)

    @property
    def author(self) -> Author:
        """Alias for the first author in `self.authors`."""
        return self.authors[0]

    @author.setter
    def author(self, value: Author) -> None:
        self.authors[0] = value

    @property
    def locale_date(self) -> str:
        """String-formatted publication date."""
        if self.date:
            return self.date.strftime(self.settings.date_format)
        return ""
