from collections import defaultdict
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import define, field

from seagull.api.exceptions import InvalidObjectError, SkippedFileError
from seagull.api.objects import SeagullObject
from seagull.api.parsers import Parser
from seagull.api.utils import GeneratorPaths, object_class_field
from seagull.logging import logger

if TYPE_CHECKING:
    from collections.abc import Iterable


@define
class Generator[T: SeagullObject]:
    """Base generator class."""

    object_class: type[T] = object_class_field(SeagullObject)
    """Type of object created by the generator."""
    content_path: Path = field(converter=Path)
    """Content path to look for files."""
    output_path: Path = field(converter=Path)
    """Output directory."""
    valid_paths: set[Path | str] = field(
        converter=lambda paths: {Path(p) for p in paths}
    )
    """Valid paths to look for files (relative to base_path)."""
    excludes: set[Path | str] = field(
        factory=set, converter=lambda paths: {Path(p) for p in paths}
    )
    """Ignored paths (relative to base_path)."""
    objects: list[T] = field(factory=list, init=False)
    """Objects created by the generator."""

    def __call__(
        self, generator_paths: GeneratorPaths | None = None, /, **kwargs: object
    ) -> None:
        """Generate all the objects.

        :param generator_paths: If provided, a `GeneratorPaths` instance that is updated
        with the processed and failed source paths for this generator. All the source
        paths that were already in `generator_paths` are excluded from being
        processed again.
        :param kwargs: Default field values for the generated object.
        """
        if not generator_paths:
            generator_paths = GeneratorPaths()

        # First, we create the objects; we do not attempt to process source
        # paths that were already processed or failed by another generator
        for source_path in self.files().difference(generator_paths.all_paths):
            obj, success = self._generate_object(source_path, **kwargs)
            # Add the object to the list of generated objects
            if obj:
                self.objects.append(obj)
            # Record the source_path depending on whether generation was successful
            if success:
                generator_paths.processed.add(source_path)
            else:
                generator_paths.failed.add(source_path)

    def _generate_object(
        self, source_path: Path, **kwargs: object
    ) -> tuple[T | None, bool]:
        """Subroutine that generates an object based on a source path.

        :param source_path: Object source path to be fed to the parser.
        :param kwargs: Default field values for the generated object.
        :return: The object (or `None` if nothing was created), and a boolean on whether
        the processing was successful. `(None, True)` may be returned if the source path
        was skipped.
        """
        # Load the parser
        try:
            parser = self._get_parser(source_path.suffix)
        except KeyError:
            logger.warning(f"No suitable parser to read '{source_path}'.")
            return None, False
        # ... Then parse the file
        try:
            obj = parser.read(
                source_path,
                self.content_path,
                self.object_class,
                **kwargs,
            )
            logger.debug(
                f"Processed '{self.content_path / source_path}' into "
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

    def reset(self) -> None:
        """Ensure the generator is in a blank state."""
        # Remove all objects that may have been generated in a past run
        self.objects.clear()

    def write(self, **kwargs: object) -> None:
        """Save all generated objects.

        If the generator wasn't called first, this won't do anything.

        :param kwargs: Additional data.
        """
        for obj in self.objects:
            self._get_parser(obj.save_as.suffix).write(
                obj, output_path=self.output_path, **kwargs
            )
            logger.debug(f"Wrote '{self.output_path / obj.save_as}' on disk.")

    def files(self, ignore_patterns: Iterable[Path | str] | None = None) -> set[Path]:
        """Set of file paths that should be parsed.

        :param ignore_patterns: Optional ignore patterns.
        :return: A set of absolute paths.
        """
        ignore_patterns = ignore_patterns or []
        result = set()
        # Resolve relative paths relatively to the base path
        base_path = self.content_path
        # Group excluded paths by parent
        per_parent_exclude_paths = defaultdict(set)
        for ep in self.excludes:
            excluded_path = base_path / ep
            per_parent_exclude_paths[excluded_path.parent].add(excluded_path.name)
        for vp in self.valid_paths:
            valid_path = base_path / vp
            if valid_path.is_dir(follow_symlinks=True):  # Walk directories
                for current_directory, subdirectories, filenames in valid_path.walk(
                    follow_symlinks=True
                ):
                    # Do not walk into subdirectories that are excluded paths
                    excluded_subdirs = per_parent_exclude_paths[current_directory]
                    for subdir in reversed(subdirectories):
                        # Do not walk into globally ignored subdirectories
                        globally_ignored = any(
                            Path(subdir).full_match(pattern)
                            for pattern in ignore_patterns
                        )
                        if subdir in excluded_subdirs or globally_ignored:
                            subdirectories.remove(subdir)
                    rel_directory = current_directory.relative_to(self.content_path)
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

    @staticmethod
    def _get_parser(extension: str) -> Parser:
        """Get the parser that should be used for a given extension.

        This is used by `Generator.__call__` to get the appropriate parser object. It is
        overridden by `AssetsGenerator` to always retrieve the static parser.

        :param extension: Extension of the file to verify.
        :return: A `Parser` instance.
        """
        return Parser.from_extension(extension)()

    @staticmethod
    def _is_valid_extension(extension: str) -> bool:
        """Verify that an extension is valid for the current generator.

        This is used by `Generator.files` to assert if a file should be included. It is
        overridden by `AssetsGenerator` to always return `True`.

        :param extension: Extension of the file to verify.
        :return: `True` if the file has a valid extension.
        """
        # The base generator accepts any extension associated to a parser
        try:
            Parser.from_extension(extension)
            return True
        except KeyError:
            return False
