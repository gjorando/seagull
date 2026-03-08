import gettext
import locale
import os
import sys
from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from functools import partial
from importlib import import_module
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from inspect import getmembers
from ipaddress import IPv4Address, IPv6Address, ip_address
from itertools import batched, permutations, product
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from zoneinfo import ZoneInfo

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader

from seagull.decorators import extra_dataclass
from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Generator
    from datetime import datetime
    from types import ModuleType

    from jinja2 import BaseLoader

    from seagull.contents import Article, Author, Category, Page, SeagullObject, Tag


class Comparable[T](Protocol):
    """Protocol for annotating comparable types."""

    @abstractmethod
    def __lt__(self: T, other: T, /) -> bool: ...


def order_by_factory[T: Comparable](
    value: str,
) -> tuple[Callable[[SeagullObject], T], bool]:
    """Convert an `*_ORDER_BY` setting to a key function and `reverse` parameter.

    See [the Python documentation](https://docs.python.org/3/howto/sorting.html)
    for details about key functions.

    :return: A function that takes a seagull object and return a value for sorting; a
    boolean that tells whether to reverse the sorting order.
    """
    reverse = False
    # Special case basename: order by filename
    if value == "basename":

        def key_func(obj: SeagullObject) -> T:
            if obj.source_path:
                return obj.source_path.name
            return obj.title
    # Otherwise, sort by a given metadata key
    else:
        if value.startswith("reversed-"):
            value = value.replace("reversed-", "", 1)
            reverse = True

        def key_func(obj: SeagullObject) -> object:
            return getattr(obj, value)

    return key_func, reverse


@contextmanager
def temporary_locale(
    temp_locale: str, lc_category: int | tuple[int, ...] = locale.LC_ALL
) -> Generator[None]:
    """Context manager for running code with a temporary locale.

    Resets the locale back when exiting context.

    :param temp_locale: Temporary locale to use.
    :param lc_category: Locale category or list of locale categories that are affected.
    """
    if not isinstance(lc_category, tuple):
        lc_category = [lc_category]
    orig_locales = {lcc: locale.setlocale(lcc) for lcc in lc_category}

    # Change the desired locale categories, then enter the context manager
    for lcc in lc_category:
        locale.setlocale(lcc, temp_locale)
    yield
    # After exiting the context manager, restore the categories to their old locale
    for lcc in lc_category:
        locale.setlocale(lcc, orig_locales[lcc])


def strftime_jinja_filter(date: datetime, date_format: str, locale_: str = "") -> str:
    """A locale aware date-formatter for Jinja.

    :param date: `datetime` object to format.
    :param date_format: Format string.
    :param locale_: Locale to use. If empty, it uses the currently defined locale for
    `LC_TIME`.
    :return: Formatted `datetime` using `strftime`.
    """
    if not locale_:
        locale_ = locale.setlocale(locale.LC_TIME)
    # on OSX, encoding from LC_CTYPE determines the Unicode output
    # So make sure it's same as LC_TIME
    with temporary_locale(locale_, (locale.LC_TIME, locale.LC_CTYPE)):
        return date.strftime(date_format)


