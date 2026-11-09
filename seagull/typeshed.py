from enum import IntEnum, StrEnum, auto
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from seagull.objects import BaseObject


type StrPath = os.PathLike | str
"""A representation of a system path, being either a `PathLike` object or a string."""
type PostGenerateMethod[T: BaseObject] = Callable[
    [T, Mapping[type[T], Iterable[T]]], None
]
"""Signature of a Seagull object's post generate method."""
type JinjaContext = dict[str, object]
"""Rendering context for Jinja is a dictionary mapping names to generic objects."""
type ConfigObject = dict[str, ConfigObject] | list[ConfigObject] | int | bool | str
"""TODO"""
type ObjectSortingFunc[T: BaseObject] = Callable[[list[T]], list[T]]
"""Sorting key function for lists of Seagull objects."""
type ObjectSortingSpec = str | Sequence[str]
"""Description of a sorting key for seagull objects."""


class SeagullStatus(StrEnum):
    """Statuses for a Seagull object."""

    PUBLISHED = auto()
    DRAFT = auto()
    HIDDEN = auto()
    SKIP = auto()


class GeneratorPriority(IntEnum):
    """Priority shorthands for the `Generator` objects."""

    PRE_CONTENT = -1000
    """Generators that must be called before the main content."""
    CONTENT = 0
    """Main content generators."""
    POST_CONTENT = 1000
    """Generators that must be called after the main content."""
    ASSETS = 2000
    """Static assets generators."""
