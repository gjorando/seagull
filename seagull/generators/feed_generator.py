import logging
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING

from seagull.contents import Feed
from seagull.exceptions import SeagullError, SkippedFileError
from seagull.generators.generator import Generator, GeneratorType
from seagull.log import logger
from seagull.writers import FeedWriter

if TYPE_CHECKING:
    from collections.abc import Iterable

    from seagull.contents import Article


class FeedGenerator[T: Feed](Generator):
    """Generator for ATOM and RSS feeds."""

    content_class: type[T] = Feed
    generator_type: GeneratorType = GeneratorType.POST_CONTENT

    def _get_writer(self, obj: T) -> FeedWriter:
        del obj  # Unused argument
        # We always use a FeedWriter for feeds
        return FeedWriter(self.settings)

    def _create_objects(self) -> list[T]:
        all_content: list[T] = []
        # For each type of feed that's been enabled
        for feed_type in self.settings.feed_types:
            # List of [feed title, feed slug, feed category, feed lang, feed articles]
            per_feed_articles: list[tuple[str, str, str, str, list[Article]]] = [
                # The all feed contains all published articles in all languages
                (
                    "",
                    "all",
                    "all",
                    self.settings.default_lang,
                    list(self.context.published_articles),
                ),
            ]
            # Feeds of all published articles for each language
            per_feed_articles.extend(
                (
                    "",
                    "per-lang",
                    "",
                    feed_lang,
                    list(
                        filter(
                            lambda o: o.lang == feed_lang,
                            self.context.published_articles,
                        )
                    ),
                )
                for feed_lang in (
                    self.settings.default_lang,
                    *self.settings.langs.keys(),
                )
            )
            # Taxonomy feeds for each language
            per_feed_articles.extend(
                (
                    taxon.name,
                    taxon.slug,
                    taxon_class.__name__.lower(),
                    taxon.lang,
                    taxon.articles,
                )
                for taxon_class, taxon_list in self.context.taxonomies.items()
                for taxon in taxon_list
                if taxon.articles
            )
            # For each taxonomy + all published articles, create one feed per lang
            for title, slug, category, lang, articles in per_feed_articles:
                # We need to use
                sorted_articles = sorted(articles, key=attrgetter("date"), reverse=True)
                try:
                    obj = self.content_class(
                        title=title,
                        slug=slug,
                        settings=self.settings,
                        lang=lang,
                        articles=sorted_articles,
                        feed_type=feed_type,
                        feed_category=category,
                    )
                except SkippedFileError:
                    continue
                except SeagullError:
                    logger.exception(
                        f"Couldn't process the {feed_type} feed '{slug}'"
                        f"{f' ({title})' if title else ''} for the {lang} lang.",
                        exc_info=logger.level == logging.DEBUG,
                    )
                    continue
                all_content.append(obj)
        return all_content

    def valid_paths(self) -> Iterable[Path]:
        """Unused property."""
        return []

    @property
    def excluded_paths(self) -> Iterable[Path]:
        """Unused property."""
        return []

    @property
    def base_path(self) -> Path:
        """Unused property."""
        return Path()
