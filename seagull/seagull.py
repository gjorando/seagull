import logging
import shutil
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING

from seagull.contents import Author, Category, Tag
from seagull.context import Context
from seagull.generators import (
    ArticlesGenerator,
    DirectTemplateGenerator,
    PagesGenerator,
    StaticGenerator,
    TaxonomyGenerator,
    ThemeStaticGenerator,
)
from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from seagull.generators import Generator
    from seagull.settings import Settings


class Seagull:
    """The main seagull class."""

    def __init__(self, settings: Settings):
        self.settings: Settings = settings
        self.generator_classes: list[type[Generator]] = [
            # Taxonomy generators must always come before content generators
            partial(TaxonomyGenerator, content_class=Category),
            partial(TaxonomyGenerator, content_class=Author),
            partial(TaxonomyGenerator, content_class=Tag),
            ArticlesGenerator,
            PagesGenerator,
            # DirectTemplateGenerator must always come after content generators
            DirectTemplateGenerator,
            # StaticGenerator must always come last
            StaticGenerator,
            ThemeStaticGenerator,
        ]

    def _clear_output_dir(self, *, dry_run: bool = False) -> None:
        """Delete the output directory according to the retention policy.

        :param dry_run: If `True`, the files that would be deleted are logged but no
        actual deletion takes place.
        """

        def _dry_run[**P](
            func: Callable[P, None], target: Path, *args: P.args, **kwargs: P.kwargs
        ) -> None:
            if dry_run:
                logger.debug(f"Would delete '{target}'.")
            else:
                func(*args, **kwargs)

        # Delete the output directory only if DELETE_OUTPUT_DIRECTORY is True
        if not self.settings.delete_output_directory:
            return
        output_path = self.settings.output_path
        # Simply return if the output path doesn't exist yet
        if not output_path.exists():
            return
        logger.debug(f"Deleting output directory '{output_path}'.")
        # Try removing a file
        if not output_path.is_dir():
            try:
                _dry_run(output_path.unlink, output_path, missing_ok=True)
            except OSError:
                logger.exception(
                    f"Unable to delete the file '{output_path.name}'.",
                    exc_info=logger.level == logging.DEBUG,
                )
            return
        # Otherwise, clear the output path contents
        for child in output_path.iterdir():
            # But not if the file/directory is in the retention list
            if child.relative_to(output_path) in self.settings.output_retention:
                logger.debug(
                    f"'{child.name}' is in 'OUTPUT_RETENTION', won't be deleted."
                )
                continue
            # The delete operation is different if we have a directory or a file
            if child.is_dir():
                delete_call = partial(shutil.rmtree, child)
                file_type = "directory"
            else:
                delete_call = child.unlink
                file_type = "file"
            # Try to delete the child
            try:
                _dry_run(delete_call, child)
            except OSError:
                child_dir = child.relative_to(output_path.parent)
                logger.exception(
                    f"Unable to delete the {file_type} '{child_dir}'.",
                    exc_info=logger.level == logging.DEBUG,
                )

    def run(self) -> None:
        """Main generation sequence."""
        # Create a new shared context
        context = Context()
        # Instantiate the generators
        generators: list[Generator] = [
            gcls(self.settings, context) for gcls in self.generator_classes
        ]

        # Don't attempt clearing the output directory if it contains the content dir
        if self.settings.path.is_relative_to(self.settings.output_path):
            logger.warning(
                "The output directory contains the content directory;"
                " 'DELETE_OUTPUT_DIR' cannot be applied."
            )
        else:
            self._clear_output_dir()

        # First, we run all generators
        for g in generators:
            g.generate_context()

        # Then, we update intrasite links
        for obj in chain(
            context.generated_content.values(), *context.taxonomies.values()
        ):
            obj.update_intrasite_links(context)

        # Now, we can write the output to disk
        for g in generators:
            g.generate_output()
