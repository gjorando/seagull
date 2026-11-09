from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Self
import urllib.parse

from attrs import converters, field
from bs4 import BeautifulSoup

from seagull.logging import logger
from seagull.theme import Theme
from seagull.utils import (
    IntrasiteLink,
    JinjaRenderable,
    datetime_converter,
)

from .base_object import BaseObject
from .utils import post_generate, seagull_object

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from seagull.typeshed import StrPath


@seagull_object
class Content(BaseObject, JinjaRenderable):
    """Seagull object with HTML content data.

    These objects are rendered using Jinja."""

    content: BeautifulSoup = field(
        converter=partial(BeautifulSoup, features="html.parser"),
        repr=False,
    )
    """HTML content for the object."""
    modified: datetime | None = field(
        default=None, converter=converters.optional(datetime_converter)
    )
    """Last modified date of the object."""
    template: str = field()
    """Name of a Jinja template to use to render the object."""
    theme: Theme = field(repr=lambda x: f"'{x.name}'")
    """Theme to use for rendering the object."""
    # TODO Find a nice way to soupify formatted fields on instantiation
    formatted_fields: list[str] = field(factory=list)
    """Fields that are formatted HTML."""

    @template.default
    def _attrs_default_template(self) -> str:
        return self._default_template()

    @theme.default
    def _attrs_default_theme(self) -> Theme:
        return Theme.load("simple")

    def _default_template(self) -> str:
        return self.printable_name(1, "_")

    @post_generate
    def parse_intrasite_links(
        self,
        objs: Mapping[type[Self], Iterable[Self]],
    ) -> None:
        """Parse intrasite links.

        This method looks for intrasite link placeholders in the HTML fields of the
        object, and converts them to actual URLs.

        :param objs: All generated objects, mapped by type.
        """
        all_objects = [o for oo in objs.values() for o in oo]
        for link in self.intrasite_links:
            for obj in all_objects:
                # If we have a matching object, parse the target url
                if not obj.matches_intrasite_link(link, self):
                    continue
                if self.site_url is None:  # Relative URL
                    target = str(Path(self.site_root) / obj.url)
                else:  # Absolute URL
                    target = urllib.parse.urljoin(self.site_url, obj.url)
                # And update the HTML tag
                link.tag[link.attr] = target
                break
            else:
                logger.warning(
                    f"Intrasite link '{link}' doesn't match any seagull object."
                )

    def _render_content(self, jinja_context: dict[str, object]) -> str:
        """Render the object as HTML.

        :param jinja_context: Base Jinja context.
        """
        return self.theme.render(
            self,
            # TODO move that to the Theme object, allow to load an installed theme/path and override some values
            # template_overrides=template_overrides,
            jinja_context=jinja_context,
        )

    def save(self, output_path: StrPath, **kwargs: object) -> None:
        output_path = output_path / self.save_as
        # mkdir -p the output directory if required
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)
        # If the output path is a directory, delete it first
        elif output_path.is_dir():
            output_path.unlink()
        with open(output_path, "w") as fp:
            fp.write(self._render_content(kwargs))

    @property
    def jinja_context(self) -> dict[str, object]:
        obj_type = self.printable_name(1, "_")
        obj_dict = self.as_dict()
        return {
            "obj_type": obj_type,  # Name of the type of object
            obj_type: obj_dict,  # Object dictionary, mapped to the name of its type
            "obj": obj_dict,  # Object dictionary, mapped to 'obj'
        }

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
            if k in [*self.formatted_fields, "content"]
            and isinstance(v, (str, BeautifulSoup))
        ):
            # Look for all tags with a valid link attribute
            if isinstance(field_value, str):
                soup = BeautifulSoup(field_value, features="html.parser")
            else:
                soup = field_value
            soup: BeautifulSoup
            for html_tag in soup(
                lambda tag: any(tag.has_attr(attr) for attr in IntrasiteLink.LINK_ATTRS)
            ):
                # For every link attribute on this tag
                for attr_name, attr_value in (
                    (k, str(v))
                    for k, v in html_tag.attrs.items()
                    if k in IntrasiteLink.LINK_ATTRS
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
                # And we update the content of the field
                if not isinstance(field_value, BeautifulSoup):
                    # TODO this is unpredictable if we break from the iteration, as the attribute won't be updated; we should create an Iterator class instead (or this would be fixed if we converted formatted fields to soup)
                    setattr(self, field_name, str(soup))
