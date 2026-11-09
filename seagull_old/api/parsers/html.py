import gettext
import locale
from pathlib import Path
from typing import ClassVar, cast

from attrs import define, field

from seagull.api.objects import Content
from seagull.api.theme import Theme
from seagull.utils import temporary_locale

from .parser import Parser


@define(kw_only=True, slots=False)
class HTMLParser[T: Content](Parser):
    """A class that reads and writes HTML data."""

    file_extensions: ClassVar[tuple[str, ...]] = ("html", "htm")

    theme: Theme = field(default="simple", converter=Theme.load)
    """Theme to use."""
    template_overrides: list[Path] = field(
        factory=list, converter=lambda v: [Path(x) for x in v]
    )
    """User overrides for the theme's templates."""
    locale: str = field(
        factory=lambda: locale.setlocale(locale.LC_ALL),
    )

    def _loads(self, text: str) -> dict:
        # TODO
        raise NotImplementedError

    def dumps(self, obj: T, /, **kwargs: object) -> str:
        """
        :param obj: Object to convert.
        :param kwargs: Base jinja context with which merge the object's jinja context.
        """
        if not isinstance(obj, Content):
            raise TypeError(
                f"'{type(self).__name__}' is only meant to write content objects."
            )

        # FIXME store lang -> locale dict
        with temporary_locale(self.locale):
            return self.theme.render(
                obj,
                template_overrides=self.template_overrides,
                jinja_context=kwargs,
            )
