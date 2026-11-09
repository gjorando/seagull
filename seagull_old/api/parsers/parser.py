from abc import ABC, ABCMeta, abstractmethod
from pathlib import Path
import threading
from typing import TYPE_CHECKING, ClassVar, Self

from attrs import define

from seagull.api.exceptions import InvalidObjectError, SkippedFileError
from seagull.api.utils import SeagullStatus
from seagull.logging import logger
from seagull.utils import subclasses

if TYPE_CHECKING:
    from io import Reader, Writer

    from seagull.api.objects import SeagullObject


class ParserMeta(ABCMeta):
    """Metaclass for parser classes.

    It implements the singleton design pattern for parser objects."""

    _parsers: ClassVar[dict] = {}
    """Singleton instances."""
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()
    """Ensure the singleton instantiation is thread-safe."""

    def __call__(cls, *args: object, **kwargs: object) -> Self:
        with cls._instance_lock:
            if cls not in cls._parsers:
                cls._parsers[cls] = super().__call__(*args, **kwargs)
            return cls._parsers[cls]


@define(kw_only=True, slots=False)
class Parser[T: SeagullObject](ABC, metaclass=ParserMeta):
    """Base parser class for reading and writing seagull objects."""

    file_extensions: ClassVar[tuple[str | None, ...]] = (None,)
    """Allowed file extensions for the parser.

    `(None,)` means that the parser accepts all extensions."""

    @classmethod
    def from_extension(cls, extension: str | None = None) -> type[Parser]:
        """Return a parser class that's suitable for a given file extension.

        If there is more than one subclass that's suitable for the file extension, we
        use a quick and dirty heuristic for finding the "most specialized subclass",
        being the one that has the longest list of parent classes. For instance, for
        `extension="foo"`, if we have candidates `FooParser(Parser)` and
        `SpecialFooParser(FooParser)`, we will return the latter.

        :param extension: File extension (with or without leading dot), or `None` for
        the "catch-all" subclass.
        :return: A suitable subclass.
        :raise KeyError: If there is no suitable class for the extension.
        """
        # Remove the leading dot if the extension is not None
        if isinstance(extension, str) and extension.startswith("."):
            extension = extension[1:]
        # Look for a suitable subclass
        candidates = [
            candidate
            for candidate in subclasses(cls)
            if extension in candidate.file_extensions
        ]
        # Raise an exception if no subclass was found
        if not candidates:
            raise KeyError(extension)
        # TODO maybe add an option for a custom key? Parser classes could have a weighing property?
        max_mro = max(len(c.mro()) for c in candidates)
        candidates = [c for c in candidates if len(c.mro()) == max_mro]
        # Log a warning if more than one reader is suitable for this extension
        if len(candidates) > 1:
            file_type = "generic file" if extension is None else f"'.{extension}' file"
            logger.warning(
                f"Found {len(candidates)} suitable subclasses of '{cls.__name__}' for "
                f"{file_type}, '{candidates[0].__name__}' will be used."
            )
        return candidates[0]

    @abstractmethod
    def _loads(self, text: str) -> dict:
        """Convert raw text data to a dictionary of fields.

        This is the actual method where subclasses implement how the object's attributes
        are extracted from raw text.

        :param text: Raw text to parse.
        :return: A dictionary of object attributes.
        """

    def loads(
        self,
        text: str,
        object_class: type[T],
        /,
        **kwargs: object,
    ) -> T:
        """Load a seagull object from raw text.

        :param text: Raw text to parse.
        :param object_class: Type of object to create.
        :param kwargs: Optional default values for the fields of the object.
        :return: A new seagull object of type `object_class`.
        :raise InvalidObjectError: If the object creation failed.
        :raise SkippedFileError: If the created object's status is `skip`.
        """
        try:
            obj = object_class.from_parsed(**(kwargs | self._loads(text)))
        # If the object creation failed, re-raise as InvalidObjectError
        except (ValueError, TypeError) as e:
            raise InvalidObjectError from e
        # If the object has the skip status, raise the SkippedFileError
        if obj.status == SeagullStatus.SKIP:
            raise SkippedFileError(obj)
        return obj

    def load(
        self,
        fp: Reader[str],
        object_class: type[T],
        /,
        **kwargs: object,
    ) -> T:
        """Load a seagull object from a reader object, typically an I/O stream.

        :param fp: File-like object that implements a `.read()` method.
        :param object_class: Type of object to create.
        :param kwargs: Optional default values for the fields of the object.
        :return: A new seagull object of type `object_class`.
        """
        return self.loads(
            fp.read(),
            object_class,
            **kwargs,
        )

    def read(
        self,
        source_path: Path | str,
        source_root: Path | str,
        object_class: type[T],
        /,
        **kwargs: object,
    ) -> T:
        """Load a seagull object from a source path.

        :param source_path: A path to a file, relative to `source_root`.
        :param source_root: Base path of the object.
        :param object_class: Type of object to create.
        :param kwargs: Optional default values for the fields of the object.
        :return: A new seagull object of type `object_class`.
        :raise InvalidObjectError: If the object creation failed.
        """
        full_path = Path(source_root) / source_path
        try:
            with open(full_path) as fp:
                return self.load(
                    fp,
                    object_class,
                    source_root=source_root,
                    source_path=full_path,
                    **kwargs,
                )
        except OSError as e:
            raise InvalidObjectError from e

    @abstractmethod
    def dumps(self, obj: T, /, **kwargs: object) -> str:
        """Convert a Seagull object to text.

        :param obj: Object to convert.
        :param kwargs: Additional data.
        :return: A string representing the object.
        """

    def dump(self, obj: T, fp: Writer[str], /, **kwargs: object) -> None:
        """Write a Seagull object in a file.

        :param obj: Object to convert.
        :param fp: File-like object that implements a `.write()` method.
        :param kwargs: Additional data.
        """

        fp.write(self.dumps(obj, **kwargs))

    def write(self, obj: T, /, output_path: Path | str = ".", **kwargs: object) -> None:
        """Write a seagull object to the object's `save_as` field.

        :param obj: Object to convert.
        :param output_path: Base output directory.
        :param kwargs: Additional data.
        """
        dest_path = output_path / obj.save_as
        # mkdir -p the output directory if required
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True)
        # If the output path is a directory, delete it first
        elif dest_path.is_dir():
            dest_path.unlink()
        with open(dest_path, "w") as fp:
            self.dump(obj, fp, **kwargs)
