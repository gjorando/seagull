import contextlib
import gettext
import locale
from pathlib import Path
from typing import TYPE_CHECKING, Self

from attrs import AttrsInstance, Converter, define, field
from babel.dates import format_date, format_datetime
from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PrefixLoader,
    TemplateNotFound,
)

from seagull.logging import logger
from seagull.utils import (
    JinjaRenderable,
    path_repr_func,
    resolve_theme_path,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from seagull.objects import Content
    from seagull.typeshed import StrPath

_BASE_ENVIRONMENT_SETTINGS = {
    "extensions": ["jinja2.ext.i18n"],
    "trim_blocks": True,
    "lstrip_blocks": True,
}
"""Base settings for `_create_environment`."""


def strftime_jinja_filter(
    date: datetime,
    *,
    date_format: str = "medium",
    strip_time: bool = False,
    locale_: str = "",
) -> str:
    """A locale aware datetime-formatter for Jinja.

    :param date: `datetime` object to format.
    :param date_format:
    [LDML](https://unicode.org/reports/tr35/tr35-dates.html#Date_Format_Patterns) format
    string, or "short", "medium", "long", or "full" (Babel presets).
    :param strip_time: Whether to only display the date.
    :param locale_: Locale to use. If empty, it uses the currently defined locale for
    `LC_TIME`.
    :return: Formatted `datetime` using `strftime`.
    """
    locale_ = locale_ or locale.setlocale(locale.LC_TIME)
    if strip_time:
        return format_date(date.date(), date_format, locale=locale_)
    return format_datetime(date, date_format, locale=locale_)


def _create_environment(templates_path: StrPath, **kwargs: object) -> Environment:
    """Create a `jinja2.Environment` object for the theme.

    :param templates_path: Path to the templates' directory.
    :param kwargs: Environment settings. They are merged with
    `_BASE_ENVIRONMENT_SETTINGS`.
    :return: A new `Environment` object.
    """
    loader = ChoiceLoader(
        [
            # Default loader: templates are searched for in the theme templates
            FileSystemLoader(templates_path),
            # Prefix loader: templates are searched for in the theme templates,
            # using the !theme prefix, or in the simple template, using the !simple
            # prefix
            PrefixLoader(
                {
                    "!theme": FileSystemLoader(templates_path),
                    "!simple": FileSystemLoader(
                        resolve_theme_path("simple") / "templates"
                    ),
                }
            ),
        ]
    )
    return Environment(loader=loader, **(_BASE_ENVIRONMENT_SETTINGS | kwargs))


def _jinja_environment_converter(
    value: Environment | dict[str, object], instance: AttrsInstance
) -> Environment:
    """Convert a dictionary of settings to a `jinja2.Environment`.

    :param value: Either a `jinja2.Environment` or a `dict` of settings.
    :return: `value` if it is already a `jinja2.Environment`, or a new instance
    with its settings set using `_create_environment`.
    """
    instance: Theme
    # If the value isn't a Jinja environment, we create it
    if isinstance(value, Environment):
        return value
    return _create_environment(instance.templates_path, **value)


@define
class Theme(JinjaRenderable):
    """Object representation of a Seagull theme."""

    name: str
    """Name of the theme."""
    path: Path = field(converter=Path, repr=path_repr_func())
    """Path of the theme."""
    lang: str = "en"
    """Default lang of the theme"""
    jinja: Environment = field(
        converter=Converter(_jinja_environment_converter, takes_self=True)
    )
    """Jinja environment."""
    _cached_translations: dict[str, gettext.NullTranslations] = field(
        factory=dict, init=False, repr=False
    )
    """Cached `gettext` translations."""

    @jinja.default
    def _attrs_default_jinja(self) -> Environment:
        return _create_environment(self.templates_path)

    @classmethod
    def load(cls, path_or_name: Path | str) -> Self:
        """Load a theme from its name or path.

        :param path_or_name: Path to the theme directory, or name of an installed theme.
        :return: Loaded theme object.
        """
        # TODO allow loading directly from a config dictionary
        theme_path = resolve_theme_path(path_or_name)
        return cls(name=theme_path.name, path=theme_path)

    def __attrs_post_init__(self) -> None:
        # TODO improve default filter recording
        self.jinja.filters["strftime"] = strftime_jinja_filter
        # Warn if i18n isn't available
        if not getattr(self.jinja, "install_gettext_translations", None):
            logger.warning("Running without jinja2 internationalization.")

    def select_translation(self, lang: str) -> None:
        """Select the appropriate translation for the Jinja environment.

        Translations are cached in `Theme._cached_translations`.

        :param lang: Lang to use.
        """
        # no-op if i18n isn't available
        if not (
            (
                install_gettext_translations := getattr(
                    self.jinja, "install_gettext_translations", None
                )
            )
            and callable(install_gettext_translations)
        ):
            return
        install_gettext_translations: Callable

        # Try retrieving the translation for the given lang
        # We will fall back to the default translation
        translations = gettext.NullTranslations()
        try:
            # Try using the cached one
            if lang in self._cached_translations:
                translations = self._cached_translations[lang]
            # Otherwise, create it
            else:
                translations = gettext.translation(
                    domain="messages",
                    localedir=self.translations_path,
                    languages=[lang],
                )
                logger.debug(f"Loaded '{lang}' translations for the theme.")
        except OSError:
            # We ignore this error for the theme lang
            if lang != self.lang:
                logger.warning(
                    f"The theme doesn't have a translation for the '{lang}' language."
                )
        # Cache our translation if it's not already done
        self._cached_translations.setdefault(lang, translations)
        install_gettext_translations(translations, newstyle=True)

    def render(
        self,
        obj: Content,
        template_overrides: list[Path] | None = None,
        jinja_context: dict[str, object] | None = None,
    ) -> str:
        """Render a content object using the theme templates.

        :param obj: Object to render.
        :param template_overrides: Optional template overrides.
        :param jinja_context: Rendering context dictionary.
        :return: Rendered HTML.
        :raise TemplateNotFound: if `obj.template` is not a valid template.
        """
        self.select_translation(obj.lang)
        template = None
        # Try to load a template override first
        if template_overrides:
            for ext in ["jinja2", "html", "htm"]:
                with contextlib.suppress(TemplateNotFound):
                    template = FileSystemLoader(template_overrides).load(
                        self.jinja, f"{obj.template}.{ext}", globals=self.jinja.globals
                    )
                if template:
                    break
        # Otherwise, look for a theme template
        if not template:
            template = self.jinja.select_template(
                [f"{obj.template}.{ext}" for ext in ["jinja2", "html", "htm"]]
            )
        return template.render(
            # The theme's rendering context
            self.jinja_context
            # Base rendering context
            | (jinja_context or {})
            # Object's rendering context
            | obj.jinja_context
        )

    @property
    def templates_path(self) -> Path:
        """Directory that stores the theme's templates."""
        return self.path / "templates"

    @property
    def translations_path(self) -> Path:
        """Directory where the theme's translations reside."""
        return self.path / "translations"

    @property
    def static_path(self) -> Path:
        """Directory where the theme's static files are located."""
        return self.path / "static"

    @property
    def jinja_context(self) -> dict[str, object]:
        return {
            # FIXME as_dict method instead
            "theme": self,
        }
