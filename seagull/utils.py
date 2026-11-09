from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from importlib import import_module
from importlib.util import find_spec
import locale
import logging
from pathlib import Path
import re
import shutil
from typing import TYPE_CHECKING, ClassVar, Self
import urllib.parse

from attrs import define, field, validators

from seagull.logging import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence

    from bs4 import Tag

    from seagull.typeshed import (
        JinjaContext,
        StrPath,
    )


def subclasses[T](cls: type[T]) -> Generator[type[T]]:
    """Yield all subclasses."""
    for sub_cls in cls.__subclasses__():
        yield sub_cls
        yield from subclasses(sub_cls)


@contextmanager
def temporary_locale(
    temp_locale: str, lc_category: int | tuple[int, ...] = locale.LC_ALL
) -> Generator[None]:
    """Context manager for running code with a temporary locale.

    Resets the locale back when exiting context.

    :param temp_locale: Temporary locale to use.
    :param lc_category: Locale category or list of locale categories that are affected.
    """
    if not isinstance(lc_category, tuple):
        lc_category = [lc_category]
    orig_locales = {lcc: locale.setlocale(lcc) for lcc in lc_category}
    # Change the desired locale categories, then enter the context manager
    for lcc in lc_category:
        locale.setlocale(lcc, temp_locale)
    yield
    # After exiting the context manager, restore the categories to their old locale
    for lcc in lc_category:
        locale.setlocale(lcc, orig_locales[lcc])


def load_object_from_module(value: str, default_module: str | None = None) -> object:
    """Load an object from an import path.

    :param value: Either an absolute or relative import path for an object. If
    `default_module` is set, it can also be the name of an object in `default_module`.
    :param default_module: Optional default module to use.
    :return: A loaded object.
    """
    mod, _, generator_class = value.rpartition(".")
    if default_module and not mod:
        mod = default_module
    try:
        return getattr(import_module(mod), generator_class)
    except ValueError as e:
        raise ValueError("No default module for object '{generator_class}'") from e
    except AttributeError as e:
        raise ValueError(
            f"'{generator_class}': unknown object in module '{mod}'"
        ) from e
    except ModuleNotFoundError as e:
        raise ValueError(
            f"'{mod}': unknown module for object '{generator_class}'"
        ) from e


def object_class_converter(
    *,
    default_module: str | None = None,
) -> Callable[[type | str], type]:
    """Converter to resolve types when passed as strings.

    :param default_module: Optional default module to use (see
    `seagull.utils.load_object_from_module`).
    :return: A converter function that ensure we resolve a type name.
    """

    def _converter(value: type | str) -> type:
        if isinstance(value, str):
            if not isinstance(
                result := load_object_from_module(value, default_module), type
            ):
                raise ValueError(f"'{value}' must be a type")
            return result
        return value

    return _converter


def datetime_converter(value: str | datetime) -> datetime:
    """Converter for `datetime` fields.

    :param value: The value to convert. If it's a string, it is parsed using
    `fromisoformat`.
    :return: A `datetime` object.
    """
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def path_repr_func(
    *, resolve: bool = False, quotes: str = "'", none_fallback: str = "None"
) -> Callable[[Path], str]:
    """Create a function that can be used to represent a path.

    This is used primarily for the `repr` parameter of the `attrs.field` function.

    :param resolve: Whether to resolve the path.
    :param quotes: Character to use around the path representation.
    :param none_fallback: If the value can be `None`, defines a default return value.
    :return: A function that takes a path and returns its string representation.
    """

    def _func(value: Path | None) -> str:
        if value is None:
            return none_fallback
        if resolve:
            value = value.resolve()
        return f"{quotes}{value}{quotes}"

    return _func


def installed_themes_path() -> Path | None:
    """Retrieve the directory where installed themes are stored.

    :return: The path for installed themes, or `None` if it couldn't be found.
    """
    result = None
    if (seagull_spec := find_spec(__package__)) and seagull_spec.origin:
        # the installed themes are stored in <seagull package>/themes/
        package_dir = Path(seagull_spec.origin).parent
        result = package_dir / "themes"
    if not (result and result.exists()):
        result = None
        logger.warning(
            "Couldn't find the installed themes path: 'simple' and "
            "the other installed themes won't be available."
        )
    return result


