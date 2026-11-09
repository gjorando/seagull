import contextlib
from functools import partial
import gettext
import locale
from pathlib import Path
from typing import TYPE_CHECKING, Self, cast

from attrs import AttrsInstance, Converter, define, field
from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PrefixLoader,
    TemplateNotFound,
)

from seagull.api.objects import Content
from seagull.logging import logger
from seagull.utils import path_repr, resolve_theme_path, temporary_locale

if TYPE_CHECKING:
    from datetime import datetime


def strftime_jinja_filter(
    date: datetime,
    date_format: str = "",
    locale_: str = "",
    default_date_format: str = "",
) -> str:
    """A locale aware date-formatter for Jinja.

    :param date: `datetime` object to format.
    :param date_format: Format string.
    :param locale_: Locale to use. If empty, it uses the currently defined locale for
    `LC_TIME`.
    :param default_date_format: Default date format to use.
    :return: Formatted `datetime` using `strftime`.
    """
    if not date_format:
        date_format = default_date_format
    if not locale_:
        locale_ = locale.setlocale(locale.LC_TIME)
    # on OSX, encoding from LC_CTYPE determines the Unicode output
    # So make sure it's same as LC_TIME
    with temporary_locale(locale_, (locale.LC_TIME, locale.LC_CTYPE)):
        return date.strftime(date_format)


def _jinja_environment_converter(
    value: Environment | dict[str, object], instance: AttrsInstance
) -> Environment:
    instance: Theme
    # If the value isn't a Jinja environment, we create it
    if isinstance(value, Environment):
        return value
    loader = ChoiceLoader(
        [
            # Default loader: templates are searched for in the theme templates
            FileSystemLoader(instance.templates_path),
            # Prefix loader: templates are searched for in the theme templates,
            # using the !theme prefix, or in the simple template, using the !simple
            # prefix
            PrefixLoader(
                {
                    "!theme": FileSystemLoader(instance.templates_path),
                    "!simple": FileSystemLoader(
                        resolve_theme_path("simple") / "templates"
                    ),
                }
            ),
        ]
    )
    return Environment(
        loader=loader,
        **(
            {
                "extensions": ["jinja2.ext.i18n"],
                "trim_blocks": True,
                "lstrip_blocks": True,
            }
            | value
        ),
    )


@define(kw_only=True)
class Theme:
    """Object representation of a Seagull theme."""

    name: str
    """Name of the theme."""
    path: Path = field(converter=Path, repr=path_repr)
    """Path of the theme."""
    lang: str = "en"
    """Default lang of the theme"""
    jinja: Environment = field(
        factory=dict, converter=Converter(_jinja_environment_converter, takes_self=True)
    )
    """Jinja environment."""
    _cached_translations: dict[str, gettext.NullTranslations] = field(
        factory=dict, init=False, repr=False
    )
    """Cached `gettext` translations."""

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
        self.jinja.filters["strftime"] = partial(
            strftime_jinja_filter,
            default_date_format="%A %d %B %Y",
        )

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
            install_gettext_translations := getattr(
                self.jinja, "install_gettext_translations", None
            )
        ):
            return

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
        jinja_context = self._jinja_context(obj, jinja_context)
        template = None
        if template_overrides:
            for ext in ["jinja2", "html", "htm"]:
                with contextlib.suppress(TemplateNotFound):
                    template = FileSystemLoader(template_overrides).load(
                        self.jinja, f"{obj.template}.{ext}", globals=self.jinja.globals
                    )
                if template:
                    break
        if not template:
            template = self.jinja.select_template(
                [f"{obj.template}.{ext}" for ext in ["jinja2", "html", "htm"]]
            )
        return template.render(jinja_context)

    def _jinja_context(
        self, obj: Content, jinja_context: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Compute the final Jinja context dictionary.

        The following additional context variables are processed.
        * `site_root`: Path to the website's root, depending on whether we use relative
          urls.
        * `theme`: The `Theme` object.

        :param obj: Object to convert.
        :param jinja_context: Base jinja context (typically that of the `Seagull`
        object).
        :return: A rendering context dictionary for the website's templates.
        """
        site = cast("dict", jinja_context.get("site", {}))
        relative_urls = site.get("relative_urls", False)
        extra_context = {
            "site_root": obj.site_root if relative_urls else site.get("url", ""),
            # FIXME as_dict method instead
            "theme": self,
        }

        return extra_context | (jinja_context or {}) | obj.jinja_context

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
