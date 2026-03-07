from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from seagull.contents import Author, Category, Tag
from seagull.log import logger

if TYPE_CHECKING:
    from pathlib import Path

    from seagull.contents import Article, Content, Page, Static, Taxonomy


@dataclass
class Context:
    """Shared context between generators."""

    # All generated Content objects mapped by source path
    generated_content: dict[Path, Content | None] = field(default_factory=dict)
    # All added Static objects
    static_content: dict[Path, Static | None] = field(default_factory=dict)
    # Failed source paths
    failed_source_paths: list[Path] = field(default_factory=list)
    # List of static links found in the content of all SeagullObject objects
    static_links: set[Path] = field(default_factory=set)
    # Per taxonomy type lists of taxonomies
    taxonomies: dict[type[Taxonomy], list[Taxonomy]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # FIXME replace with cached properties
    # All articles
    all_articles: list[Article] = field(default_factory=list)
    # Hidden articles
    hidden_articles: list[Article] = field(default_factory=list)
    # Draft articles
    drafts: list[Article] = field(default_factory=list)
    # All articles
    all_pages: list[Page] = field(default_factory=list)
    # Hidden articles
    hidden_pages: list[Page] = field(default_factory=list)
    # Draft articles
    draft_pages: list[Page] = field(default_factory=list)

    @property
    def authors(self) -> list[Author]:
        """Shorthand for `taxonomies[Author]`."""
        return cast("list[Author]", self.taxonomies.get(Author, []))

    @property
    def tags(self) -> list[Tag]:
        """Shorthand for `taxonomies[Tags]`."""
        return cast("list[Tag]", self.taxonomies.get(Tag, []))

    @property
    def categories(self) -> list[Category]:
        """Shorthand for `taxonomies[Category]`."""
        return cast("list[Category]", self.taxonomies.get(Category, []))

    @property
    def base_jinja_context(self) -> dict[str, Any]:
        """Base context dictionary for Jinja templates rendering.

        The `all_articles` key always contains the full list of articles, while
        `articles` may be overridden to contain a subset of articles. For instance if
        we are rendering a taxonomy page, `articles` contains the list of articles in
        the taxonomy.
        """
        return {
            "all_articles": self.all_articles,
            "articles": self.all_articles,
            "dates": None,  # TODO
            "hidden_articles": self.hidden_articles,
            "drafts": self.drafts,
            "period_archives": None,  # TODO
            "authors": self.authors,
            "categories": self.categories,
            "tags": self.tags,
            "pages": self.all_pages,
            "hidden_pages": self.hidden_pages,
            "draft_pages": self.draft_pages,
        }

    # TODO would be great to be able to query by slug. We could try first by slug,
    #  returning the appropriate translation, and if it doesn't find with a slug, try
    #  the name of the category. It would be great to be able to do the same for
    #  metadata in articles and pages
    def taxa_by_name[T: Taxonomy](self, name: str) -> tuple[type[T], list[T]]:
        """Retrieve a list of taxonomies of a given type by name (case-insensitive).

        :param name: Name of the taxon.
        :return: The taxon class, and its list in `self.taxonomies`, if it exists.
        :raise KeyError: If there is no such taxonomy.
        """
        name = name.lower()
        for taxon_class, taxa in self.taxonomies.items():
            class_name = taxon_class.__name__.lower()
            if name == class_name:
                return taxon_class, taxa
        raise KeyError(name)

    def get_or_new_taxon[T: Taxonomy](
        self, taxon_class: type[T], name: str, **kwargs: Any
    ) -> T:
        """Retrieve a taxonomy object from its name.

        If it doesn't already exist, it is created and stored in
        `self.taxonomies[taxon_class]`.

        :param taxon_class: `Taxonomy` subclass.
        :param name: Name of the taxonomy to look for.
        :param kwargs: Other metadata attributes for the taxon if it needs to be
        created.
        :return: A taxonomy object.
        """
        # We look for an existing taxon in the appropriate list of existing taxa
        taxon_list = self.taxonomies[taxon_class]
        for taxon in taxon_list:
            if taxon.name == name:
                return taxon
        # If we're here, it means we have a new taxon, so we create it
        logger.debug(f"Creating a new '{taxon_class.__name__}' named '{name}'.")
        taxon = taxon_class(title=name, **kwargs)
        # We add it to our list of taxa
        taxon_list.append(taxon)
        return taxon
