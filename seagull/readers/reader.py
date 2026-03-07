import re
from abc import ABC, abstractmethod
from dataclasses import fields
from datetime import datetime
from typing import TYPE_CHECKING, Any, Self

from seagull.exceptions import DiscardMetadataException, SkippedFileException
from seagull.log import logger
from seagull.readers.metadata_processors import MetadataProcessor

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from seagull.contents import SeagullObject
    from seagull.context import Context
    from seagull.settings import Settings


class Reader(ABC):
    """Abstract base reader class.

    A `Reader` object creates seagull objects from a file."""

    enabled: bool = True
    file_extensions: list[str] = []
    _instances: dict[type[Reader], Reader] = {}
    _per_extension: dict[str | None, Reader] = {}

    def __init__(self, settings: Settings):
        """Create a new `Reader`.

        Do not instantiate a reader directly. Instead, use `Reader.from_extension`.

        :param settings: Seagull settings.
        """
        self.settings = settings

    @classmethod
    def all_readers(cls) -> Iterable[type[Reader]]:
        """Yield the list of enabled reader classes."""
        for reader in Reader.__subclasses__():
            if reader.enabled:
                yield reader

    @classmethod
    def from_extension(cls, settings: Settings, extension: str | None) -> Self:
        """Return a reader instance that's suitable for a given file extension. It
        automatically creates an instance if it doesn't exist already.

        :param settings: Settings to initialize the reader with.
        :param extension: File extension (with or without leading dot). `None` is used
        as a special value for static files.
        :return: A `Reader` subclass instance.
        :raise KeyError: If there is no suitable reader class for the extension.
        """
        # Remove the leading dot if the extension is not None
        if isinstance(extension, str) and extension.startswith("."):
            extension = extension[1:]
        # If we already encountered this extension, directly retrieve the reader
        if extension in cls._per_extension:
            return cls._per_extension[extension]

        # Otherwise, look for a suitable reader
        candidates = [r for r in cls.all_readers() if extension in r.file_extensions]
        # Raise an exception if no reader was found
        if not candidates:
            raise KeyError(extension)
        # FIXME maybe find the most specialized subclass instead
        reader_class = candidates[0]
        # Log a warning if more than one reader is suitable for this extension
        if len(candidates) > 1:
            file_type = "static files" if extension is None else f"'{extension}' files"
            logger.warning(
                f"Found {len(candidates)} readers for {file_type},"
                f"{reader_class.__name__} will be used."
            )
        # Create the reader instance if it doesn't already exist
        if reader_class not in cls._instances:
            cls._instances[reader_class] = reader_class(settings)
        # Associate the extension to the reader instance
        cls._per_extension[extension] = cls._instances[reader_class]
        # Return the reader instance
        return cls._instances[reader_class]

    @abstractmethod
    def _parse_data(self, path: Path) -> tuple[str, dict[str, Any]]:
        """Parsing procedure for the reader.

        :param path: Absolute path of the source file to path.
        :return: Parsed content and unprocessed metadata dictionary.
        """

    def read_file[T: SeagullObject](
        self,
        path: Path,
        content_class: type[T],
        context: Context,
        base_path: Path | None = None,
    ) -> T:
        """Parse a file to return a content object.

        It uses the `_parse_data` method to retrieve the parsed content and parsed,
        unprocessed metadata. Each raw metadata value is then processed using
        `seagull.readers.MetadataProcessor.process`.

        :param path: Absolute path of the source file.
        :param content_class: Class of the content object to create.
        :param context: Shared `Context` object for the run.
        :param base_path: Base path of the source file. If `None`, it is assumed to be
        that of the content object.
        :return: A new seagull object.
        :raise SkippedFileException: If the file should be skipped.
        """
        if not base_path:
            base_path = getattr(self.settings, content_class.default_base_path_key)
        log_path = path.relative_to(base_path.parent)
        logger.debug(
            f"Parsing '{log_path}' into an object of type '{content_class.__name__}'."
        )
        metadata = {}
        content_fields = [f.name for f in fields(content_class)]
        is_extra_dataclass = getattr(content_class, "__extra_dataclass__", False)

        def _process_metadata(k, v, dest):
            try:
                # If the content class doesn't accept extra metadata and the key is not
                # a regular field, discard it
                if k not in content_fields and not is_extra_dataclass:
                    raise DiscardMetadataException(k)
                dest[k] = MetadataProcessor.process(
                    k, v, settings=self.settings, context=context
                )
            except DiscardMetadataException:
                if k in dest:
                    del dest[k]

        # Defaults from settings (DEFAULT_METADATA and DEFAULT_* keys)
        for key, value in self.settings.default_metadata.items():
            metadata[key.lower()] = value
        for key in content_fields:  # look for a DEFAULT_* setting for each field
            if value := getattr(self.settings, f"default_{key}", None):
                # DEFAULT_DATE="fs" gets special treatment
                if key == "date" and value == "fs":
                    metadata[key] = datetime.fromtimestamp(
                        (self.settings.path / path).stat().st_mtime
                    )
                    continue
                metadata[key] = value
        # Default author
        if value := self.settings.author:
            # 'authors', because the default author can be a list of authors
            metadata["authors"] = value

        # Defaults from EXTRA_PATH_METADATA
        epm = self.settings.extra_path_metadata
        # Sorting so that the most specific path wins a conflict
        for target_path, extra_metadata in sorted(epm.items()):
            if path.is_relative_to(target_path):
                for key, value in extra_metadata.items():
                    metadata[key.lower()] = value

        # Process metadata from source path
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
        # FIXME remove default fields that aren't in the dataclass fields of the content class?

        # Parse the source file
        content, reader_metadata = self._parse_data(path)
        # If the parsed metadata as an author or multiple authors, delete both defaults
        # to avoid unwanted interactions
        if "author" in reader_metadata or "authors" in reader_metadata:
            metadata.pop("author", None)
            metadata.pop("authors", None)
        # Process metadata
        metadata.update(reader_metadata)
        # We iterate over a list copy, because _process_metadata can remove keys from
        # the metadata dict
        for key, value in list(metadata.items()):
            _process_metadata(key, value, metadata)

        # We skip items who have a skip status, or those whose output path has been
        # explicitly set to an empty value
        if metadata.get("status") == "skip" or not metadata.get("save_as", True):
            raise SkippedFileException(path)

        return content_class(self.settings, content, path, base_path, **metadata)
