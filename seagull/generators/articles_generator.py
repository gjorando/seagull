from typing import TYPE_CHECKING

from seagull.contents import Article
from seagull.generators.pages_generator import PagesGenerator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class ArticlesGenerator[T: Article](PagesGenerator):
    """Generate article pages."""

    content_class: type[T] = Article

    def _context_list_from_status(self, status: str) -> list[T]:
        match status:
            case "published":
                return self.context.all_articles
            case "hidden":
                return self.context.hidden_articles
            case "draft":
                return self.context.drafts
        raise AttributeError(status)

    def generate_context(self) -> None:
        super().generate_context()

        # Now, we process taxonomies
        # Only original published articles are added to a taxonomy
        obj: T
        for obj in self.original_content:
            if obj.status != "published":
                continue
            # FIXME maybe move this elsewhere? I would need an ORM at this point idk
            obj.category.articles.append(obj)
            for tag in obj.tags:
                tag.articles.append(obj)
            for author in obj.authors:
                author.articles.append(obj)

        # Sort taxonomies
        for taxon_class, taxon_list in self.context.taxonomies.items():
            order_by_setting_key = f"{taxon_class.__name__.lower()}_order_by"
            sort_key, reverse = getattr(
                self.settings, order_by_setting_key, (lambda o: o.name, False)
            )
            taxon_list.sort(key=sort_key, reverse=reverse)

        # TODO archives

    @property
    def valid_paths(self) -> Iterable[Path]:
        return self.settings.article_paths

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return self.settings.article_excludes
