from abc import ABC, abstractmethod
import logging
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, ClassVar, Self

from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from seagull.contents import SeagullObject
    from seagull.context import Context
    from seagull.settings import Settings


class Writer(ABC):
    """Abstract base writer class.

    A `Writer` object turns seagull objects into files.
    """

    enabled: bool = True
    file_extensions: ClassVar[list[str | None]] = []

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
    def from_extension(cls, extension: str | None) -> type[Self]:
        """Return a writer class that's suitable for a given file extension.

        :param extension: File extension (with or without leading dot). `None` is used
        as a special value for static files.
        :return: A `Writer` subclass.
        :raise KeyError: If there is no suitable writer class for the extension.
        """
        # Remove the leading dot if the extension is not None
        if isinstance(extension, str) and extension.startswith("."):
            extension = extension[1:]
        # Look for a suitable reader
        candidates = [r for r in cls.all_writers() if extension in r.file_extensions]
        # Raise an exception if no reader was found
        if not candidates:
            raise KeyError(extension)
        # TODO maybe find the most specialized subclass instead
        writer_class = candidates[0]
        # Log a warning if more than one reader is suitable for this extension
        if len(candidates) > 1:
            file_type = "static files" if extension is None else f"'{extension}' files"
            logger.warning(
                f"Found {len(candidates)} readers for {file_type},"
                f"{writer_class.__name__} will be used."
            )
        return writer_class

    @abstractmethod
    def _parse_data(
        self, obj: SeagullObject, context: Context
    ) -> dict[Path, str | Path]:
        """Parsing procedure for the writer.

        This method can return multiple destinations, which is useful for paginated
        templates.

        :param obj: Seagull object.
        :param context: Shared context.
        :return: A dictionary of absolute paths, mapped to a content string ready to be
        written to the path, or a Path pointing to a file that will be copied directly.
        """

    @staticmethod
    def _get_jinja_context(obj: SeagullObject, context: Context) -> dict[str, Any]:
        """Create the render context for the object.

        This may be called by `self._parse_data` to get the full render context of an
        object.
        """
        # We merge the settings, the base render context, and that of the object, to
        # create the full render context
        return (
            obj.settings.as_dict()
            | context.base_jinja_context(obj.lang)
            | obj.jinja_context
        )

    def write_file[T: SeagullObject](self, obj: T, context: Context) -> None:
        """Parse a seagull object to write a file.

        It uses the `_parse_data` method to create the content of the output file.

        :param obj: Seagull object to parse.
        :param context: Shared context.
        """
        # Parse the data and save it
        for dest_path, content in self._parse_data(obj, context).items():
            log_dest_path = dest_path.relative_to(obj.settings.output_path.parent)
            logger.debug(f"Writing '{log_dest_path}'.")
            try:
                # mkdir -p the output directory if required
                if not dest_path.parent.exists():
                    dest_path.parent.mkdir(parents=True)
                # If the output path is a directory, delete it first
                elif dest_path.is_dir():
                    dest_path.unlink()
                elif dest_path.is_file():
                    logger.warning(f"Overriding {log_dest_path}.")
                # For every returned parsed content...
                match content:
                    # If we have a path, we copy this file to the output
                    case Path() as source_path:
                        if source_path.is_dir():
                            # If the output path is an existing file, delete it first
                            if dest_path.is_file():
                                dest_path.unlink(missing_ok=True)
                            shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                        else:
                            shutil.copy2(source_path, dest_path)
                    # Otherwise, we write the parsed data to the output
                    case str(output_data):
                        dest_path.write_text(output_data)
            except OSError:
                logger.exception(
                    f"Failed to create '{log_dest_path}'.",
                    exc_info=logger.level == logging.DEBUG,
                )
