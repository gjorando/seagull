import gettext
import locale
import os
import sys
from dataclasses import dataclass, field, fields
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from inspect import getmembers
from ipaddress import IPv4Address, IPv6Address, ip_address
from itertools import batched, permutations, product
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader

from seagull.contents.feed import FeedType
from seagull.decorators import extra_dataclass
from seagull.log import logger
from seagull.utils import (
    PaginationRule,
    absolute_from_base_path,
    ensure_paths,
    get_installed_themes_path,
    order_by_factory,
    strftime_jinja_filter,
    temporary_locale,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
    from typing import Any, Self

    from jinja2 import BaseLoader

    from seagull.contents import Article, Author, Category, Page, Tag
    from seagull.utils import Comparable


@extra_dataclass
@dataclass(kw_only=True, repr=False)
class Settings:
    # Basic settings
    use_folder_as_category: bool = True
    default_category: str = "misc"
    docutils_settings: dict[str, Any] = field(default_factory=dict)
    html_parser: str = "html.parser"
    delete_output_directory: bool = False
    output_retention: list[Path] = field(default_factory=list)
    jinja_environment: dict[str, Any] = field(
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
    summary_max_length: int | None = 50
    summary_max_paragraphs: int | None = None
    summary_end_suffix: str = "…"
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
    article_url: str = "{date:%Y}/{date:%m}/{date:%d}/{slug}/"
    article_save_as: Path | None = Path(
        "{date:%Y}/{date:%m}/{date:%d}/{slug}/index.html"
    )
    article_lang_url: str = "{lang}/{date:%Y}/{date:%m}/{date:%d}/{slug}/"
    article_lang_save_as: Path | None = Path(
        "{lang}/{date:%Y}/{date:%m}/{date:%d}/{slug}/index.html"
    )
    draft_url: str = "drafts/{slug}.html"
    draft_save_as: Path | None = Path("drafts/{slug}.html")
    draft_lang_url: str = "drafts/{slug}-{lang}.html"
    draft_lang_save_as: Path | None = Path("drafts/{slug}-{lang}.html")
    page_url: str = "pages/{slug}/"
    page_save_as: Path | None = Path("pages/{slug}/index.html")
    page_lang_url: str = "{lang}/pages/{slug}/"
    page_lang_save_as: Path | None = Path("{lang}/pages/{slug}/index.html")
    draft_page_url: str = "drafts/pages/{slug}.html"
    draft_page_save_as: Path | None = Path("drafts/pages/{slug}.html")
    draft_page_lang_url: str = "drafts/pages/{slug}-{lang}.html"
    draft_page_lang_save_as: Path | None = Path("drafts/pages/{slug}-{lang}.html")
    author_url: str = "author/{slug}"
    author_save_as: Path | None = Path("author/{slug}/index.html")
    author_lang_url: str = "{lang}/author/{slug}/"
    author_lang_save_as: Path | None = Path("{lang}/author/{slug}/index.html")
    category_url: str = "category/{slug}/"
    category_save_as: Path | None = Path("category/{slug}/index.html")
    category_lang_url: str = "{lang}/category/{slug}/"
    category_lang_save_as: Path | None = Path("{lang}/category/{slug}/index.html")
    tag_url: str = "tag/{slug}/"
    tag_save_as: Path | None = Path("tag/{slug}/index.html")
    tag_lang_url: str = "{lang}/tag/{slug}/"
    tag_lang_save_as: Path | None = Path("{lang}/tag/{slug}/index.html")
    year_archive_url: str = "archives/{date:%Y}/"
    year_archive_save_as: Path | None = Path("archives/{date:%Y}/index.html")
    year_archive_lang_url: str = "{lang}/archives/{date:%Y}/"
    year_archive_lang_save_as: Path | None = Path(
        "{lang}/archives/{date:%Y}/index.html"
    )
    month_archive_url: str = "archives/{date:%Y}/{date:%m}/"
    month_archive_save_as: Path | None = Path("archives/{date:%Y}/{date:%m}/index.html")
    month_archive_lang_url: str = "{lang}/archives/{date:%Y}/{date:%m}/"
    month_archive_lang_save_as: Path | None = Path(
        "{lang}/archives/{date:%Y}/{date:%m}/index.html"
    )
    day_archive_url: str = ""
    day_archive_save_as: Path | None = None
    day_archive_lang_url: str = ""
    day_archive_lang_save_as: Path | None = None
    archives_url: str = "archives/"
    archives_save_as: Path | None = Path("archives/index.html")
    archives_lang_url: str = "{lang}/archives/"
    archives_lang_save_as: Path | None = Path("{lang}/archives/index.html")
    authors_url: str = "authors/"
    authors_save_as: Path | None = Path("authors/index.html")
    authors_lang_url: str = "{lang}/authors/"
    authors_lang_save_as: Path | None = Path("{lang}/authors/index.html")
    categories_url: str = "categories/"
    categories_save_as: Path | None = Path("categories/index.html")
    categories_lang_url: str = "{lang}/categories/"
    categories_lang_save_as: Path | None = Path("{lang}/categories/index.html")
    tags_url: str = "tags/"
    tags_save_as: Path | None = Path("tags/index.html")
    tags_lang_url: str = "{lang}/tags/"
    tags_lang_save_as: Path | None = Path("{lang}/tags/index.html")
    index_url: str = "."
    index_save_as: Path | None = Path("index.html")
    index_lang_url: str = "{lang}/"
    index_lang_save_as: Path | None = Path("{lang}/index.html")
    direct_template_url: str = "{slug}/"
    direct_template_save_as: Path | None = Path("{slug}/index.html")
    direct_template_lang_url: str = "{lang}/{slug}/"
    direct_template_lang_save_as: Path | None = Path("{lang}/{slug}/index.html")
    slugify_source: str = "title"
    slugify_settings: dict[str, Any] = field(default_factory=dict)
    author_slugify_settings: dict[str, Any] | None = None
    category_slugify_settings: dict[str, Any] | None = None
    tag_slugify_settings: dict[str, Any] | None = None

    # Time and date
    timezone: str | ZoneInfo = field(default_factory=lambda: ZoneInfo("UTC"))
    default_date: str | None = None
    date_format: str = "%a %d %B %Y"
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
            "archives",
        ]
    )

    # Metadata
    author: str | None = None
    default_metadata: dict[str, Any] = field(default_factory=dict)
    filename_metadata: str = r"(?P<date>\d{4}-\d{2}-\d{2}).*"
    path_metadata: str = ""
    extra_path_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Feed
    feed_domain: str | None = None
    feed_types: list[FeedType] = field(default_factory=lambda: [FeedType.ATOM])
    all_feed_url: str = ""
    all_feed_save_as: Path | None = Path("feeds/all.{feed_type}.xml")
    feed_url: str = ""
    feed_save_as: Path | None = None
    feed_lang_url: str = ""
    feed_lang_save_as: Path | None = None
    category_feed_url: str = ""
    category_feed_save_as: Path | None = Path("feeds/category/{slug}.{feed_type}.xml")
    category_feed_lang_url: str = ""
    category_feed_lang_save_as: Path | None = Path(
        "{lang}/feeds/category/{slug}.{feed_type}.xml"
    )
    author_feed_url: str = ""
    author_feed_save_as: Path | None = Path("feeds/author/{slug}.{feed_type}.xml")
    author_feed_lang_url: str = ""
    author_feed_lang_save_as: Path | None = Path(
        "{lang}/feeds/author/{slug}.{feed_type}.xml"
    )
    tag_feed_url: str = ""
    tag_feed_save_as: Path | None = None
    tag_feed_lang_url: str = ""
    tag_feed_lang_save_as: Path | None = None
    feed_max_items: int | None = 100
    rss_feed_summary_only: bool = True
    feed_append_ref: bool = False

    # Pagination
    default_orphans: int = 0
    default_pagination: int = 0
    paginated_templates: dict[str, int | None] = field(
        default_factory=lambda: {
            "index": None,
            "tag": None,
            "category": None,
            "author": None,
        }
    )
    pagination_patterns: list[PaginationRule] = field(
        default_factory=lambda: [
            (-1, "{base_name}/page/last/", "{base_name}/page/last/index.html"),
            (1, "{url}", "{save_as}"),
            (2, "{base_name}/page/{number}/", "{base_name}/page/{number}/index.html"),
        ]
    )

    # Translations
    default_lang: str = "en"
    langs: dict[str, dict] = field(default_factory=dict)
    use_subsites: bool = False

    # Ordering content
    # TODO allow for sorting by more than one function (eg. sort by date, then by name)
    article_order_by: str | tuple[Callable[[Article], Comparable], bool] = (
        "reversed-date"
    )
    page_order_by: str | tuple[Callable[[Page], Comparable], bool] = "basename"
    author_order_by: str | tuple[Callable[[Author], Comparable], bool] = "name"
    category_order_by: str | tuple[Callable[[Category], Comparable], bool] = "name"
    tag_order_by: str | tuple[Callable[[Tag], Comparable], bool] = "name"

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

    # Technical fields
    _settings_path: Path | None = field(default=None, repr=False)
    _overrides: dict[str, Any] = field(default_factory=dict, repr=False)
    _localized_settings: dict[str, Self] = field(default_factory=dict, repr=False)
    _jinja_env_object: Environment | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        logger.warning(f"{self.output_path}, {Path.cwd()}")
        """Parse and normalize various settings."""
        # Coalesce these relative paths to absolute paths relative to _working_dir,
        # which is usually the directory where the settings module is
        # All these paths are "base paths", which means they're used as a base for all
        # the other relative path settings (see below)
        # self.theme is also a base path, but it requires special treatment
        for key in ("path", "output_path", "cache_path", "plugin_paths"):
            value = getattr(self, key)
            setattr(self, key, absolute_from_base_path(value, Path.cwd()))
        # Ensure relative paths
        self._ensure_relative_paths(
            "output_retention", "theme_static_dir", "theme_template_overrides"
        )

        # Convert *_order_by settings into a key function if necessary
        for key in [f.name for f in fields(self) if f.name.endswith("_order_by")]:
            value = getattr(self, key)
            if isinstance(value, str):
                setattr(self, key, order_by_factory(value))
        # If seagull_class is a string, import the class it is referring to
        if isinstance(self.seagull_class, str):
            module_name, cls_name = self.seagull_class.rsplit(".", 1)
            module = import_module(module_name)
            self.seagull_class = getattr(module, cls_name)
        # FIXME very not practical with absolute URLs
        # Add the trailing slash if missing (important for link joining)
        if not self.siteurl.endswith("/"):
            self.siteurl = f"{self.siteurl}/"
        # Parse the IP address in bind
        if not isinstance(self.bind, (IPv4Address, IPv6Address)):
            self.bind = ip_address(self.bind)
        # Convert our pagination rules to the named tuple type,
        # and ensure they're sorted
        self.pagination_patterns = sorted(
            [PaginationRule(*pr) for pr in self.pagination_patterns],
            key=attrgetter("min_page"),
        )

        # Article, taxonomy and page paths are mutually exclusive
        self._mutually_exclude_sources("article", "page", "author", "category", "tag")
        # Set up lang-related settings
        self._init_i18n()
        # Find the installed themes path
        installed_themes_path = get_installed_themes_path()
        # Resolve the theme path
        self._init_theme(installed_themes_path)
        # Setup the jinja environment
        self._init_jinja_environment(installed_themes_path)
        # Validate the feed-related settings
        self._validate_feed_settings()
        # Finally, register all localized settings; this must always be done last
        for lang in (self.default_lang, *self.langs):
            self.localized_settings(lang)

    def _ensure_relative_paths(self, *other_keys: str) -> None:
        """Ensure relative path settings are `Path` objects.

        `_save_as`, `_paths`, and `_excludes` settings, as well all `other_keys`
        settings, are processed. A relative path here is relative to one of the base
        path settings.

        :param other_keys: Other setting keys to process.
        """
        # TODO ensure all of these are relative paths, and that they do not walk up
        save_as_keys = []
        include_keys = []
        exclude_keys = []
        for setting_key in self.as_dict():
            if setting_key.endswith("_save_as"):
                save_as_keys.append(setting_key)
            elif setting_key.endswith("_paths"):
                include_keys.append(setting_key)
            elif setting_key.endswith("_excludes"):
                exclude_keys.append(setting_key)
        # _save_as settings can be None (disables
        # the rendering of the associated object)
        for key in save_as_keys:
            path = getattr(self, key)
            path = Path(path) if path else None
            setattr(self, key, path)
        for key in (
            *other_keys,
            *include_keys,
            *exclude_keys,
        ):
            value = getattr(self, key)
            setattr(self, key, ensure_paths(value))

    def _mutually_exclude_sources(self, *mutex_types: str) -> None:
        """Add all paths for an object type to the excludes of all other types.

        Paths for an object type are stored in `self.<type>_paths`, excludes are in
        `self.<type>_excludes`.

        :param mutex_types: Sequence of mutually exclusive object types.
        """
        for (includes, _), (_, excludes) in permutations(
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
            for p in includes:
                if p not in excludes:
                    excludes.append(p)

    def _validate_feed_settings(self) -> None:
        """Feed settings validation."""
        if not self.feed_domain:
            self.feed_domain = self.siteurl
        self.feed_types = [FeedType(f.lower()) for f in self.feed_types]

    def _init_i18n(self) -> None:
        """Set up internationalization related settings."""
        # Strip and lowercase language codes
        for key in ["default_lang", "theme_lang"]:
            setattr(self, key, getattr(self, key).strip().lower())
        self.langs = {k.strip().lower(): v for k, v in self.langs.items()}

        # Configure the locale
        if isinstance(self.locale, str):
            self.locale = [self.locale]
        for candidate_locale in self.locale:
            try:
                # Try the candidate locale
                with temporary_locale(candidate_locale, locale.LC_ALL):
                    pass
                # If no error, we set self.locale to the candidate and exit the loop
                self.locale = candidate_locale
                break
            except locale.Error:
                pass
        else:
            log_locales = ", ".join(f"'{loc}'" for loc in self.locale)
            logger.warning(
                f"No valid locale: {log_locales}. Check the LOCALE setting, "
                "ensuring it is valid and available on your system."
            )
            # We fall back to the currently defined locale
            self.locale = locale.setlocale(locale.LC_ALL)

        # Ensure timezone is a ZoneInfo object
        if not isinstance(self.timezone, ZoneInfo):
            self.timezone = ZoneInfo(self.timezone)

    def _init_theme(self, installed_themes_path: Path | None) -> None:
        """Set up the theme path.

        If the theme setting value doesn't refer to a subdir of the working directory,
        try finding it in the installed themes.

        :param installed_themes_path: The path for installed themes, if it exists.
        :raise RuntimeError: If the theme couldn't be found.
        """
        if (
            not (theme_path := absolute_from_base_path(self.theme, Path.cwd())).is_dir()
            and installed_themes_path
        ):
            theme_path = installed_themes_path / self.theme
        self.theme = theme_path
        # If the theme still doesn't exist, raise a RuntimeError
        if not self.theme.exists():
            raise RuntimeError(
                f"Couldn't load the theme '{self.theme}' from installed themes."
            )

    def _init_jinja_environment(self, installed_themes_path: Path | None) -> None:
        """Set up the jinja environment object.

        :param installed_themes_path: The path for installed themes, if it exists.
        """
        # Ensure the defaults for JINJA_ENVIRONMENT are set, even if the user has
        # set a custom JINJA_ENVIRONMENT
        jinja_defaults = next(
            filter(lambda f: f.name == "jinja_environment", fields(self.__class__))
        ).default_factory()
        for k, v in jinja_defaults.items():
            self.jinja_environment.setdefault(k, v)
        # Default loader: template are searched for in the template overrides first,
        # then in the theme
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
            # The simple theme can also be accessed with the !simple prefix
            prefix_loaders["!simple"] = simple_loader
        # And the last loader we try is a prefix loader with !simple (if possible)
        # and !theme, which looks at self.theme's templates
        prefix_loaders["!theme"] = FileSystemLoader(self.theme / "templates")
        loaders.append(PrefixLoader(prefix_loaders))

        # Finally, we can create our Jinja environment object
        environment = Environment(
            loader=ChoiceLoader(loaders), **self.jinja_environment
        )

        # Jinja filter for time formatting
        environment.filters["strftime"] = strftime_jinja_filter
        # User defined filters for Jinja2
        environment.filters.update(self.jinja_filters)

        # Store our environment object in the settings
        self._jinja_env_object = environment

        # If the i18n extension is set, we configure it
        if install_gettext_translations := getattr(
            environment, "install_gettext_translations", None
        ):
            # We will fall back to a null translation for the theme lang or a lang
            # that's not available for the theme
            translations = gettext.NullTranslations()
            # If the site language is different from the theme's default one...
            if self.theme_lang != self.default_lang:
                # Try retrieving the translation for the site language
                try:
                    translations = gettext.translation(
                        domain="messages",
                        localedir=self.theme / "translations",
                        languages=[self.default_lang],
                    )
                    logger.debug(
                        f"Installed '{self.default_lang}' translations for the theme."
                    )
                except OSError:
                    logger.warning(
                        f"Cannot find translations for language '{self.default_lang}'."
                    )
            install_gettext_translations(translations, newstyle=True)
        else:
            logger.warning("Running without jinja2 internationalization.")

    def localized_settings(self, lang: str) -> Self:
        """Get the localized settings for a given lang.

        It creates a shallow copy of the current object, with `self.langs[lang]` as a
        dictionary of overrides. The copy is cached; if `lang == self.default_lang`,
        we cache `self` as well.

        :param lang: Target language.
        :return: A new `Settings` object.
        :raise ValueError: If there is no `lang` override in `self.langs`.
        """
        lang = lang.lower()
        # If the localized settings were already created, simply return them
        if lang in self._localized_settings:
            return self._localized_settings[lang]
        # Otherwise, if we're retrieving the default lang, simply return self
        if lang == self.default_lang:
            # We also keep track of the default lang
            self._localized_settings[lang] = self
            return self
        # Otherwise, let's try registering a new Settings object specific to this lang
        context = self.as_dict()
        # We get the overrides from self.langs[lang], and we raise a ValueError if
        # there is no override for this lang; we pop the langs from the context of the
        # localized settings as well
        if (lang_overrides := context.pop("langs", {}).get(lang)) is None:
            raise ValueError(lang)
        # Convert setting keys to lowercase
        lang_overrides = {k.lower(): v for k, v in lang_overrides.items()}
        context.update(lang_overrides)
        # Update the default_lang for these localized settings
        context["default_lang"] = lang
        # Do not re-do the subsites setup in localized settings
        context["use_subsites"] = False
        # Keep track of the lang overrides and the other localized settings
        context["_overrides"] = lang_overrides
        context["_localized_settings"] = self._localized_settings
        self._localized_settings[lang] = self.__class__(**context)
        return self._localized_settings[lang]

    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary of all fields and extra metadata attributes."""
        return {
            k: getattr(self, k)
            for k in [f.name for f in fields(self)]
            + list(getattr(self, "__extra_dataclass__attrs__", []))
        }

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

        # Update overrides
        context_overrides = {}
        extra_overrides = {}
        for k, v in overrides.items():
            process_setting(context_overrides, extra_overrides, k, v)

        # Update the context with overrides
        context.update(context_overrides)
        extra_context.update(extra_overrides)
        context.update(extra_context)

        # As this settings instance was created from a file, we record its path
        context["_settings_path"] = Path(module.__spec__.origin)
        # Keep track of the overrides
        context["_overrides"] = context_overrides | extra_overrides
        # Set the working directory to the settings module directory
        os.chdir(context["_settings_path"].parent)
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

    @property
    def settings_path(self) -> Path | None:
        """Getter for the settings path.

        :return: The path of the settings file from which the `Settings` instances comes
        from, or `None` if it was created programmatically.
        """
        return self._settings_path

    @property
    def overrides(self) -> dict:
        """Getter for the overrides.

        :return: If `self.settings_path` is not None, this property keeps track of
        settings overrides.
        """
        return self._overrides

    @property
    def jinja_env_object(self) -> Environment:
        """Getter for the Jinja `Environment` object.

        :return: The configured Jinja environment for template rendering.
        :raise RuntimeError: If the Jinja environment is not initialized.
        """
        if not self._jinja_env_object:
            raise RuntimeError("The Jinja environment has not been initialized.")
        return self._jinja_env_object
