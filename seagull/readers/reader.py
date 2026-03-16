import re
from abc import ABC, abstractmethod
from dataclasses import fields
from datetime import datetime
from itertools import chain
from typing import TYPE_CHECKING, Any, ClassVar, Self

from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from seagull.contents import SeagullObject
    from seagull.context import Context
    from seagull.settings import Settings


class Reader(ABC):
    """Abstract base reader class.

    A `Reader` object creates seagull objects from a file."""

    enabled: ClassVar[bool] = True
    file_extensions: ClassVar[list[str | None]] = []

    def __init__(self, settings: Settings):
        """Create a new `Reader`.

        Do not instantiate a reader directly. Instead, use `Reader.from_extension`.

        :param settings: Seagull settings.
        """
        self.settings = settings

    # TODO deal with code duplication with Writer class
    @classmethod
    def all_readers(cls) -> Iterable[type[Reader]]:
        """Yield the list of enabled reader classes."""
        for reader in Reader.__subclasses__():
            if reader.enabled:
                yield reader

    @classmethod
    def from_extension(cls, extension: str | None) -> type[Self]:
        """Return a reader class that's suitable for a given file extension.

        :param extension: File extension (with or without leading dot). `None` is used
        as a special value for static files.
        :return: A `Reader` subclass.
        :raise KeyError: If there is no suitable reader class for the extension.
        """
        # Remove the leading dot if the extension is not None
        if isinstance(extension, str) and extension.startswith("."):
            extension = extension[1:]
        # Look for a suitable reader
        candidates = [r for r in cls.all_readers() if extension in r.file_extensions]
        # Raise an exception if no reader was found
        if not candidates:
            raise KeyError(extension)
        # TODO maybe find the most specialized subclass instead
        reader_class = candidates[0]
        # Log a warning if more than one reader is suitable for this extension
        if len(candidates) > 1:
            file_type = "static files" if extension is None else f"'{extension}' files"
            logger.warning(
                f"Found {len(candidates)} readers for {file_type},"
                f"{reader_class.__name__} will be used."
            )
        return reader_class

    @abstractmethod
    def _parse_data(self, path: Path) -> tuple[str, dict[str, Any]]:
        """Parsing procedure for the reader.

        :param path: Absolute path of the source file to path.
        :return: Parsed content and unprocessed metadata dictionary.
        """

    def _default_metadata[T: SeagullObject](
        self, path: Path, content_class: type[T], base_path: Path
    ) -> dict[str, Any]:
        """Create the default metadata for an object.

        :param path: Absolute path of the source file.
        :param content_class: Class of the content object to create.
        :param base_path: Base path of the source file.
        :return: A dictionary of unprocessed metadata attributes.
        """

        metadata = {}
        # Defaults from settings
        for key, value in chain(
            # DEFAULT_METADATA
            self.settings.default_metadata.items(),
            # DEFAULT_*
            (
                (f.name, getattr(self.settings, f"default_{f.name}", None))
                for f in fields(content_class)
            ),
            # AUTHOR
            (("authors", self.settings.author),),
            # EXTRA_PATH_METADATA
            (
                (k, v)
                # Sorting so that the most specific path wins a conflict
                for target_path, extra_metadata in sorted(
                    self.settings.extra_path_metadata.items()
                )
                if path.is_relative_to(target_path)
                for k, v in extra_metadata.items()
            ),
        ):
            field_name = key.lower()
            match field_name, value:
                # Skip None or empty values
                case _, (None | ""):
                    continue
                # DEFAULT_DATE="fs" gets special treatment
                case "date", "fs":
                    metadata[field_name] = datetime.fromtimestamp(
                        (self.settings.path / path).stat().st_mtime,
                        tz=self.settings.timezone,
                    )
                case _, _:
                    metadata[field_name] = value

        # Defaults from source path
        regexes = {}
        # PATH_METADATA -> parent directory
        if regex := self.settings.path_metadata:
            regexes[regex] = path.parent
        # FILENAME_METADATA -> file name without the extension
        if regex := self.settings.filename_metadata:
            regexes[regex] = path.stem
        # USE_FOLDER_AS_CATEGORY = True -> parent directory name is the category
        # ... Except if the source file is in the base path
        if self.settings.use_folder_as_category and path.parent != base_path:
            regexes[r"(?P<category>.*)"] = path.parent.name
        # Execute each regex
        for regex, target in regexes.items():
            if not target:
                continue
            if not (match := re.match(regex, target)):
                continue
            for key, value in match.groupdict().items():
                if value:
                    metadata[key.lower()] = value

        return metadata

    def read_file[T: SeagullObject](
        self,
        path: Path,
        content_class: type[T],
        context: Context,
        base_path: Path,
    ) -> T:
        """Parse a file to return a content object.

        It uses the `_parse_data` method to retrieve the parsed content and parsed,
        unprocessed metadata. Each raw metadata value is then processed using
        `seagull.readers.MetadataProcessor.process`.

        :param path: Absolute path of the source file.
        :param content_class: Class of the content object to create.
        :param context: Shared `Context` object for the run.
        :param base_path: Base path of the source file.
        :return: A new seagull object.
        :raise SkippedFileError: If the file should be skipped.
        """
        log_path = path.relative_to(base_path.parent)
        logger.debug(
            f"Parsing '{log_path}' into an object of type '{content_class.__name__}'."
        )

        # Get the default metadata
        metadata = self._default_metadata(path, content_class, base_path)

        # Parse the source file
        content, reader_metadata = self._parse_data(path)
        # If the parsed metadata as an author or multiple authors, delete both defaults
        # to avoid unwanted interactions
        if "author" in reader_metadata or "authors" in reader_metadata:
            metadata.pop("author", None)
            metadata.pop("authors", None)

        # Apply the parsed metadata to the defaults
        metadata.update(reader_metadata)
        return content_class.from_parsed_metadata(
            settings=self.settings,
            context=context,
            content=content,
            source_path=path,
            base_path=base_path,
            **metadata,
        )
