import re
import urllib.parse
from dataclasses import dataclass, field, fields
from functools import total_ordering
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Self, cast
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from jinja2.exceptions import TemplateNotFound
from slugify import slugify

from seagull.exceptions import InvalidObject
from seagull.log import logger, warning_with_paths

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sequence

    from bs4 import Tag

    from seagull.context import Context
    from seagull.settings import Settings


def reserved_property(fget: Callable) -> property:
    """Create a read-only property for a seagull object.

    If the user tries to set metadata with the same name as a Python property of the
    seagull object, it will raise a more descriptive `AttributeError`.

    :param fget: Getter for the property.
    :return: A `property` object.
    """

    def fset(self: SeagullObject, _):
        """Failsafe setter for the property.

        :raise InvalidObject: Always.
        """
        raise InvalidObject(
            f"'{fget.__name__}' is a reserved metadata key for objects "
            f"of type '{self.__class__.__name__}'."
        )

    return property(fget, fset)


class IntrasiteLink(NamedTuple):
    """Data associated with an intrasite link."""

    raw_link: str
    identifier: str
    target: Path | str


class IntrasiteLinkParser:
    """A helper parser to extract intrasite links.

    Upon feeding it a seagull object, it extracts the intrasite links in it. Links are
    formatted to be relative to the base path of the object.
    """

    valid_attrs = (
        "href",
        "src",
        "poster",
        "data",
        "cite",
        "formaction",
        "action",
        "content",
    )
    path_identifiers = ("static", "filename", "attach")

    def __init__(
        self,
        intrasite_link_regex: str,
        valid_identifiers: str | list[str] | None = None,
    ):
        """Initialize the parser.

        :param intrasite_link_regex: Regex for identifying the intrasite link
        identifier.
        :param valid_identifiers: Optional identifier or list of identifier to filter
        links.
        """
        self.regex_str: str = rf"{intrasite_link_regex}(?P<target>.*)"
        self.regex: re.Pattern = re.compile(self.regex_str, re.X)
        if not valid_identifiers:
            valid_identifiers = None
        elif isinstance(valid_identifiers, str):
            valid_identifiers = [valid_identifiers]
        self.valid_identifiers: list[str] | None = valid_identifiers

    def _has_valid_attr(self, tag: Tag) -> bool:
        """Filter out tags that don't have a valid link attribute."""
        return any(tag.has_attr(attr) for attr in self.valid_attrs)

    @staticmethod
    def _iterate_object(data: SeagullObject) -> Iterable[tuple[str, BeautifulSoup]]:
        """Iterate over every formatted field in a seagull object.

        :param data: A seagull object.
        :return: Iterate a tuple of `(field_name, soupified_content)`.
        """
        for key in data.settings.formatted_fields + ["content"]:
            # Soup time if the field exists in the object
            if value := getattr(data, key, None):
                yield key, BeautifulSoup(value, features=data.settings.html_parser)

    def _iterate_valid_attrs(
        self, soup: BeautifulSoup
    ) -> Iterable[tuple[Tag, str, str]]:
        """Iterate all valid attributes in all tags of a soup.

        :param soup: Soupified content.
        :return: Iterate a tuple of `(associated_tag, attr_name, attr_value)`.
        """
        # Look for all tags with a valid link attribute
        for tag in soup(self._has_valid_attr):
            # For every link attribute
            for attr_name, attr_value in tag.attrs.items():
                # Yield if the attribute is an accepted attribute
                if attr_name in self.valid_attrs:
                    yield tag, attr_name, attr_value

    def extract(self, obj: SeagullObject) -> set[IntrasiteLink]:
        """Retrieve the intrasite links.

        :param obj: A seagull object. Formatted fields are parsed as well.
        :return: A set of absolute paths.
        """
        links = set()
        # Retrieve the links from all formatted fields, including the content itself
        for _, soup in self._iterate_object(obj):
            for _, _, attr_value in self._iterate_valid_attrs(soup):
                # Go to the next attribute if we don't have a match
                if not (match := self.regex.match(attr_value)):
                    continue
                # If we have a list of valid types, skip links of another type
                what = match.group("what").lower().strip()
                if self.valid_identifiers and what not in self.valid_identifiers:
                    continue
                # Convert %xx escapes back to unicode
                target = urllib.parse.unquote(match.group("target"))
                # If the target is a path
                if what in self.path_identifiers:
                    target = Path(target)
                    # Make the path absolute:
                    # - if it has a leading slash path, it is rooted in the base path
                    # - otherwise, it is relative to the source_path folder
                    target = (
                        obj.base_path
                        / (
                            # path.relative_to("/") if path.is_relative_to("/") removes the
                            # leading slash
                            target.relative_to("/")
                            if target.is_relative_to("/")
                            else obj.relative_source_path.parent / target
                        )
                    ).resolve()
                link = IntrasiteLink(
                    raw_link=attr_value, identifier=what, target=target
                )
                links.add(link)
        return links

    def update(self, obj: SeagullObject, context: Context):
        """Update intrasite links using data fron a `Context` object.

        :param obj: A seagull object. Formatted fields are parsed as well.
        :param context: Shared context to use for link replacement.
        """
        # We extract our list of links
        links = self.extract(obj)
        # Then, we create a replacement for each intrasite reference
        parsed_links: dict[str, str] = {}
        for raw_link, what, target in links:
            match what:
                # Static files
                # TODO handle attached files
                case _ if what in self.path_identifiers:
                    context_key = (
                        "generated_content" if what == "filename" else "static_content"
                    )
                    if not (target_obj := getattr(context, context_key).get(target)):
                        logger.warning(
                            f"'{target}': unknown content in '{obj.source_path}'."
                        )
                        continue
                    target_path = target_obj.url
                # Index
                # FIXME allow for any direct template
                case "index":
                    target_path = obj.settings.index_url
                # Taxonomies, or unknown identifier
                case _:
                    # Try getting the appropriate list of taxa
                    try:
                        _, taxa = context.taxa_by_name(what)
                    except KeyError:
                        logger.warning(
                            f"'{what}': unknown link identifier in '{obj.source_path}'."
                        )
                        continue
                    # Try fetching the taxon by name
                    for taxon in taxa:
                        if taxon.name == target:
                            target_path = taxon.url
                            break
                    else:
                        logger.warning(
                            f"'{target}': unknown {what.lower()} in "
                            f"'{obj.source_path}'."
                        )
                        continue
            # At this point, we should have a target path, relative to the output path
            target_path = Path(target_path)
            # Now we construct the parsed URL
            if obj.settings.relative_urls:
                # If relative_urls is True, the base is the URL of the current object
                base_url = obj.url
            else:
                # Otherwise, the base is the site URL
                base_url = obj.settings.siteurl
                # And we make our target path "absolute"
                target_path = Path("/") / target_path
            # Extract the path component from the base URL
            base_url = urlparse(base_url)
            base_url_path = Path(base_url.path)
            # If the base path ends with a slash, we walk up one step
            if not base_url.path.endswith("/"):
                base_url_path = base_url_path.parent
            # Now, we make the target path relative to our base
            joined_path = target_path.relative_to(base_url_path, walk_up=True)
            # We unparse the URL to reconstruct the final URL
            parsed_url = urlunparse(base_url._replace(path=str(joined_path)))
            # Add it to our dictionary of parsed links
            parsed_links[raw_link] = cast("str", cast("Sequence", parsed_url))
        # Finally, let's replace our links!
        # For each link attribute in each formatted field
        for f, soup in self._iterate_object(obj):
            for tag, attr_name, attr_value in self._iterate_valid_attrs(soup):
                # If the link is in our dictionary of parsed links...
                if attr_value in parsed_links:
                    # We replace the link with its parsed version
                    tag[attr_name] = parsed_links[attr_value]
            # And we update the content of the field
            setattr(obj, f, str(soup))


