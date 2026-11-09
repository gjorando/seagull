from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Self

from attrs import define, field, fields

from seagull.exceptions import InvalidObjectError, SkippedFileError
from seagull.typeshed import SeagullStatus

if TYPE_CHECKING:
    from io import Reader

    from attrs import Attribute

    from seagull.objects import BaseObject
    from seagull.typeshed import StrPath


@define
class BaseReader[T: BaseObject](ABC):
    """A reader converts raw data into a Seagull object."""

    _registered_readers: ClassVar[list[Self]] = []
    """Set of registered readers, for global access."""
    file_extensions: ClassVar[tuple[str | None, ...]] = (None,)
    """Allowed file extensions for the reader.

    If set to `(None,)`, the reader accepts all file extensions."""
    binary_mode: ClassVar[bool] = False
    """Whether the reader works in binary mode."""

    registered: bool = field(default=False, converter=bool, repr=False)
    """Mark the reader as registered.

    A registered reader is globally available through `BaseReader.all_readers`."""

    @registered.validator
    def _attrs_registered_validator(self, attribute: Attribute, value: object) -> None:
        del attribute  # Unused variable
        if value:
            if self not in self._registered_readers:
                self._registered_readers.append(self)
        elif self in self._registered_readers:
            self._registered_readers.remove(self)

    @classmethod
    def all_readers(cls) -> tuple[Self, ...]:
        """Return all registered readers."""
        return tuple(cls._registered_readers)

    @classmethod
    def from_extension(cls, extension: str | None) -> BaseReader:
        """Return a reader for files of the given extension.

        :param extension: Extension of the file to verify, or `None` for the static
        reader.
        :return: A `BaseReader` subclass instance.
        :raise ValueError: If there is no suitable reader for the extension.
        """
        candidates = list(
            filter(lambda r: extension in r.file_extensions, cls.all_readers())
        )
        if not candidates:
            raise ValueError(extension)
        # TODO if we have more than one suitable reader, what should we do?
        return candidates[0]

    @abstractmethod
    def _parse_raw_data(self, text_or_bytes: str | bytes) -> dict[str, str | list[str]]:
        """Parse raw text or bytes into a dictionary of attributes.

        Subclasses should implement this method to define how input data is actually
        handled.

        :param text_or_bytes: Raw text or bytes to parse.
        :return: A dictionary of parsed attributes.
        """

    def loads(
        self,
        object_class: type[T],
        text_or_bytes: str | bytes,
        /,
        *,
        default_values: dict[str, object] | None = None,
    ) -> T:
        """Load a seagull object from raw text or bytes.

        :param object_class: Type of object to create.
        :param text_or_bytes: Raw text or bytes to parse.
        :param default_values: Optional default values for the fields of the object.
        :return: A new Seagull object of type `object_class`.
        :raise InvalidObjectError: If the object creation failed.
        :raise SkippedFileError: If the created object's status is `skip`.
        """
        try:
            obj_data = (default_values or {}) | self._parse_raw_data(text_or_bytes)
            # Regular fields are init fields. We rule-out 'metadata' as a
            # regular field as well, because we do not want a user field
            # named 'metadata' to override ours.
            all_fields = {
                # We must use the alias to ensure we have the actual init param name
                v.alias: v
                for v in fields(object_class)
                if v.init and v.name != "metadata"
            }
            attributes = {k: v for k, v in obj_data.items() if k in all_fields}
            attributes["metadata"] = {
                k: v for k, v in obj_data.items() if k not in all_fields
            }
            obj = object_class(**attributes)
        # If the object creation failed, re-raise as InvalidObjectError
        except (ValueError, TypeError) as e:
            raise InvalidObjectError from e
        # If the object has the skip status, raise the SkippedFileError
        if obj.status == SeagullStatus.SKIP:
            raise SkippedFileError(obj)
        return obj

    def load(
        self,
        object_class: type[T],
        fp: Reader[str | bytes],
        /,
        *,
        default_values: dict[str, object] | None = None,
    ) -> T:
        """Load a seagull object from a reader object, typically an I/O stream.

        :param object_class: Type of object to create.
        :param fp: File-like object that implements a `.read()` method.
        :param default_values: Optional default values for the fields of the object.
        :return: A new Seagull object of type `object_class`.
        :raise InvalidObjectError: If the object creation failed.
        :raise SkippedFileError: If the created object's status is `skip`.
        """
        return self.loads(object_class, fp.read(), default_values=default_values)

    def __call__(
        self,
        object_class: type[T],
        source_path: StrPath,
        /,
        *,
        default_values: dict[str, object] | None = None,
    ) -> T:
        """Load a Seagull object from a source path.

        :param object_class: Type of object to create.
        :param source_path: A path to a file.
        :param default_values: Optional default values for the fields of the object.
        :return: A new Seagull object of type `object_class`.
        :raise InvalidObjectError: If the object creation failed.
        :raise SkippedFileError: If the created object's status is `skip`.
        """
        default_values = default_values or {}
        default_values.setdefault("source_path", source_path)

        with open(source_path, "rb" if self.binary_mode else "r") as fp:
            return self.load(object_class, fp, default_values=default_values)