@extra_dataclass
@dataclass(kw_only=True)
class Settings:
    # Basic settings
    use_folder_as_category: bool = True
    default_category: str = "misc"
    docutils_settings: dict[str, Any] = field(default_factory=dict)
    html_parser: str = "html.parser"
    delete_output_directory: bool = False
    output_retention: list[Path] = field(default_factory=list)
    jinja_environment: dict[str, Any] | Environment = field(
        default_factory=lambda: {
            "extensions": ["jinja2.ext.i18n"],
            "trim_blocks": True,
            "lstrip_blocks": True,
        }
    )
    jinja_filters: dict[str, Callable] = field(default_factory=dict)
    ignore_files: list[str | Path] = field(default_factory=lambda: ["**/.*"])
    output_path: Path = Path("output")
    path: Path = Path(".")
    article_paths: list[Path] = field(default_factory=lambda: [Path(".")])
    article_excludes: list[Path] = field(default_factory=list)
    page_paths: list[Path] = field(default_factory=lambda: [Path("pages/")])
    page_excludes: list[Path] = field(default_factory=list)
    plugin_paths: list[Path] = field(default_factory=list)
    category_paths: list[Path] = field(default_factory=lambda: [Path("categories/")])
    category_excludes: list[Path] = field(default_factory=list)
    author_paths: list[Path] = field(default_factory=lambda: [Path("authors/")])
    author_excludes: list[Path] = field(default_factory=list)
    tag_paths: list[Path] = field(default_factory=lambda: [Path("tags/")])
    tag_excludes: list[Path] = field(default_factory=list)
    sitename: str = "A Seagull Blog"
    siteurl: str = "/"
    static_paths: list[Path] = field(default_factory=lambda: [Path("images/")])
    static_excludes: list[Path] = field(default_factory=list)
    intrasite_link_regex: str = r"{(?P<what>.*?)}"
    cache_path: Path = Path("cache")
    formatted_fields: list = field(default_factory=lambda: ["summary"])
    port: int = 8000
    bind: IPv4Address | IPv6Address = field(
        default_factory=lambda: ip_address("127.0.0.1")
    )
    seagull_class: type | str = "seagull.Seagull"

    # URL settings
    relative_urls: bool = False
    article_url: str = "{slug}.html"
    article_save_as: Path | None = Path("{slug}.html")
    article_lang_url: str = "{slug}-{lang}.html"
    article_lang_save_as: Path | None = Path("{slug}-{lang}.html")
    draft_url: str = "drafts/{slug}.html"
    draft_save_as: Path | None = Path("drafts/{slug}.html")
    draft_lang_url: str = "drafts/{slug}-{lang}.html"
    draft_lang_save_as: Path | None = Path("drafts/{slug}-{lang}.html")
    page_url: str = "pages/{slug}.html"
    page_save_as: Path | None = Path("pages/{slug}.html")
    page_lang_url: str = "pages/{slug}-{lang}.html"
    page_lang_save_as: Path | None = Path("pages/{slug}-{lang}.html")
    draft_page_url: str = "drafts/pages/{slug}.html"
    draft_page_save_as: Path | None = Path("drafts/pages/{slug}.html")
    draft_page_lang_url: str = "drafts/pages/{slug}-{lang}.html"
    draft_page_lang_save_as: Path | None = Path("drafts/pages/{slug}-{lang}.html")
    author_url: str = "author/{slug}.html"
    author_save_as: Path | None = Path("author/{slug}.html")
    category_url: str = "category/{slug}.html"
    category_save_as: Path | None = Path("category/{slug}.html")
    tag_url: str = "tag/{slug}.html"
    tag_save_as: Path | None = Path("tag/{slug}.html")
    index_url: str = "index.html"
    index_save_as: Path | None = Path("index.html")
    slugify_source: str = "title"
    slugify_settings: dict[str, Any] = field(default_factory=dict)
    author_slugify_settings: dict[str, Any] | None = None
    category_slugify_settings: dict[str, Any] | None = None
    tag_slugify_settings: dict[str, Any] | None = None

    # Time and date
    timezone: str | ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    default_date: str | None = None
    default_date_format: str = "%a %d %B %Y"
    date_formats: dict[str, str | tuple[str, str]] = field(default_factory=dict)
    locale: str | list[str] = field(
        default_factory=lambda: [locale.setlocale(locale.LC_ALL)]
    )

    # Template pages
    template_extensions: list[str] = field(default_factory=lambda: [".html"])
    direct_templates: list[str] = field(
        default_factory=lambda: [
            "index",
            "tags",
            "categories",
            "authors",
            # TODO archives
            # "archives",
        ]
    )

    # Metadata
    author: str | None = None
    default_metadata: dict[str, Any] = field(default_factory=dict)
    filename_metadata: str = r"(?P<date>\d{4}-\d{2}-\d{2}).*"
    path_metadata: str = ""
    extra_path_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Translations
    default_lang: str = "en"
    article_translation_id: str | Collection[str] | None = "slug"
    page_translation_id: str | Collection[str] | None = "slug"

    # Ordering content
    article_order_by: str | Callable[[Article], tuple[Any, bool]] = "reversed-date"
    page_order_by: str | Callable[[Page], tuple[Any, bool]] = "basename"
    author_order_by: str | Callable[[Author], tuple[Any, bool]] = "name"
    category_order_by: str | Callable[[Category], tuple[Any, bool]] = "name"
    tag_order_by: str | Callable[[Tag], tuple[Any, bool]] = "name"

    # Themes
    theme: Path | str = "simple"
    theme_lang: str = "en"
    theme_static_dir: Path = Path("theme")
    theme_static_paths: list[Path] = field(default_factory=lambda: [Path("static/")])
    theme_template_overrides: list[Path] = field(default_factory=list)
    stylesheet_url: str | None = None
    sitesubtitle: str | None = None
    menuitems: list[tuple[str, str]] = field(default_factory=list)
    display_pages_on_menu: bool = True
    display_categories_on_menu: bool = True

    # FIXME PLR0912, PLR0915
    def __post_init__(self) -> None:  # noqa: PLR0912, PLR0915
        """Parse and normalize various settings."""

        # Ensure a path-like or list of path-like uses pathlib.Path
        def ensure_paths(p: Path | str | list[Path | str]) -> Path | list[Path]:
            if isinstance(p, list):
                return [Path(v) for v in p]
            return Path(p)

        def absolute_from_base(
            p: Path | str | list[Path | str], base: Path
        ) -> Path | list[Path]:
            def _absolute_from_base(o: Path) -> Path:
                return o if o.is_absolute() else (base / o).resolve()

            p = ensure_paths(p)
            if isinstance(p, Path):
                return _absolute_from_base(p)
            return [_absolute_from_base(o) for o in p]

        def mutually_exclusive_sources(
            includes: list[Path], excludes: list[Path]
        ) -> None:
            for p in includes:
                if p not in excludes:
                    excludes.append(p)

        # Coalesce these relative paths to absolute paths relative to _working_dir,
        # which is usually the directory where the settings module is
        # All these paths are "base paths", which means they're used as a base for all
        # the other relative path settings (see below)
        # self.theme is also a base path, but it requires special treatment
        absolute_from_working_dir = partial(absolute_from_base, base=Path.cwd())
        for key in ["path", "output_path", "cache_path", "plugin_paths"]:
            value = getattr(self, key)
            setattr(self, key, absolute_from_working_dir(value))

        # Strip and lowercase these values
        for key in ["default_lang", "theme_lang"]:
            setattr(self, key, getattr(self, key).strip().lower())
        self.date_formats = {k.lower(): v for k, v in self.date_formats.items()}

        # Setup locale
        if isinstance(self.locale, str):
            self.locale = [self.locale]
        for candidate_locale in self.locale:
            try:
                # Try setting the candidate locale
                locale.setlocale(locale.LC_ALL, candidate_locale)
                # If no error, we set self.locale to the candidate and exit the loop
                self.locale = candidate_locale
                break
            except locale.Error:
                pass
        else:
            logger.warning(
                "Locale could not be set. Check the LOCALE setting, "
                "ensuring it is valid and available on your system."
            )
            # We fall back to the currently defined locale
            self.locale = locale.setlocale(locale.LC_ALL)

        # Timezone
        if not isinstance(self.timezone, ZoneInfo):
            self.timezone = ZoneInfo(self.timezone)

        # Ensure paths for these values
        # All these paths are relative to a base path (see above)
        for key in [
            "article_paths",
            "article_excludes",
            "page_paths",
            "page_excludes",
            "static_paths",
            "static_excludes",
            "output_retention",
            "theme_static_dir",
            "theme_template_overrides",
            "category_paths",
            "category_excludes",
            "author_paths",
            "author_excludes",
            "tag_paths",
            "tag_excludes",
            "theme_static_paths",
        ]:
            value = getattr(self, key)
            # FIXME ensure all of these are relative paths, and that they do not walk up
            setattr(self, key, ensure_paths(value))

        # Ensure paths or none for the _save_as settings:
        # FIXME idem
        for key in [f.name for f in fields(self) if f.name.endswith("_save_as")]:
            path = getattr(self, key)
            # None disables the rendering of the associated object
            path = Path(path) if path else None
            setattr(self, key, path)

        # Article, taxonomy and page paths are mutually exclusive
        # So add all paths for an object type to the excludes of all the other types
        mutex_types = ("article", "page", "author", "category", "tag")
        for (i, _), (_, e) in permutations(
            batched(
                (
                    getattr(self, f"{a}_{b}")
                    for a, b in product(mutex_types, ("paths", "excludes"))
                ),
                n=2,
                strict=True,
            ),
            2,
        ):
            mutually_exclusive_sources(i, e)

        # Parse the IP address in bind
        if not isinstance(self.bind, (IPv4Address, IPv6Address)):
            self.bind = ip_address(self.bind)

        # Convert *_order_by settings into a key function if necessary
        for key in [f.name for f in fields(self) if f.name.endswith("_order_by")]:
            value = getattr(self, key)
            if isinstance(value, str):
                setattr(self, key, order_by_factory(value))

        # Add the trailing slash if missing (important for link joining)
        if not self.siteurl.endswith("/"):
            self.siteurl = f"{self.siteurl}/"

        # Find the installed themes path
        installed_themes_path = None
        if seagull_spec := find_spec(__package__):
            # the installed themes are stored in <seagull package>/themes/
            package_dir = Path(seagull_spec.origin).parent
            installed_themes_path = package_dir / "themes"
        if not (installed_themes_path and installed_themes_path.exists()):
            installed_themes_path = None
            logger.warning(
                "Couldn't find the installed themes path: 'simple' and "
                "the other installed themes won't be available."
            )

        # Set up the theme: if it's not a directory in the working directory, try
        # finding it in the installed themes
        if (
            not (theme_path := absolute_from_working_dir(self.theme).is_dir())
            and installed_themes_path
        ):
            theme_path = installed_themes_path / self.theme
        self.theme = theme_path
        # If the theme still doesn't exist, raise a RuntimeError
        if not self.theme.exists():
            raise RuntimeError(
                f"Couldn't load the theme '{self.theme}' from installed themes."
            )

        # If JINJA_ENVIRONMENT is not already a jinja2.Environment object, create it
        if not isinstance(self.jinja_environment, Environment):
            # Ensure the defaults for JINJA_ENVIRONMENT are set, even if the user has
            # set a custom JINJA_ENVIRONMENT
            jinja_defaults = next(
                filter(lambda f: f.name == "jinja_environment", fields(self.__class__))
            ).default_factory()
            for k, v in jinja_defaults.items():
                if k not in self.jinja_environment:
                    self.jinja_environment[k] = v
            # Default loader: template are searched for in the overrides first, then in
            # the theme
            template_paths = [*self.theme_template_overrides, self.theme / "templates"]
            loaders: list[BaseLoader] = [FileSystemLoader(template_paths)]
            prefix_loaders = {}
            # If we have found an installed themes path, the next loader we try is the
            # implicit loader for the simple theme
            if installed_themes_path:
                simple_loader = FileSystemLoader(
                    installed_themes_path / "simple" / "templates"
                )
                loaders.append(simple_loader)
                prefix_loaders["!simple"] = simple_loader
            # And the last loader we try is a prefix loader with !simple (if possible)
            # and !theme, which looks at self.theme's templates
            prefix_loaders["!theme"] = FileSystemLoader(self.theme / "templates")
            loaders.append(PrefixLoader(prefix_loaders))

            # Finally, we can create our Jinja environment object
            self.jinja_environment: Environment = Environment(
                loader=ChoiceLoader(loaders), **self.jinja_environment
            )

        # If the i18n extension is set, we configure it
        if install_gettext_translations := getattr(
            self.jinja_environment, "install_gettext_translations", None
        ):
            translations = gettext.NullTranslations()
            # If the site language is different from the theme's default one...
            if self.theme_lang != self.default_lang:
                # Try retrieving the translation for the site language
                try:
                    translations = gettext.translation(
                        domain="messages",
                        localedir=self.theme / "translations",
                        # FIXME all languages!
                        languages=[self.default_lang],
                    )
                except OSError:
                    logger.warning(
                        f"Cannot find translations for language '{self.default_lang}'."
                    )
            install_gettext_translations(translations, newstyle=True)
        else:
            logger.warning("Running without jinja2 internationalization.")

        # Jinja filter for time formatting
        self.jinja_environment.filters["strftime"] = strftime_jinja_filter
        # User defined filters for Jinja2
        self.jinja_environment.filters.update(self.jinja_filters)

        # If SEAGULL_CLASS is a string, import the class it is referring to
        if isinstance(self.seagull_class, str):
            module_name, cls_name = self.seagull_class.rsplit(".", 1)
            module = import_module(module_name)
            self.seagull_class = getattr(module, cls_name)

    @classmethod
    def from_settings_file(cls, settings_file: Path, **overrides: dict) -> Settings:
        """Initialize settings from a settings file.

        Seagull settings are defined in Python files.

        :param settings_file: Path to a settings file.
        :param overrides: Optional overrides.
        :return: A new `Settings` object.
        """
        module = module_from_spec(
            spec_from_file_location(settings_file.stem, settings_file)
        )

        return cls.from_module(module, **overrides)

    @classmethod
    def from_module(cls, module: ModuleType, **overrides: dict) -> Settings:
        """Initialize settings from a python module.

        :param module: A settings module.
        :param overrides: Optional overrides.
        :return: A new `Settings` object.
        """
        # Load the module
        sys.modules[module.__name__] = module
        module.__spec__.loader.exec_module(module)

        # Defined settings fields
        base_fields = [f.name for f in fields(cls) if f != "_extra"]

        def process_setting(dest: dict, extra: dict, key: str, value: object) -> None:
            if not cls.is_valid_param_key(key):
                return
            key = key.lower()
            if key in base_fields:  # base setting keys
                dest[key] = value
            else:  # additional setting keys
                extra[key] = value

        # Create the initialization context with the module members
        context = {}
        extra_context = {}
        if module:
            for k, v in getmembers(module):
                process_setting(context, extra_context, k, v)

        # Update overrides so that non-base settings are put in _extra
        context_overrides = {}
        extra_overrides = {}
        for k, v in overrides.items():
            process_setting(context_overrides, extra_overrides, k, v)

        # Update the context with overrides
        context.update(context_overrides)
        extra_context.update(extra_overrides)
        context.update(extra_context)

        # Set the working directory to the settings module directory
        os.chdir(Path(module.__spec__.origin).parent)
        return cls(**context)

    @classmethod
    def is_valid_param_key(cls, value: str) -> bool:
        """Validate a parameter key.

        Only uppercase setting keys are considered, and those starting with '_' are
        ignored as well.

        :param value: Key to test.
        :return: `True` if `value` is a valid parameter key.
        """
        return value.isupper() and not value.startswith("_")
