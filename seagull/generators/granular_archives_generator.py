import logging
from datetime import date
from itertools import groupby, product
from operator import attrgetter
from typing import TYPE_CHECKING, ClassVar

from seagull.contents import GranularArchive
from seagull.contents.granular_archive import ArchiveGranularity
from seagull.exceptions import SeagullError, SkippedFileError
from seagull.generators.direct_templates_generator import DirectTemplatesGenerator
from seagull.log import logger

if TYPE_CHECKING:
    from seagull.context import Context
    from seagull.settings import Settings


class GranularArchivesGenerator[T: GranularArchive](DirectTemplatesGenerator):
    """Generator for the granular archives."""

    content_class: type[T] = GranularArchive

    _GETTERS: ClassVar[dict[ArchiveGranularity, attrgetter]] = {
        ArchiveGranularity.YEAR: attrgetter("date.year"),
        ArchiveGranularity.MONTH: attrgetter("date.year", "date.month"),
        ArchiveGranularity.DAY: attrgetter("date.year", "date.month", "date.day"),
    }

    def __init__(self, settings: Settings, context: Context):
        super().__init__(settings, context)

    def _create_objects(self) -> list[T]:
        all_content = []
        # TODO pagination
        archive_granularity: ArchiveGranularity
        for archive_granularity, archive_lang in product(
            ArchiveGranularity,
            (self.settings.default_lang, *self.settings.langs.keys()),
        ):
            # Get the published articles for archive_lang
            articles = list(
                filter(
                    lambda o: o.lang == archive_lang, self.context.published_articles
                )
            )
            # Sort them by reverse chronological order
            articles.sort(key=attrgetter("date"), reverse=True)
            for granularity, period_articles in groupby(
                articles, self._GETTERS[archive_granularity]
            ):
                # Complete the granularity tuple with default values for month and day
                # if missing
                date_tuple = (
                    granularity if isinstance(granularity, tuple) else (granularity,)
                )
                date_tuple = (*date_tuple, *((1,) * (3 - len(date_tuple))))
                try:
                    obj = self.content_class(
                        settings=self.settings,
                        lang=archive_lang,
                        date=date(*date_tuple),
                        granularity=archive_granularity,
                        articles=list(period_articles),
                    )
                except SkippedFileError:
                    pass
                except SeagullError:
                    logger.exception(
                        f"Couldn't process period archive {'FIXME'}.",
                        exc_info=logger.level == logging.DEBUG,
                    )
                    continue
                all_content.append(obj)
        return all_content
