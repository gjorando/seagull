import logging
import shutil
from functools import partial
from typing import TYPE_CHECKING

from seagull.contents import Author, Category, Content, Tag, Taxonomy
from seagull.contents.content import ContentStatus
from seagull.context import Context
from seagull.generators import (
    ArticlesGenerator,
    DirectTemplatesGenerator,
    FeedGenerator,
    GranularArchivesGenerator,
    PagesGenerator,
    StaticGenerator,
    TaxonomyGenerator,
)
from seagull.log import error_with_paths, logger
from seagull.utils import Comparable, PluralFormatter

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from seagull.contents import SeagullObject
    from seagull.generators import Generator
    from seagull.settings import Settings


class Seagull:
    """The main seagull class."""

    def __init__(self, settings: Settings):
        """
        :param settings: Seagull settings.
        """
        self.settings: Settings = settings
        self.context: Context = Context()

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
        # Instantiate the generators
        generators: list[Generator] = [
            gcls(self.settings, self.context) for gcls in self.generator_classes
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

        # Prune the context from empty taxa
        self.context.prune_taxonomies()

        # Then, we link the translations together
        for g in generators:
            g.link_translations()

        # We sort the objects
        self._sort_context()

        # We update intrasite links for all objects
        for obj in self.context:
            obj.update_intrasite_links(self.context)

        # Now, we can write the output to disk
        for g in generators:
            g.generate_output()

        self._run_stats()

    def _sort_context(self) -> None:
        """Sort the objects in the context according to the `*_order_by` settings."""
        # Then, we sort every list of seagull objects
        for obj_class, objs in self.context.objects.items():
            # Get the setting for the type of object
            order_by_setting_key = f"{obj_class.__name__.lower()}_order_by"
            sort_key: Callable[[SeagullObject], Comparable]
            sort_key, reverse = getattr(
                self.settings, order_by_setting_key, (None, False)
            )
            # If a setting for this type exists, do the sorting
            if sort_key:
                self.context.sort_objects(obj_class, key=sort_key, reverse=reverse)

            # We sort the list of articles in taxonomies
            # FIXME better handling of sorting the sub-objects of individual objects
            if issubclass(obj_class, Taxonomy):
                obj: Taxonomy
                for obj in objs:
                    sort_key, reverse = self.settings.article_order_by
                    obj.articles.sort(key=sort_key, reverse=reverse)

    def _run_stats(self) -> None:
        """Display some stats about a run."""
        # Number of generated objects, per type
        for object_class, objs in self.context.objects.items():
            # For content objects, log by status
            if issubclass(object_class, Content):
                for status in ContentStatus:
                    if num_status := len(
                        list(filter(lambda c: c.status == status, objs))
                    ):
                        logger.info(
                            f"Processed {num_status} {status} "
                            f"{object_class.printable_name(num_status)}."
                        )
                continue
            logger.info(
                f"Processed {len(objs)} {object_class.printable_name(len(objs))}."
            )
        # Log failed source paths
        if self.context.failed_source_paths:
            error_with_paths(
                PluralFormatter().format(
                    "There {paths:plural,is,are} {len_paths} "
                    "failed file{paths:plural,s}.",
                    paths=self.context.failed_source_paths,
                    len_paths=len(self.context.failed_source_paths),
                ),
                paths=self.context.failed_source_paths,
            )

    @property
    def generator_classes(self) -> list[type[Generator]]:
        """Get the list of generator classes to run."""
        return [
            # Taxonomy generators must always come before content generators
            partial(TaxonomyGenerator, content_class=Category),
            partial(TaxonomyGenerator, content_class=Author),
            partial(TaxonomyGenerator, content_class=Tag),
            # Content generators
            ArticlesGenerator,
            PagesGenerator,
            # FeedGenerator must always come after content generators
            FeedGenerator,
            # DirectTemplatesGenerator must always come after content generators
            DirectTemplatesGenerator,
            GranularArchivesGenerator,
            # StaticGenerator must always come last
            StaticGenerator,
            partial(StaticGenerator, theme_static=True),
        ]
