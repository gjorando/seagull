import logging
from pathlib import Path
from typing import TYPE_CHECKING

from seagull.contents import SeagullObject
from seagull.exceptions import SeagullError
from seagull.generators.generator import Generator
from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable


class DirectTemplateGenerator[T: SeagullObject](Generator):
    """Generator for direct templates, such as 'index' or 'categories'."""

    content_class: type[T] = SeagullObject

    def add_object_to_context(self, obj: T) -> None:
        pass

    def _create_objects(self) -> list[T]:
        """Create the objects for each direct template.

        This generator works a bit differently from the other ones, as it doesn't use
        content files to create objects. Instead, it creates one generic seagull object
        for each template listed in `DIRECT_TEMPLATES`. As such, this generator doesn't
        use a `Reader` object.
        """
        all_content = []
        # FIXME maybe actually delegate the object creation to a DirectTemplateReader?
        # TODO translations
        # TODO pagination
        # TODO maybe a dedicated seagull object for direct templates
        for template_name in self.settings.direct_templates:
            save_as = getattr(
                self.settings,
                f"{template_name.lower()}_save_as",
                Path(f"{template_name}.html"),
            )
            url = (
                getattr(self.settings, f"{template_name.lower()}_url", str(save_as))
                or "."
            )
            try:
                obj = SeagullObject(
                    settings=self.settings,
                    title=template_name,
                    # FIXME slug
                    slug=f"direct-template-{template_name}",
                    lang=self.settings.default_lang,
                    save_as=save_as,
                    url=url,
                    template=template_name,
                )
            except SeagullError:
                logger.exception(
                    f"Couldn't process direct template '{template_name}'.",
                    exc_info=logger.level == logging.DEBUG,
                )
                continue
            all_content.append(obj)
        return all_content

    @property
    def valid_paths(self) -> Iterable[Path]:
        """Unused property."""
        # FIXME maybe having unused property means we should have a base generic
        # Generator class, and all others Generator subclases should instead inherit
        # from a FileReaderGenerator or something?
        return []

    @property
    def excluded_paths(self) -> Iterable[Path]:
        """Unused property."""
        return []

    @property
    def base_path(self) -> Path:
        """Unused property."""
        return Path()
