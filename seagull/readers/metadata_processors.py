from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seagull.contents import Author, Category, Tag, Taxonomy
from seagull.exceptions import DiscardMetadataException

if TYPE_CHECKING:
    from collections.abc import Callable

    from seagull.contents import SeagullObject
    from seagull.context import Context
    from seagull.settings import Settings


class MetadataProcessor(ABC):
    """A metadata processor processes raw parsed metadata.

    Each new processor can be registered with `MetadataProcessor.register`.
    """

    _processors: dict[str, Callable] = {}

    @abstractmethod
    def __call__(
        self, key: str, value: Any, settings: Settings, context: Context
    ) -> Any:
        """Process the metadata.

        :param key: Name of the metadata attribute.
        :param value: Raw parsed value.
        :param settings: Seagull settings.
        :param context: Shared context.
        :return: Processed value.
        """

    @classmethod
    def register(cls, keys: str | list[str], instance_or_func: Callable):
        """Register a new processor.

        A processor can also be a function, for more basic processors.

        :param keys: Either a metadata key or list of metadata keys to register the
        processor for.
        :param instance_or_func: Either a `MetadataProcessor` instance, or a callable
        that takes a metadata key and a raw metadata value, and returns processed
        metadata.
        """
        if isinstance(keys, str):
            keys = [keys]

        for key in keys:
            cls._processors[key.lower()] = instance_or_func

    @classmethod
    def process(cls, key: str, value: Any, settings: Settings, context: Context) -> Any:
        """Process a metadata attribute.

        The appropriate processor is retrieved based on the `key` argument. If no
        specific processor exists for this metadata attribute, `value` is returned
        untouched.

        :param key: Name of the metadata attribute.
        :param value: Raw value.
        :param settings: Seagull settings.
        :param context: Shared context.
        :return: Processed value.
        """

        key = key.lower()
        processor = cls._processors.get(key, lambda _, v, **__: v)
        return processor(key, value, settings=settings, context=context)


class SeagullObjectProcessor[T: SeagullObject](MetadataProcessor):
    """Convert a raw metadata value into a seagull object (or list of objects)."""

    def __init__(
        self,
        object_class: type[T],
        multiple: bool = False,
        discard_if_empty: bool = False,
    ):
        """
        :param object_class: `SeagullObject` subclass to create upon processing.
        :param multiple: If `True`, parse into multiple seagull objects.
        :param discard_if_empty: If `True`, empty values are discarded.
        """
        self.object_class = object_class
        self.multiple = multiple
        self.discard_if_empty = discard_if_empty

    def __call__(
        self, key: str, value: Any, settings: Settings, context: Context
    ) -> T | list[T]:
        """Parse into Seagull objects.

        If `self.multiple` is `True`, the value is converted into a list. If the value
        contains semicolons, it is split on semicolons; otherwise, it is split on
        commas. This allows you to write author lists in either "Jane Doe, John Doe" or
        "Doe, Jane; Doe, John" format.

        If `self.object_class` is a subclass of `Taxonomy`, we try to retrieve it from
        the context, if there is a `context` parameter in `kwargs`.
        """
        if isinstance(value, str):
            value = value.strip()
        if not value and self.discard_if_empty:
            raise DiscardMetadataException(key.lower())

        # Split the value if it's a string and we are parsing multiple objects
        if self.multiple and isinstance(value, str):
            separator = ";" if ";" in value else ","
            values = value.split(separator)
        # Otherwise if we have a string, we are parsing a single object
        elif isinstance(value, str):
            values = [value]
        # Otherwise, we should already have a list
        else:
            values = value

        # Convert the values into Seagull objects
        objects = []
        for value in values:
            value = value.strip()
            # Skip empty values
            if not value:
                continue
            # If we are processing a taxon, try retrieving it from the context
            if issubclass(self.object_class, Taxonomy):
                obj = context.get_or_new_taxon(
                    self.object_class, value, settings=settings
                )
            else:
                obj = self.object_class(settings, title=value)
            objects.append(obj)
        # If we were parsing a single object, return it instead of the list
        return objects if self.multiple else objects[0]


def discard_if_empty_processor(key: str, value: Any, **_: Any) -> str:
    """Raise a `DiscardMetadataException` if the value evaluates to `False`."""
    if not value:
        raise DiscardMetadataException(key.lower())
    return value


def boolean_processor(_: str, value: Any, **__: Any) -> bool:
    """Convert a boolean string to a Python boolean.

    A string is evaluated to be `True` if it is either "true", "t", "yes" or "y"
    (case-insensitive), `False` for any other value.
    """
    return value.strip().lower() in ("true", "t", "yes", "y")


# Register the default metadata processors
# Dates are simply parsed to datetime objects, or discarded if empty
MetadataProcessor.register(
    ["date", "modified"],
    lambda k, v, **_: datetime.fromisoformat(discard_if_empty_processor(k, v.strip())),
)
# slug is stripped, or discarded if empty
MetadataProcessor.register(
    "slug", lambda k, v, **_: discard_if_empty_processor(k, v.strip())
)
# lang and status are lowercased and stripped, or discarded if empty
MetadataProcessor.register(
    ["lang", "status"],
    lambda k, v, **_: discard_if_empty_processor(k, v.lower().strip()),
)
# save_as is converted to a Path object, or set to None if empty
MetadataProcessor.register("save_as", lambda _, v, **__: Path(v) if v.strip() else None)
# Seagull objects are discarded if empty
MetadataProcessor.register(
    "category", SeagullObjectProcessor(Category, discard_if_empty=True)
)
MetadataProcessor.register(
    "author", SeagullObjectProcessor(Author, discard_if_empty=True)
)
MetadataProcessor.register(
    "authors", SeagullObjectProcessor(Author, multiple=True, discard_if_empty=True)
)
MetadataProcessor.register(
    "tags", SeagullObjectProcessor(Tag, multiple=True, discard_if_empty=True)
)
# Translation is converted to a boolean, or discarded if empty
MetadataProcessor.register(
    "translation",
    lambda k, v, **_: boolean_processor(k, discard_if_empty_processor(k, v)),
)
# TODO automatic summary generation
