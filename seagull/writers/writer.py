import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Self

from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from seagull.contents import SeagullObject
    from seagull.context import Context
    from seagull.settings import Settings


class Writer(ABC):
    """Abstract base writer class.

    A `Writer` object turns seagull objects into files.
    """

    # FIXME metaclass for all this duplicated code from Reader?
    enabled: bool = True
    file_extensions: list[str] = []
    _instances: dict[type[Writer], Writer] = {}
    _per_extension: dict[str | None, Writer] = {}

    @classmethod
    def all_writers(cls) -> Iterable[type[Writer]]:
        """Yield the list of enabled writer classes."""
        for reader in Writer.__subclasses__():
            if reader.enabled:
                yield reader

    def __init__(self, settings: Settings):
        """Create a new `Writer`.

        Do not instantiate a reader directly. Instead, use `Writer.from_extension`.

        :param settings: Seagull settings.
        """
        self.settings = settings

    @classmethod
    def from_extension(cls, settings: Settings, extension: str | None) -> Self:
        """Return a writer instance that's suitable for a given file extension. It
        automatically creates an instance if it doesn't exist already.

        :param settings: Settings to initialize the writer with.
        :param extension: File extension (with or without leading dot). `None` is used
        as a special value for static files.
        :return: A `Writer` subclass instance.
        :raise KeyError: If there is no suitable writer class for the extension.
        """
        # Remove the leading dot if the extension is not None
        if isinstance(extension, str) and extension.startswith("."):
            extension = extension[1:]
        # If we already encountered this extension, directly retrieve the writer
        if extension in cls._per_extension:
            return cls._per_extension[extension]

        # Otherwise, look for a suitable writer
        candidates = [r for r in cls.all_writers() if extension in r.file_extensions]
        # Raise an exception if no reader was found
        if not candidates:
            raise KeyError(extension)
        writer_class = candidates[0]
        # Log a warning if more than one reader is suitable for this extension
        if len(candidates) > 1:
            file_type = "static files" if extension is None else f"'{extension}' files"
            logger.warning(
                f"Found {len(candidates)} writers for {file_type},"
                f"{writer_class.__name__} will be used."
            )
        # Create the reader instance if it doesn't already exist
        if writer_class not in cls._instances:
            cls._instances[writer_class] = writer_class(settings)
        # Associate the extension to the reader instance
        cls._per_extension[extension] = cls._instances[writer_class]
        # Return the reader instance
        return cls._instances[writer_class]

    @abstractmethod
    def _parse_data(self, obj: SeagullObject, context: Context) -> str | Path:
        """Parsing procedure for the writer.

        :param obj: Seagull object.
        :param context: Shared context.
        :return: Parsed content string, ready to be written in a file, or a `Path`
        object pointing to a file that will be copied to the `save_as` value of the
        object.
        """

    def write_file[T: SeagullObject](self, obj: T, context: Context):
        """Parse a seagull object to write a file.

        It uses the `_parse_data` method to create the content of the output file.

        :param obj: Seagull object to parse.
        :param context: Shared context.
        """
        output_path = self.settings.output_path / obj.save_as
        log_output_path = output_path.relative_to(self.settings.output_path.parent)
        logger.debug(f"Writing '{log_output_path}'.")

        # FIXME handle overrides

        # Write the file
        try:
            # mkdir -p the output directory if required
            if not output_path.parent.exists():
                output_path.parent.mkdir(parents=True)
            # If the output path is a directory, delete it first
            elif output_path.is_dir():
                output_path.unlink()
            # Parse the data and save it
            match self._parse_data(obj, context):
                # If _parse_data returns a path, we copy this file to the output
                case Path() as source_path:
                    if source_path.is_dir():
                        # If the output path is an existing file, delete it first
                        if output_path.is_file():
                            output_path.unlink(missing_ok=True)
                        shutil.copytree(source_path, output_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_path, output_path)
                # Otherwise, we write the parsed data to the output
                case str(output_data):
                    output_path.write_text(output_data)
        except OSError:
            logger.exception(
                f"Failed to create '{log_output_path}'.",
                exc_info=logger.level == logging.DEBUG,
            )
