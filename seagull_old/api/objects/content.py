from pathlib import Path
from typing import TYPE_CHECKING, Self
import urllib.parse

from attrs import field
from bs4 import BeautifulSoup

from seagull.api.utils import LINK_ATTRS, IntrasiteLink, post_generate, seagull_object
from seagull.logging import logger

from .seagull_object import SeagullObject

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@seagull_object
class Content(SeagullObject):
    """Seagull object with content data."""

    content: str = field(repr=False)
    """HTML content for the object."""
    template: str = field()
    """Name of a Jinja template to use to render the object."""
    formatted_fields: list[str] = field(factory=list)
    """Fields that are formatted HTML."""

    @template.default
    def _default_template(self) -> str:
        return self.printable_name(1, "_")

    @post_generate
    def parse_intrasite_links(
        self,
        objs: Mapping[type[Self], Iterable[Self]],
        *,
        # FIXME with post_generate, how can we pass these settings?
        site_url: str = "/",
        relative_url: bool = True,
    ) -> None:
        """Parse intrasite links.

        This method looks for intrasite link placeholders in the HTML fields of the
        object, and converts them to actual URLs.

        :param objs: All generated objects, mapped by type.
        :param site_url: Site url to use for absolute URLs. Ignored if `relative_url` is
        `True`.
        :param relative_url: Whether to output a relative or absolute URL.
        """
        all_objects = [o for oo in objs.values() for o in oo]
        # This is required to ensure the URL is rooted
        if not site_url.endswith("/"):
            site_url = f"{site_url}/"

        for link in self.intrasite_links:
            for obj in all_objects:
                # If we have a matching object, parse the target url
                if not obj.matches_intrasite_link(link, self):
                    continue
                if relative_url:
                    target = str(Path(self.site_root) / obj.url)
                else:
                    target = urllib.parse.urljoin(site_url, obj.url)
                # And update the HTML tag
                link.tag[link.attr] = target
                break
            else:
                logger.warning(
                    f"Intrasite link '{link}' doesn't match any seagull object."
                )

    @property
    def intrasite_links(self) -> Iterable[IntrasiteLink]:
        """Iterate intrasite links in the content object.

        It goes over every HTML attribute of every formatted field that contains a valid
        intrasite identifier.

        :return: Yields a BeautifulSoup `Tag` object and an `IntrasiteLink` object for
        every attribute. The tag can be edited, the object field from which it comes
        from will be updated accordingly.
        """
        # For each existing formatted field
        for field_name, field_value in (
            (k, v)
            # The field could be extra metadata, so we work on obj.as_dict()
            for k, v in self.as_dict().items()
            # Retain fields that are formatted fields, ensure they're strings
            if k in [*self.formatted_fields, "content"] and isinstance(v, str)
        ):
            field_value: str
            # Look for all tags with a valid link attribute
            soup = BeautifulSoup(field_value, features="html.parser")
            for html_tag in soup(
                lambda tag: any(tag.has_attr(attr) for attr in LINK_ATTRS)
            ):
                # For every link attribute on this tag
                for attr_name, attr_value in (
                    (k, str(v)) for k, v in html_tag.attrs.items() if k in LINK_ATTRS
                ):
                    # Yield only if the link was parsed as an intrasite link
                    try:
                        yield IntrasiteLink.from_string(
                            attr_value,
                            tag=html_tag,
                            attr=attr_name,
                        )
                    except ValueError:
                        continue
                # TODO this is unpredictable if we break from the iteration, as the attribute won't be updated; we should create an Iterator class instead
                # And we update the content of the field
                setattr(self, field_name, str(soup))

    @property
    def jinja_context(self) -> dict[str, object]:
        """Jinja context for rendering content."""
        obj_type = self.printable_name(1, "_")
        obj_dict = self.as_dict()
        return {
            "obj_type": obj_type,
            obj_type: self,
            "obj": obj_dict,
        }