def resolve_theme_path(value: str | StrPath) -> Path:
    """Ensure a theme value is an existing theme path.

    :param value: Path to a theme, or name of an installed theme.
    :return: Resolved path to said theme, if it exists.
    :raise ValueError: If the path doesn't exist.
    """
    result = Path(value)
    if result.exists():
        return result
    base_theme_path = installed_themes_path()
    if not (base_theme_path and (result := base_theme_path / value).exists()):
        raise ValueError(f"'{value}': not a valid theme.")
    return result


class JinjaRenderable(ABC):
    """Mixin for objects that can be rendered in Jinja."""

    @property
    @abstractmethod
    def jinja_context(self) -> JinjaContext:
        """Rendering context that the object adds."""


def clear_directory(
    path: Path,
    retention_paths: Sequence[str | Path] | None = None,
    *,
    file_okay: bool = False,
) -> list[Path]:
    """Clear a directory in order to populate it again.

    This function ensures `path` exists by the end of its normal execution.

    :param path: Path to clear.
    :param retention_paths: Paths, relative to `path`, to preserve from deletion.
    :param file_okay: If `True`, delete `path` if it's a file.
    :return: List of paths relative to `path` that were effectively kept because of the
    retention policy.
    :raise RuntimeError: If `path` is a file and `file_okay` is `False`.
    """
    # Simply create the directory if it doesn't exist yet
    if not path.exists():
        path.mkdir()
        return []
    # Try removing a file if path is a file and file_okay == True
    if not path.is_dir():
        if not file_okay:
            raise RuntimeError(f"Cannot clear {path}, as it is a file.")
        try:
            path.unlink()
        except OSError:
            logger.exception(
                f"Unable to delete the file '{path}'.",
                exc_info=logger.level == logging.DEBUG,
            )
        path.mkdir()
        return []

    # Otherwise, clear the output path contents
    # Ensure retention_paths is a list of paths
    retention_paths = [Path(p) for p in (retention_paths or [])]
    retained_paths = []
    for child in path.iterdir():
        # But not if the file/directory is in the retention paths
        if (rel_child := child.relative_to(path)) in retention_paths:
            retained_paths.append(rel_child)
            continue
        # Try to delete the child
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError:
            child_dir = child.relative_to(path.parent)
            logger.exception(
                f"Unable to delete '{child_dir}'.",
                exc_info=logger.level == logging.DEBUG,
            )
    return retained_paths


@define
class IntrasiteLink:
    """A representation of an intrasite link.

    Intrasite links are essentially URNs, apart from the fact that the NSS portion
    (Namespace-Specific String, corresponding to the target of the link) can contain any
    character (the RFC8141 restricts the NSS to a limited subset of characters). The
    actual implementation of how to convert the intrasite link is up to the seagull
    object. The scheme part is `seagull:`.
    """

    SCHEME_NAME: ClassVar[str] = "seagull"
    """Name of the scheme."""
    LINK_ATTRS: ClassVar[tuple[str, ...]] = (
        "href",
        "src",
        "poster",
        "data",
        "cite",
        "formaction",
        "action",
        "content",
    )
    """HTML attributes that can contain an intrasite link."""

    identifier: str = field(
        validator=validators.matches_re(
            r"^[a-z0-9][a-z0-9\-]{1,31}$", flags=re.IGNORECASE
        ),
        converter=lambda x: x.lower().strip(),
    )
    """Identifier for the type of intrasite link (NID of the URN)."""
    target: str = field(
        default="",
        # Convert %xx escapes back to Unicode
        converter=lambda x: urllib.parse.unquote(x.strip()),
    )
    """Intrasite target(NSS of the URN, allowing leading slashes)."""
    tag: Tag = field(kw_only=True, repr=False)
    """HTML tag associated with the intrasite link."""
    attr: str = field(kw_only=True, repr=False)
    """HTML attribute in `tag` where the intrasite link resides."""

    @classmethod
    def from_string(cls, raw_urn: str, tag: Tag, attr: str) -> Self:
        """Create a new `URN` object.

        :param raw_urn: Raw URN string.
        :param tag: Optional HTML tag.
        :param attr: Optional attribute.
        :return: A parsed `URN` object.
        """
        scheme, *remainder = raw_urn.split(":", 2)
        if scheme != cls.SCHEME_NAME or not remainder:
            raise ValueError("Invalid URN string")
        return cls(*remainder, tag=tag, attr=attr)

    def __str__(self) -> str:
        return (
            f"{self.SCHEME_NAME}:{self.identifier}"
            f"{f':{self.target}' if self.target else ''}"
        )
