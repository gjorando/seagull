from collections import defaultdict
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import define, field

from seagull.exceptions import InvalidObjectError, SkippedFileError
from seagull.logging import logger
from seagull.objects import BaseObject
from seagull.readers import BaseReader

if TYPE_CHECKING:
    from collections.abc import Iterable

    from attrs import Attribute


@define(kw_only=True)
class Generator[T: BaseObject]:
    """Default generator class."""

    object_class: type[T] = field()
    """Type of object created by the generator."""
    valid_paths: set[Path | str] = field(
        converter=lambda paths: {Path(p) for p in paths}
    )
    """Valid path patterns to look for files.

    These patterns are relative to a content path provided in the `__call__` method."""
    excludes: set[Path | str] = field(
        factory=set, converter=lambda paths: {Path(p) for p in paths}
    )
    """Ignored paths (relative to base_path)."""
    enabled: bool = field(default=True, repr=False)
    """Whether to enable the generator."""

    @object_class.validator
    def _attrs_object_class_validator(self, attribute: Attribute, value: type) -> None:
        if not (isinstance(value, type) and issubclass(value, BaseObject)):
            raise ValueError(
                f"'{attribute.name}' must be a subtype of 'seagull.objects.BaseObject'"
            )

    def __call__(
        self,
        content_path: Path,
        processed_paths: dict[Path, bool] | None = None,
        /,
        *,
        default_values: dict[str, object] | None = None,
    ) -> list[T]:
        """Generate all the objects.

        :param content_path: Base path to use as the content path.
        :param processed_paths: If provided, a dictionary mapping processed source paths
        to whether they were successfully processed.
        :param default_values: Default field values for the generated object.
        :return: The list of generated objects. If the generator is disabled, an empty
        list is returned.
        """
        if not self.enabled:
            return []
        if processed_paths is None:
            processed_paths = {}
        default_values = default_values or {}
        objects = []
        # First, we create the objects; we do not attempt to process source
        # paths that were already processed or failed by another generator
        for source_path in self.files(content_path).difference(processed_paths):
            obj, success = self._generate_object(
                content_path,
                source_path,
                default_values=default_values,
            )
            # Add the object to the list of generated objects
            if obj:
                objects.append(obj)
            # Record the source_path depending on whether generation was successful
            processed_paths[source_path] = success
        return objects

    def _generate_object(
        self,
        base_path: Path,
        source_path: Path,
        /,
        *,
        default_values: dict[str, object],
    ) -> tuple[T | None, bool]:
        """Subroutine that generates an object based on a source path.

        :param base_path: Base path to use as the content path.
        :param source_path: Object source path to be fed to the parser (relative to
        `base_path`).
        :param default_values: Default field values for the generated object.
        :return: The object (or `None` if nothing was created), and a boolean on whether
        the processing was successful. `(None, True)` may be returned if the source path
        was skipped.
        """
        # Pick the appropriate reader
        try:
            reader = self._get_reader(source_path.suffix)
        except ValueError:
            logger.warning(f"No suitable reader for '{source_path}'.")
            return None, False
        # ... Then parse the file
        try:
            obj = reader(
                self.object_class,
                base_path / source_path,
                default_values={"base_path": base_path} | default_values,
            )
            logger.debug(
                f"Processed '{base_path / source_path}' into "
                f"{self.object_class.printable_name()} '{obj.name}'."
            )
            return obj, True
        # If the file was skipped, return no object but mark the
        # source path as successfully processed
        except SkippedFileError:
            logger.info(f"Skipped '{source_path}'.")
            return None, True
        # If the file is invalid, return no object and mark the
        # source path as failed
        except InvalidObjectError:
            logger.exception(
                f"Couldn't process '{source_path}'.",
                exc_info=logger.level == logging.DEBUG,
            )
            return None, False

    def files(
        self,
        base_path: Path,
        ignore_patterns: Iterable[Path | str] | None = None,
    ) -> set[Path]:
        """Set of file paths that should be parsed.

        :param base_path: Base path to use as the content path.
        :param ignore_patterns: Optional ignore patterns.
        :return: A set of absolute paths.
        """
        # By default, we do not walk into hidden directories that
        # aren't explicitly set in self.valid_paths
        if ignore_patterns is None:
            ignore_patterns = ["**/.*"]
        ignore_patterns = set(ignore_patterns)
        result = set()
        # Group excluded paths by parent
        per_parent_exclude_paths = defaultdict(set)
        for ep in self.excludes:
            excluded_path = base_path / ep
            per_parent_exclude_paths[excluded_path.parent].add(excluded_path.name)
        # Go through each valid path for the generator
        for vp in self.valid_paths:
            valid_path = base_path / vp
            # If the valid path is a directory, walk it
            if valid_path.is_dir(follow_symlinks=True):
                for current_directory, subdirectories, filenames in valid_path.walk(
                    follow_symlinks=True
                ):
                    # We remove from the walk subdirs that are excluded by self.excludes
                    excluded_subdirs = per_parent_exclude_paths[current_directory]
                    for subdir in reversed(subdirectories):
                        # We do not walk into globally ignored subdirs either
                        globally_ignored = any(
                            Path(subdir).full_match(pattern)
                            for pattern in ignore_patterns
                        )
                        if subdir in excluded_subdirs or globally_ignored:
                            subdirectories.remove(subdir)
                    rel_directory = current_directory.relative_to(base_path)
                    # Add each source path, if it is not a globally
                    # ignored file, and if it has a valid extension
                    for filename in filenames:
                        # The pattern matching is done relatively to the base path
                        rel_path = rel_directory / filename
                        globally_ignored = any(
                            rel_path.full_match(pattern) for pattern in ignore_patterns
                        )
                        if not globally_ignored and self._is_valid_extension(
                            rel_path.suffix
                        ):
                            result.add(rel_path)
            elif valid_path.exists():  # Directly add a single file if it exists
                result.add(vp)
        return result

    def _get_reader(self, extension: str | None) -> BaseReader:
        """Get the reader that should be used for a given extension.

        This is used by `Generator.__call__` to get the appropriate reader object.

        :param extension: Extension of the file to verify.
        :return: A `BaseReader` instance.
        :raise ValueError: If there is no reader for the extension.
        """
        return BaseReader.from_extension(extension)

    def _is_valid_extension(self, extension: str) -> bool:
        """Verify that an extension is valid for the current generator.

        This is used by `Generator.files` to assert if a file should be included.

        :param extension: Extension of the file to verify.
        :return: `True` if the file has a valid extension.
        """
        # The base generator accepts any extension associated to a reader
        try:
            self._get_reader(extension)
            return True
        except KeyError:
            return False
