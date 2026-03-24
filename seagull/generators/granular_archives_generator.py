from datetime import date
from itertools import groupby, product
import logging
from operator import attrgetter
from typing import ClassVar

from seagull.contents import GranularArchive
from seagull.contents.granular_archive import ArchiveGranularity
from seagull.exceptions import SeagullError
from seagull.generators.direct_templates_generator import DirectTemplatesGenerator
from seagull.log import logger


class GranularArchivesGenerator[T: GranularArchive](DirectTemplatesGenerator):
    """Generator for the granular archives."""

    content_class: type[T] = GranularArchive

    _GETTERS: ClassVar[dict[ArchiveGranularity, attrgetter]] = {
        ArchiveGranularity.YEAR: attrgetter("date.year"),
        ArchiveGranularity.MONTH: attrgetter("date.year", "date.month"),
        ArchiveGranularity.DAY: attrgetter("date.year", "date.month", "date.day"),
    }

    def _granularity_is_enabled(
        self, granularity: ArchiveGranularity, *, is_default_lang: bool
    ) -> bool:
        """Test if a granularity should be generated.

        :param granularity: Granularity to check.
        :param is_default_lang: Whether we're in the default lang.
        :return: Whether the granularity is enabled in the settings.
        """
        setting_key = (
            f"{granularity.value}_archive_{'' if is_default_lang else 'lang_'}save_as"
        )
        return getattr(self.settings, setting_key, None) is not None

    def _create_objects(self) -> list[T]:
        all_content = []
        archive_granularity: ArchiveGranularity
        for archive_granularity, archive_lang in product(
            ArchiveGranularity,
            (self.settings.default_lang, *self.settings.langs.keys()),
        ):
            # We skip a disabled granularity
            if not self._granularity_is_enabled(
                archive_granularity,
                is_default_lang=archive_lang == self.settings.default_lang,
            ):
                continue
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
                log_granularity = "/".join(str(g) for g in date_tuple)
                date_tuple = (*date_tuple, *((1,) * (3 - len(date_tuple))))
                try:
                    obj = self.content_class(
                        settings=self.settings,
                        lang=archive_lang,
                        date=date(*date_tuple),
                        granularity=archive_granularity,
                        articles=list(period_articles),
                    )
                except SeagullError:
                    logger.exception(
                        f"Couldn't process the granular archive"
                        f" for the {log_granularity} period.",
                        exc_info=logger.level == logging.DEBUG,
                    )
                    continue
                all_content.append(obj)
        return all_content
