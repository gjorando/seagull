from itertools import product
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from seagull.contents import DirectTemplate
from seagull.exceptions import SeagullError
from seagull.generators.generator import Generator
from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable


class DirectTemplatesGenerator[T: DirectTemplate](Generator):
    """Generator for direct templates, such as 'index' or 'categories'."""

    content_class: type[T] = DirectTemplate

    def _create_objects(self) -> list[T]:
        """Create the objects for each direct template.

        This generator works a bit differently from the other ones, as it doesn't use
        content files to create objects. Instead, it creates one generic seagull object
        for each template listed in `DIRECT_TEMPLATES`. As such, this generator doesn't
        use a `Reader` object.
        """
        existing_save_as = [o.save_as for o in self.context]
        all_content = []
        for template_name, template_lang in product(
            self.settings.direct_templates,
            (self.settings.default_lang, *self.settings.langs.keys()),
        ):
            try:
                obj = self.content_class(
                    settings=self.settings,
                    lang=template_lang,
                    template=template_name,
                )
            except SeagullError:
                logger.exception(
                    f"Couldn't process direct template '{template_name}'.",
                    exc_info=logger.level == logging.DEBUG,
                )
                continue
            # Avoid overriding previously generated content
            if obj.save_as in existing_save_as:
                logger.debug(f"Skipped direct template '{template_name}'.")
                continue
            all_content.append(obj)
        return all_content

    @property
    def valid_paths(self) -> Iterable[Path]:
        """Unused property."""
        # FIXME maybe having unused property means we should have a base generic
        # Generator class, and all others Generator subclasses should instead inherit
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
