import contextlib
from dataclasses import dataclass, field
from enum import StrEnum, auto
from itertools import product
from typing import TYPE_CHECKING, ClassVar

from jinja2 import TemplateNotFound

from seagull.contents.composable_classes import ArticlesContainer
from seagull.contents.direct_template import DirectTemplate
from seagull.exceptions import InvalidObjectError

if TYPE_CHECKING:
    from datetime import date
    from typing import Any


class ArchiveGranularity(StrEnum):
    """Granularity for a granular archive."""

    YEAR = auto()
    MONTH = auto()
    DAY = auto()


# FIXME maybe also inherit from a Taxonomy
@dataclass
class GranularArchive(ArticlesContainer, DirectTemplate):
    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        "date",
        "granularity",
        *DirectTemplate.MANDATORY_FIELDS,
    )

    date: date | None = field(default=None, compare=False, repr=False)
    """Granularity date."""
    granularity: ArchiveGranularity | None = field(
        default=None, compare=False, repr=False
    )
    """Granularity level."""

    def _field_setting_key(self, field_name: str) -> str:
        lang_fragment = "" if self.in_default_lang else "lang"
        return "_".join(
            f for f in (self.granularity, "archive", lang_fragment, field_name) if f
        )

    @property
    def _slug_source(self) -> str:
        # Build the slug from the level of granularity
        date_fragment = self.date.strftime("%Y")
        if self.granularity != ArchiveGranularity.YEAR:
            date_fragment += f"-{self.date.strftime('%m')}"
            if self.granularity == ArchiveGranularity.DAY:
                date_fragment += f"-{self.date.strftime('%d')}"
        return date_fragment

    @property
    def _template(self) -> str:
        # The template should be "period_archives", we fall back to "archives" if it
        # doesn't exist
        for template_name, ext in product(
            ("period_archives", "archives"), self.settings.template_extensions
        ):
            with contextlib.suppress(TemplateNotFound):
                # Try retrieving the template
                self.settings.jinja_env_object.get_template(template_name + ext)
                # Return it if it was found
                return template_name
        raise InvalidObjectError(f"Cannot find an template for {self}.")

    @property
    def jinja_context(self) -> dict[str, Any]:
        return super().jinja_context | {
            # FIXME we should access period_num and period from the object in a template
            "period_num": self.period_num,
            "period": self.period,
        }

    @property
    def period_num(self) -> tuple[int, ...]:
        """A tuple representing the period covered by the archive.

        :return: A tuple of the form `(year, month, day)`, as in `self.period`, except
        all values are numbers.
        """
        date_struct = self.date.timetuple()
        date_tuple = (date_struct.tm_year,)
        if self.granularity != ArchiveGranularity.YEAR:
            date_tuple = (*date_tuple, date_struct.tm_mon)
            if self.granularity == ArchiveGranularity.DAY:
                date_tuple = (*date_tuple, date_struct.tm_mday)
        return date_tuple

    @property
    def period(self) -> tuple[str, ...]:
        """A tuple representing the period covered by the archive.

        :return: A tuple of the form `(year, month, day)` that indicates the current
        time period. `year` and `day` are numbers while `month` is a string. This tuple
        only contains `year` if the time period is a given year. It contains both `year`
         and `month` if the time period is over years and months, and so on.
        """
        date_tuple = (str(self.date.year),)
        if self.granularity != ArchiveGranularity.YEAR:
            date_tuple = (*date_tuple, self.date.strftime("%B"))
            if self.granularity == ArchiveGranularity.DAY:
                date_tuple = (*date_tuple, str(self.date.day))
        return date_tuple
