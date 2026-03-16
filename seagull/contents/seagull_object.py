import contextlib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from jinja2 import TemplateNotFound
from slugify import slugify

from seagull.exceptions import InvalidObjectError, SkippedFileError
from seagull.intrasite_link_parser import IntrasiteLinkParser
from seagull.utils import PluralFormatter

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, Self

    from jinja2 import Template

    from seagull.context import Context
    from seagull.settings import Settings


@dataclass(order=True)
class SeagullObject:
    """Base class for seagull objects."""

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        "slug",
        "save_as",
        "url",  # URL must be placed after save_as, as save_as is a fallback for URL
        "base_path",
    )
    """Fields that should be set.

    What it means is that they can't evaluate to `False` at the end of `__post_init__`.
    The order in which they are defined is important, because it determines the order
    in which auto-generation methods are called.
    """

    settings: Settings = field(compare=False, repr=False)
    """Settings associated with the object."""
    content: str = field(default="", compare=False, repr=False)
    """Content of the object."""
    source_path: Path | None = field(default=None, compare=False, repr=False)
    """Source path, if the object was created from a file."""
    base_path: Path | None = field(default=None, compare=False, repr=False)
    """If the object has a source path, base path associated with it."""
    title: str = field(default="", compare=False, repr=False)
    """Title for the object."""
    slug: str = field(default="", compare=True, repr=True)
    """Slug: this is used to set an object apart.

    Objects with the same slug should have a different lang.
    """
    lang: str = field(default="", compare=True, repr=True)
    """Lang of the object."""
    save_as: Path | None = field(default="", compare=False, repr=False)
    """Destination path for the object."""
    url: str | None = field(default=None, compare=False, repr=False)
    """URL for the object."""
    template: str = field(default="", compare=False, repr=False)
    """Template for rendering the object."""
    extra_metadata: dict[str, str] = field(
        default_factory=dict, compare=False, repr=False
    )
    """Additional metadata for the object."""
    in_default_lang: bool = field(default=True, compare=False, init=False, repr=False)
    """Whether the object is in the default lang."""
    translations: list[SeagullObject] = field(
        default_factory=list, init=False, compare=False, repr=False
    )
    """List of translations associated with the object."""

    def __post_init__(self) -> None:
        """Post-init routines.

        It ensures that the object is valid. Notably, for every required field in
        `self.__class__.MANDATORY_FIELDS`, it tries to auto-compute them. The class
        shall define a property with the name `_<field_name>` for every property that
        can be auto-computed.

        :raise InvalidObjectError: If a mandatory field is missing, or if the source
        path is not a subdirectory of the base path.
        :raise SkippedFileError: If `save_as` is `None` and couldn't be initialized with
        a default setting key.
        """
        # If the object has a lang, or should have one
        if "lang" in self.MANDATORY_FIELDS or self.lang:
            # Ensure it is set with the generated fallback
            self.lang = self.lang or self._lang
            # If that lang is not the default lang, update its settings so that it uses
            # the localized settings for this lang; if there's no localized settings for
            # the object's lang, fallback to default settings
            if self.lang != self.settings.default_lang:
                # Mark the object has not in the default lang
                self.in_default_lang = False
                with contextlib.suppress(ValueError):
                    self.settings = self.settings.localized_settings(self.lang)

        # Try calling the auto-compute properties for mandatory fields
        for f in self.MANDATORY_FIELDS:
            if not getattr(self, f):
                setattr(self, f, getattr(self, f"_{f}", None))

        # If there's a source path, it must be relative to the base path
        if self.source_path and not self.source_path.is_relative_to(self.base_path):
            raise InvalidObjectError(
                f"The source path '{self.source_path}' is not a "
                f"subpath of the base path '{self.base_path}'."
            )

        # Finally, check that all mandatory fields are initialized
        for f in self.MANDATORY_FIELDS:
            if not getattr(self, f):
                raise InvalidObjectError(f"'{f}' can't be empty.")

    @classmethod
    def from_parsed_metadata(
        cls,
        settings: Settings,
        context: Context,
        content: str,
        source_path: Path,
        base_path: Path,
        **metadata: object | str,
    ) -> Self:
        """Create a new seagull object based on raw parsed metadata.

        :param settings: Settings for the object.
        :param context: Shared context.
        :param content: Parsed content for the object.
        :param source_path: Absolute path of the source file.
        :param base_path: Base path of the source file.
        :param metadata: Raw metadata parsed by the `Reader` object.
        :return: A new seagull object.
        :raise InvalidObjectError: If a valid metadata key has an invalid value that
        cannot be simply discarded.
        :raise SkippedFileError: If the file should be skipped.
        """
        # Unused argument
        del context

        parsed_metadata: dict[str, Any] = {}
        for key, value in metadata.items():
            match key:
                # Strip these values
                case "slug" | "template":
                    parsed_value = value.strip() or None
                # Strip and lowercase these values
                case "lang":
                    parsed_value = value.lower().strip() or None
                # Convert save_as to a path
                case "save_as":
                    parsed_value = Path(value) if value.strip() else None
                case _:
                    parsed_value = value

            # None values are discarded
            if parsed_value is not None:
                parsed_metadata[key.lower()] = parsed_value

        # Finally, separate extra_metadata keys
        valid_fields = [f.name for f in fields(cls)]
        extra_metadata = {
            k: v for k, v in parsed_metadata.items() if k not in valid_fields
        }
        parsed_metadata = {
            k: v for k, v in parsed_metadata.items() if k in valid_fields
        }
        parsed_metadata["extra_metadata"] = extra_metadata

        return cls(
            settings=settings,
            content=content,
            source_path=source_path,
            base_path=base_path,
            **parsed_metadata,
        )

    @classmethod
    def all_object_types(cls) -> Iterable[type[SeagullObject]]:
        """Yield all subclasses."""
        for subcls in cls.__subclasses__():
            yield from subcls.all_object_types()
            yield subcls

    @classmethod
    def printable_name(cls, count: int = 1) -> str:
        """Convert the camelCase name of the class to a printable name.

        :param count: Count value for pluralization.
        """
        name = "".join(
            c if c.islower() else f" {c.lower()}" for c in cls.__name__
        ).strip()
        if name.endswith("y"):
            return PluralFormatter().format(
                f"{name[:-1]}{{count:plural,y,ies}}", count=count
            )
        return PluralFormatter().format(f"{name}{{count:plural,s}}", count=count)

    def update_intrasite_links(self, context: Context) -> None:
        """Refresh intra-site links.

        The URLs are updated in the content, as well as in metadata keys listed in the
        `settings.formatted_fields`. This includes field metadata, as well as extra
        metadata keys.

        :param context: Shared `Context` object.
        """
        # We make use of an intrasite link parser to update our links
        parser = IntrasiteLinkParser(self.settings.intrasite_link_regex)
        parser.update(self, context)

    def link_translations(self, objs: Iterable[Self]) -> None:
        """Find and link translations.

        It updates `self.translations`.

        :param objs: Objects of the same type to search for translations.
        """
        self.translations.extend(
            filter(
                # Look for objects with the same slug
                lambda o: o.slug == self.slug
                # Do not put `self` in its own list of translations
                and o is not self
                # Do not put the object twice in the list of translations
                and o not in self.translations,
                objs,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        """Return all fields and extra metadata (excluding the settings).

        :return: A shallow-copied dictionary.
        """
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in ("settings", "extra_metadata")
        } | self.extra_metadata

    def _field_setting_key(self, field_name: str) -> str:
        """Compute the setting key for a given field.

        :param field_name: Name of the field for the associated setting key.
        :return: Appropriate setting key for the field, depending on the state of the
        object. Typically, if the object is not in the default lang, the setting key is
        different.
        """
        class_fragment = self.__class__.__name__.lower()
        lang_fragment = "" if self.in_default_lang else "lang"
        return "_".join(f for f in (class_fragment, lang_fragment, field_name) if f)

    @property
    def _slug_source(self) -> str:
        """Base value to parse the auto-generated slug.

        :return: It uses `settings.slugify_source` to return the raw value to use for
        the slug. This setting can either be `basename`, which yields the source file
        name, or the name of a field or extra metadata. If this yields an empty value,
        it falls back to the `title` attribute.
        """
        match self.settings.slugify_source:
            case "basename":
                if self.source_path:
                    return self.source_path.stem
            case _ as key:
                # Try retrieving an attribute first
                with contextlib.suppress(AttributeError):
                    return str(getattr(self, key))
                # Try retrieving an extra metadata next
                with contextlib.suppress(KeyError):
                    return str(self.extra_metadata[key])
        # Finally, fall back to title
        return self.title

    @property
    def _slug(self) -> str:
        """Auto-generate a slug.

        :return: A slug generated with the object's slugify settings.
        """
        # Try to get slugify settings for this specific type of object
        if (
            slugify_settings := getattr(
                self.settings,
                f"{self.__class__.__name__.lower()}_slugify_settings",
                None,
            )
        ) is None:
            # Fallback to default slugify settings
            slugify_settings = self.settings.slugify_settings
        return slugify(self._slug_source, **slugify_settings)

    @property
    def _save_as(self) -> Path:
        """Auto-generate the destination path.

        :return: A value for `self.save_as`, computed from the appropriate settings'
        `*_save_as` value
        :raise SkippedFileError: If there is no valid setting key for this type of
        object.
        """
        setting_key = self._field_setting_key("save_as")
        output_path = getattr(self.settings, setting_key, None)
        if not output_path:
            raise SkippedFileError(
                f"No `save_as` value could be computed for the object "
                f"(attempted to load setting '{setting_key}')."
            )
        output_path = str(output_path).format(**self.as_dict())
        return Path(output_path)

    @property
    def _url(self) -> str:
        """Auto-generate the url."""
        url = getattr(self.settings, self._field_setting_key("url"))
        # We fall back to the save as attribute if the url format is empty
        return url.format(**self.as_dict()) or str(self.save_as)

    @property
    def _lang(self) -> str:
        """Auto-compute the lang."""
        return self.settings.default_lang

    @property
    def _base_path(self) -> Path:
        """Auto-compute the base path."""
        return self.settings.path

    @property
    def _template(self) -> str:
        """Auto-compute the template name.

        :return: By default, the template name is the lowercase name of the object
        class.
        """
        return self.__class__.__name__.lower()

    @property
    def jinja_context(self) -> dict[str, Any]:
        """Context dictionary for Jinja templates rendering."""
        return {
            # The object can be accessed via the generic attribute "obj", or via its
            # type name
            "obj": self,
            self.__class__.__name__.lower(): self,
            "siteurl": self.relative_url,
            "output_file": self.save_as,
        }

    @property
    def jinja_template(self) -> Template:
        """Jinja rendering template for the object.

        :return: A `jinja2.Template` object.
        :raise TemplateNotFound: if there is no valid template.
        """
        for ext in self.settings.template_extensions:
            with contextlib.suppress(TemplateNotFound):
                return self.settings.jinja_env_object.get_template(self.template + ext)
        raise TemplateNotFound(self.template)

    @property
    def static_links(self) -> set[Path]:
        """Discovered static links in the object.

        :return: Absolute paths to static links found in the object content and
        formatted fields.
        """
        parser = IntrasiteLinkParser(
            self.settings.intrasite_link_regex, valid_identifiers="static"
        )
        return {link.target for link in parser.extract(self)}

    @property
    def relative_source_path(self) -> Path | None:
        """Source path relative to the base path.

        :return: `None` if there is no source path.
        """
        if not self.source_path:
            return None
        return self.source_path.relative_to(self.base_path)

    @property
    def relative_url(self) -> str:
        """Relative site URL.

        :return: If `self.settings.relative_urls` is `False`, this returns
        `self.settings.site_url`. Otherwise, it returns the path to the site root,
        relative to the current object's output directory.
        """
        if not self.settings.relative_urls:
            return self.settings.siteurl
        return str(Path(".").relative_to(self.save_as.parent, walk_up=True))

    def __str__(self) -> str:
        """The string representation of an object is its slug.

        This is useful for the `*_SAVE_AS` and `*_URL` settings, among other things.
        """
        return self.slug