@dataclass(repr=False)
@total_ordering
class SeagullObject:
    """Base class for seagull objects.

    A seagull object holds information about a conceptual element of a seagull site.
    """

    mandatory_fields: ClassVar[tuple[str, ...]] = (
        "title",
        "slug",
        "save_as",
        "url",
        "lang",
    )
    # For 99% of objects, the default base path is the content path
    default_base_path_key: ClassVar[str] = "path"

    # settings, content, source_path and base_path should always be the first attributes
    settings: Settings = field(repr=False)
    content: str = ""
    source_path: Path | None = None  # Absolute source path
    base_path: Path | None = None
    translation: bool = False
    translations: list[SeagullObject] = field(default_factory=list, init=False)
    title: str = ""
    slug: str = ""
    lang: str = ""
    save_as: Path | None = None
    url: str | None = None
    template: str | None = None

    def __post_init__(self):
        # If the object has a source path and base_path is None, retrieve the base path
        # from the settings using self.default_base_path_key
        if self.source_path and not self.base_path:
            self.base_path = getattr(self.settings, self.default_base_path_key)
        # Generate a slug if required
        if not self.slug:
            self.slug = self._slugify()
        # Fallback to the default lang
        if not self.lang:
            self.lang = self.settings.default_lang
        # Generate the destination path if required
        if self.save_as is None:
            self.save_as = self._save_as()
        # Generate the url if required
        if self.url is None:
            self.url = self._url()
        # Cache the template object for the seagull object
        self.template_object = None
        if self.template is not None:
            # Try every possible extension
            for ext in self.settings.template_extensions:
                try:
                    self.template_object = self.settings.jinja_environment.get_template(
                        self.template + ext
                    )
                    break
                except TemplateNotFound:
                    pass
            else:
                raise TemplateNotFound(self.template)

        # If there's a source path, it must be relative to the base path
        if self.source_path and not self.source_path.is_relative_to(self.base_path):
            raise InvalidObject(
                f"The source path '{self.source_path}' is not a "
                f"subpath of the base path '{self.base_path}'."
            )

        # Check that mandatory fields are initialized
        for f in self.mandatory_fields:
            if not getattr(self, f):
                raise InvalidObject(f"'{f}' can't be empty")

    def _setting_key_fragments(self, field_name: str) -> list[str]:
        """Setting key fragments for formatting a field.

        Used for the `save_as` and `url` fields. Join the returned list with underscores
        to get the setting attribute.

        :param: Field associated with the setting key.
        :return: A list of fragments for deducing the setting key.
        """
        class_fragment = self.__class__.__name__.lower()
        lang_fragment = "lang" if self.lang != self.settings.default_lang else None
        # Filter-out empty fragments
        return [f for f in [class_fragment, lang_fragment, field_name] if f]

    @property
    def _url_setting_key(self) -> str:
        return "_".join(self._setting_key_fragments("url"))

    @property
    def _save_as_setting_key(self) -> str:
        return "_".join(self._setting_key_fragments("save_as"))

    def as_dict(self, _recurse=None) -> dict[str, Any]:
        """Return a dictionary of all fields and extra metadata attributes.
        The `settings` field is not included.
        """
        return {
            f.name: getattr(self, f.name) for f in fields(self) if f.name != "settings"
        } | self.extra_metadata

    def _save_as(self) -> Path | None:
        """Auto-generate the destination path."""
        setting_key = self._save_as_setting_key
        output_path = getattr(self.settings, setting_key, None)
        if not output_path:
            return None
        output_path = str(output_path).format(**self.as_dict())
        return Path(output_path)

    def _url(self) -> str:
        """Auto-generate the url."""
        setting_key = self._url_setting_key
        url = getattr(self.settings, setting_key)
        return url.format(**self.as_dict())

    def _slugify(self) -> str:
        """Auto-generate a slug."""
        # FIXME ensure unique slugs per object type
        # Retrieve the per-object type slugify settings if they exist
        settings_key = f"{self.__class__.__name__.lower()}_slugify_settings"
        if (slugify_settings := getattr(self.settings, settings_key, None)) is None:
            # Fallback to default slugify settings
            slugify_settings = self.settings.slugify_settings
        return slugify(self.title, **slugify_settings)

    @classmethod
    def _find_original_translations(cls, objs: list[Self]) -> list[Self]:
        """Subroutine to identify the objects that are the original translation.

        :param objs: List of candidate objects (assumed to be related).
        :return: All objects that could be the original translation. Under normal
        circumstances, there should only be a single element in this list.
        """
        # Log a warning if there are related items with the same lang attribute
        for lang, items in groupby(objs, attrgetter("lang")):
            items = list(items)
            if len(items) > 1:
                warning_with_paths(
                    f"There are {len(items)} items with lang '{lang}'.",
                    paths=[o.source_path for o in items],
                )

        # Valid candidates are objects with translation set to False...
        candidates = [o for o in objs if not o.translation]
        # ... Unless all the objects are marked as translations
        if not candidates:
            warning_with_paths(
                f"All {len(objs)} items are marked as a translation.",
                paths=[o.source_path for o in objs],
            )
            candidates = objs

        # Find objects in default language, or fallback to all candidates
        origs = [o for o in candidates if o.in_default_lang] or candidates
        # Log a warning if we have more than one original object
        if len(origs) > 1:
            warning_with_paths(
                f"All {len(objs)} items are marked as not translated.",
                [o.source_path for o in origs],
            )
        return origs

    @classmethod
    def link_translations(
        cls,
        objs: list[SeagullObject],
        translation_id: str | Collection[str] | None = None,
    ) -> list[Self]:
        """Find and link translations.

        It updates the `translations` attribute of each object in `objs`.

        :param objs: List of objects of the same type to search translations in.
        :param translation_id: Attribute or collection of attributes keys. Two objects
        are deemed to be related if they have the same value(s) for all of these
        attributes. If this parameter is `None`, this method is a no-op.
        :return: A list of original objects.
        """

        # No-op if translation_id evaluates to False
        if not translation_id:
            return objs
        # Ensure we have a set
        if isinstance(translation_id, str):
            translation_id = {translation_id}
        if not isinstance(translation_id, set):
            translation_id = set(translation_id)

        origs = []
        # Group by translation id
        objs = sorted(objs, key=attrgetter(*translation_id))
        # For each group of related items, retrieve the originals and translations
        for _, items in groupby(objs, attrgetter(*translation_id)):
            items = list(items)
            origs.extend(cls._find_original_translations(items))
            # Cross-reference translations
            for orig in items:
                orig.translations.extend(trans for trans in items if orig != trans)
        return origs

    def update_intrasite_links(self, context: Context):
        """Refresh intra-site URLs.

        The URLs are updated in the content, as well as in metadata keys listed in the
        `FORMATTED_FIELDS` setting.

        :param context: Shared `Context` object.
        """
        # We make use of an intrasite link parser to update our links
        parser = IntrasiteLinkParser(self.settings.intrasite_link_regex)
        parser.update(self, context)

    # FIXME should be cached I guess
    @reserved_property
    def static_links(self) -> set[Path]:
        """Discovered static links in the object.

        :return: Absolute paths to static links found in the object content and
        formatted fields.
        """
        parser = IntrasiteLinkParser(
            self.settings.intrasite_link_regex, valid_identifiers="static"
        )
        result = {link.target for link in parser.extract(self)}
        return result

    @reserved_property
    def extra_metadata(self) -> dict[str, str]:
        """User-defined metadata.

        This returns a mapping of copies of all user-defined metadata. It makes use of
        the `__extra_dataclass__attrs__` of dataclasses decorated with
        `seagull.utils.extra_dataclass`.

        As the return dictionary stores values, not references, editing it won't
        modify the actual attributes stored in the class. To edit the attributes, use
        `getattr` or the dot notation instead.

        :return: A dictionary of metadata attributes. If there is no user-defined
        metadata keys, it returns an empty dictionary.
        """
        if hasattr(self, "__extra_dataclass__attrs__"):
            return {k: getattr(self, k) for k in self.__extra_dataclass__attrs__}
        return {}

    @reserved_property
    def relative_source_path(self) -> Path:
        """Source path relative to the base path."""
        return self.source_path.relative_to(self.base_path)

    @reserved_property
    def jinja_context(self) -> dict[str, Any]:
        """Context dictionary for Jinja templates rendering.

        It is typically added to `seagull.Context` to create the rendering context for
        Jinja.
        """
        return {
            # The object can be accessed via the generic attribute "obj", or via its
            # type name
            "obj": self,
            self.__class__.__name__.lower(): self,
            "siteurl": self.relative_siteurl,
            "output_file": self.save_as,
        }

    @reserved_property
    def in_default_lang(self) -> bool:
        """Whether the object is in the default language."""
        return self.lang == self.settings.default_lang

    @reserved_property
    def relative_siteurl(self) -> str:
        """Relative site URL.

        If `RELATIVE_URLS` is `False`, this returns `SITEURL`. Otherwise, it returns the
        path to the site root, relative to the current object's output directory.
        """
        if not self.settings.relative_urls:
            return self.settings.siteurl
        return str(Path(".").relative_to(self.save_as.parent, walk_up=True))

    # FIXME implement comparison with a string
    def __lt__(self, other: Self) -> bool:
        """Seagull objects are sorted by title.

        Because this class is decorated with `functools.total_ordering`, the other
        comparison operators are automatically created.
        """
        return self.title < other.title

    def __str__(self) -> str:
        """The string representation of an object is its slug.

        This is useful for the `*_SAVE_AS` and `*_URL` settings, among other things.
        """
        return self.slug

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"<{class_name}: slug='{self.slug}', source_path='{self.source_path}'>"
