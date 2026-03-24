from pathlib import Path
import re
from typing import TYPE_CHECKING, NamedTuple, cast
import urllib.parse
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from bs4 import Tag

    from seagull.contents import SeagullObject, Taxonomy
    from seagull.context import Context


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

    VALID_ATTRS = (
        "href",
        "src",
        "poster",
        "data",
        "cite",
        "formaction",
        "action",
        "content",
    )
    """HTML attributes that can contain an intrasite link."""
    PATH_IDENTIFIERS = ("static", "filename", "attach")
    """Link identifiers that take paths."""

    def __init__(
        self,
        intrasite_link_regex: str,
        valid_identifiers: str | tuple[str] | None = None,
    ):
        """Initialize the parser.

        :param intrasite_link_regex: Regex for identifying the intrasite link
        identifier.
        :param valid_identifiers: Optional identifier or tuple of identifiers to filter
        links.
        """
        self.regex_str: str = rf"{intrasite_link_regex}(?P<target>.*)"
        self.regex: re.Pattern = re.compile(self.regex_str, re.VERBOSE)
        if not valid_identifiers:
            valid_identifiers = None
        elif isinstance(valid_identifiers, str):
            valid_identifiers = (valid_identifiers,)
        self.valid_identifiers: tuple[str] | None = valid_identifiers

    def _has_valid_attr(self, tag: Tag) -> bool:
        """Filter out tags that don't have a valid link attribute."""
        return any(tag.has_attr(attr) for attr in self.VALID_ATTRS)

    def _object_valid_attrs(
        self, obj: SeagullObject, *, update_field: bool = False
    ) -> Iterable[tuple[Tag, str, str]]:
        """Iterate over every valid attribute of all HTML tags in the object.

        Both the content of the object and the formatted fields are searched for.

        :param obj: A seagull object.
        :param update_field: If `True` each field is updated once all its attributes
        have been iterated over. This means that the `Tag` object can be updated, it
        will be reflected in the value of the field.
        :return: Iterate a tuple of `(bs4_tag, attr_name, attr_value)`.
        """
        # The field could be extra metadata, so we work on obj.as_dict()
        obj_dict = obj.as_dict()
        for field_name in [*obj.settings.formatted_fields, "content"]:
            # Soup time if the field exists in the object
            if value := obj_dict.get(field_name):
                soup = BeautifulSoup(value, features=obj.settings.html_parser)
                # Look for all tags with a valid link attribute
                for html_tag in soup(self._has_valid_attr):
                    # For every link attribute
                    for attr_name, attr_value in html_tag.attrs.items():
                        # Yield if the attribute is an accepted attribute
                        if attr_name in self.VALID_ATTRS:
                            yield html_tag, attr_name, attr_value
                # And we update the content of the field if required
                if update_field:
                    # If we are updating an extra field
                    if field_name in obj.extra_metadata:
                        obj.extra_metadata[field_name] = str(soup)
                    # Otherwise, we are updating a regular field
                    else:
                        setattr(obj, field_name, str(soup))

    def extract(self, obj: SeagullObject) -> set[IntrasiteLink]:
        """Retrieve the path intrasite links.

        :param obj: A seagull object. Formatted fields are parsed as well.
        :return: A set of intrasite links.
        """
        links = set()
        # Retrieve the links from all formatted fields, including the content itself
        for _, _, attr_value in self._object_valid_attrs(obj):
            # Go to the next attribute if we don't have a match
            if not (match := self.regex.match(attr_value)):
                continue
            # If we have a list of valid types, skip links of another type
            what = match.group("what").lower().strip()
            if self.valid_identifiers and what not in self.valid_identifiers:
                continue
            # Convert %xx escapes back to unicode
            target = urllib.parse.unquote(match.group("target"))
            # If the target is a path, make it absolute
            if what in self.PATH_IDENTIFIERS:
                target = Path(target)
                # If it has a leading slash path, it is rooted in the base path;
                # otherwise, it is relative to the source_path folder
                target = (
                    obj.base_path
                    / (
                        # path.relative_to("/") if path.is_relative_to("/") removes
                        # the leading slash
                        target.relative_to("/")
                        if target.is_relative_to("/")
                        else obj.relative_source_path.parent / target
                    )
                ).resolve()
            link = IntrasiteLink(raw_link=attr_value, identifier=what, target=target)
            links.add(link)
        return links

    @staticmethod
    def _target_link_from_source_path(
        context: Context, identifier: str, target: str | Path
    ) -> str | None:
        """Get the target link from content/static file.

        :param context: Shared context.
        :param identifier: An identifier among `self.path_identifiers`.
        :param target: The source path of the target.
        :return: The target link, or `None` if there is no content or static file for
        this source path.
        """
        context_key = (
            "generated_content" if identifier == "filename" else "static_content"
        )
        if not (target_obj := getattr(context, context_key).get(target)):
            return None
        return target_obj.url

    @staticmethod
    def _target_link_from_taxon(
        taxa: list[Taxonomy],
        taxon_name: str | Path,
    ) -> str | None:
        """Get the target link from a taxonomy.
        :param taxa: List of taxonomies to search.
        :param taxon_name: The name of the taxon.
        :return: The target link, or `None` if there is no taxonomy with this type and
        name.
        """
        # FIXME translations
        # Try fetching the taxon by name
        for taxon in taxa:
            if taxon.name == taxon_name:
                return taxon.url
        # Then try fetching by slug FIXME
        for taxon in taxa:
            if taxon.slug == taxon_name:
                return taxon.url
        return None

    def update(self, obj: SeagullObject, context: Context) -> None:
        """Update intrasite links using data from a `Context` object.

        :param obj: A seagull object. Formatted fields are parsed as well.
        :param context: Shared context to use for link replacement.
        """
        # We extract our list of links
        links = self.extract(obj)
        # Then, we create a replacement for each intrasite reference
        parsed_links: dict[str, str] = {}
        for raw_link, identifier, target in links:
            match identifier:
                case _ if identifier in self.PATH_IDENTIFIERS:  # Static/content files
                    if not (
                        target_path := self._target_link_from_source_path(
                            context, identifier, target
                        )
                    ):
                        logger.warning(
                            f"'{raw_link}': unknown content in '{obj.source_path}'."
                        )
                        continue
                case "index":  # Index direct template
                    # FIXME allow for any direct template
                    target_path = obj.settings.index_url
                case _:  # Taxonomies, or unknown identifier
                    # TODO this could enable us to do something like {article}<article_name>
                    # Try getting the appropriate list of taxa
                    try:
                        taxa = context.get_by_type(identifier)
                    except KeyError:
                        logger.warning(
                            f"'{identifier}': unknown link identifier in "
                            f"'{obj.source_path}'."
                        )
                        continue
                    if not (target_path := self._target_link_from_taxon(taxa, target)):
                        logger.warning(
                            f"'{target}': unknown {identifier.lower()} in "
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
        for html_tag, attr_name, attr_value in self._object_valid_attrs(
            obj, update_field=True
        ):
            # If the link is in our dictionary of parsed links...
            if attr_value in parsed_links:
                # We replace the link with its parsed version
                html_tag[attr_name] = parsed_links[attr_value]
