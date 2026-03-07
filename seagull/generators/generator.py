import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from seagull.contents import SeagullObject
from seagull.exceptions import InvalidObject, SkippedFileException
from seagull.log import logger
from seagull.readers import Reader
from seagull.writers import Writer

if TYPE_CHECKING:
    from collections.abc import Iterable

    from seagull.context import Context
    from seagull.settings import Settings


class Generator[T: SeagullObject](ABC):
    """Abstract base generator class.

    A `Generator` object is dedicated to generating a specific type of object.
    """

    content_class: type[T] = SeagullObject

    def __init__(self, settings: Settings, context: Context):
        self.settings = settings
        self.context = context
        # Record generated content, sorted by status
        self.all_content: list[T] = []
        self.original_content: list[T] = []

    def _create_objects(self) -> list[T]:
        """Create the objects.

        :return: A list of generated seagull objects.
        """
        all_content = []
        for source_path in self.files:
            log_path = source_path.relative_to(self.base_path)
            # Parse the file
            try:
                obj: T = self._get_reader(source_path).read_file(
                    source_path,
                    self.content_class,
                    self.context,
                    base_path=self.base_path,
                )
            except SkippedFileException:
                # If the file was skipped, continue with the next file
                logger.debug(f"Skipped '{log_path}'.")
                continue
            except InvalidObject:
                # If the file is invalid, log the error and continue with the next file
                logger.exception(
                    f"Couldn't process '{log_path}'.",
                    exc_info=logger.level == logging.DEBUG,
                )
                # We also mark the source path as failed
                self._add_failed_to_context(source_path)
                continue
            all_content.append(obj)
        return all_content

    def _get_reader(self, source_path: Path) -> Reader:
        """Retrieve the appropriate reader, given a source path.

        :param source_path: Source path of the file to parse.
        :return: A `Reader` instance.
        """
        return Reader.from_extension(self.settings, source_path.suffix)

    def _get_writer(self, obj: T) -> Writer:
        """Retrieve the appropriate writer for an object.

        :param obj: Seagull object to write.
        :return: A `Writer` instance.
        """
        return Writer.from_extension(self.settings, obj.save_as.suffix)

    def _add_failed_to_context(self, source_path: Path):
        """Record a source file path that a generator failed to process.

        :param source_path: Source path.
        """
        self.context.failed_source_paths.append(source_path)

    def _link_translations(self, objs: list[T]) -> list[T]:
        """Link translations.

        :param objs: Objects to process.
        :return: List of objects that aren't translations
        """
        class_name = self.content_class.__name__.lower()
        # Get the key for the groupby operation
        translation_id = getattr(self.settings, f"{class_name}_translation_id", None)
        # Get the order_by setting (fallback to ordering by title)
        sort_key, reverse = getattr(
            self.settings, f"{class_name}_order_by", (lambda o: o.title, False)
        )

        # Link translations together
        origs = self.content_class.link_translations(
            objs, translation_id=translation_id
        )
        # Sort original content
        origs.sort(key=sort_key, reverse=reverse)
        return origs

    def _update_context(self, objs: list[T]):
        """Update the shared context.

        :param objs: Objects to register in the context.
        """
        for obj in objs:
            # Record the file into the context
            self.add_object_to_context(obj)
            # Record the static links in the object as well
            self.context.static_links |= obj.static_links

    def generate_context(self):
        """Create the context of a generator.

        The default implementation calls `_create_objects`, `_link_translations` and
        `_update_context`, in this order.
        """
        # First, we create the objects
        self.all_content.extend(self._create_objects())
        # Next, we link the translations together
        self.original_content.extend(self._link_translations(self.all_content))
        # Finally, we update the context
        self._update_context(self.all_content)

    def generate_output(self):
        """Generate the output of a generator."""
        obj: T
        for obj in self.all_content:
            writer = self._get_writer(obj)
            writer.write_file(obj, self.context)

    def has_valid_extension(self, path: Path) -> bool:
        """Verify that a file has a valid extension for the current generator.

        :param path: Path of the file to verify.
        :return: `True` if the file has a valid extension.
        """
        # The default implementation checks if there exists a reader for the file
        # extension
        return path.suffix[1:] in (
            extension
            for reader in Reader.all_readers()
            for extension in reader.file_extensions
        )

    @property
    def files(self) -> set[Path]:
        """Set of file paths that should be parsed.

        :return: A set of absolute paths.
        """
        result = set()
        ignores = self.settings.ignore_files
        # Resolve relative paths relatively to the base path
        base_path = self.base_path
        # Group excluded paths by parent
        per_parent_exclude_paths = defaultdict(set)
        for excluded_path in self.excluded_paths:
            excluded_path = base_path / excluded_path
            per_parent_exclude_paths[excluded_path.parent].add(excluded_path.name)
        for valid_path in self.valid_paths:
            valid_path = base_path / valid_path
            if valid_path.is_dir(follow_symlinks=True):  # Walk directories
                for current_directory, subdirectories, filenames in valid_path.walk(
                    follow_symlinks=True
                ):
                    # Do not walk into subdirectories that are excluded paths
                    excluded_subdirs = per_parent_exclude_paths[current_directory]
                    for subdir in reversed(subdirectories):
                        # Do not walk into globally ignored subdirectories
                        globally_ignored = any(
                            Path(subdir).full_match(pattern) for pattern in ignores
                        )
                        if subdir in excluded_subdirs or globally_ignored:
                            subdirectories.remove(subdir)
                    rel_directory = current_directory.relative_to(self.base_path)
                    # Add each absolute file path, if it is not a globally ignored file,
                    # and if it has a valid extension
                    for filename in filenames:
                        file_path = current_directory / filename
                        # The pattern matching is done relatively to the base path
                        rel_path = rel_directory / filename
                        globally_ignored = any(
                            rel_path.full_match(pattern) for pattern in ignores
                        )
                        if not globally_ignored and self.has_valid_extension(file_path):
                            result.add(file_path)
            elif valid_path.exists():  # Directly add a single file if it exists
                result.add(valid_path)
        return result

    @property
    @abstractmethod
    def valid_paths(self) -> Iterable[Path]:
        """A property that yields the valid paths to look for files.

        :return: An iterable of paths relative to `self.base_path`.
        """

    @property
    @abstractmethod
    def excluded_paths(self) -> Iterable[Path]:
        """A property that yields the ignored paths.

        :return: An iterable of paths relative to `self.base_path`.
        """

    @abstractmethod
    def add_object_to_context(self, obj: T):
        """Add an object to the shared context.

        :param obj: Content to store.
        """

    @property
    @abstractmethod
    def base_path(self) -> Path:
        """Base path for the generator to look into.

        :return: A path that's used as the base for all files processed by the
        generator.
        """

    def __str__(self):
        return self.__class__.__name__
