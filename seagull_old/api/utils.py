from enum import StrEnum, auto
from importlib import import_module
import re
from typing import TYPE_CHECKING, ClassVar, Self, cast, dataclass_transform
import urllib.parse

from attrs import Attribute, AttrsInstance, define, field, validators

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path

    from bs4 import Tag

    from seagull.api.objects import SeagullObject


@dataclass_transform(field_specifiers=(field,), kw_only_default=True)
def seagull_object[T: type](
    cls: T,
) -> T:
    """Wrapped `attrs.define` decorator for seagull object classes."""
    return define(cls, kw_only=True, slots=False)


def post_generate[T: SeagullObject](
    method: Callable[[T, Mapping[type[T], Iterable[T]]], None],
) -> Callable[[T, Mapping[type[T], Iterable[T]]], None]:
    """Decorator for marking a seagull object's method as a post generate step."""
    method.__is_post_generate_method__ = True
    return method


LINK_ATTRS = (
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

    identifier: str = field(
        validator=validators.matches_re(
            r"^[a-z0-9][a-z0-9\-]{1,31}$", flags=re.IGNORECASE
        ),
        converter=lambda x: x.lower().strip(),
    )
    """Identifier for the type of intrasite link (NID of the URN)."""
    target: str = field(
        default="",
        # Convert %xx escapes back to unicode
        converter=lambda x: urllib.parse.unquote(x.strip()),
    )
    """Intrasite target(NSS of the URN, allowing leading slashes)."""
    tag: Tag | None = field(default=None, kw_only=True, repr=False)
    """HTML tag associated with the intrasite link."""
    attr: str | None = field(default=None, kw_only=True, repr=False)
    """HTML attribute in `tag` where the intrasite link resides."""

    @classmethod
    def from_string(
        cls, raw_urn: str, tag: Tag | None = None, attr: str | None = None
    ) -> Self:
        """Create a new `URN` object.

        :param raw_urn: Raw URN string.
        :param tag: Optional HTML tag.
        :param attr: Optional attribute.
        :return: A parsed `URN` object.
        """
        scheme, *remainder = raw_urn.split(":", 2)
        if scheme != cls.SCHEME_NAME or not remainder:  # noqa: PLR2004
            raise ValueError("Invalid URN string")
        return cls(*remainder, tag=tag, attr=attr)

    def __str__(self) -> str:
        return (
            f"{self.SCHEME_NAME}:{self.identifier}"
            f"{f':{self.target}' if self.target else ''}"
        )


@define
class GeneratorPaths:
    """Successfully processed and failed source paths returned by a generator."""

    processed: set[Path] = field(factory=set, init=False)
    failed: set[Path] = field(factory=set, init=False)

    def clear(self) -> None:
        """Empty both sets."""
        self.processed.clear()
        self.failed.clear()

    @property
    def all_paths(self) -> set[Path]:
        """All processed paths."""
        return self.processed.union(self.failed)


class SeagullStatus(StrEnum):
    """Statuses for a Seagull object."""

    PUBLISHED = auto()
    DRAFT = auto()
    HIDDEN = auto()
    SKIP = auto()


def load_object_from_module(value: str, default_module: str | None = None) -> object:
    """Load an object from an import path.

    :param value: Either an absolute or relative import path for an object. If
    `default_module` is set, it can also be the name of an object in `default_module`.
    :param default_module: Optional default module to use.
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


def validator_subclass_of[T](
    cls: type[T],
) -> Callable[[AttrsInstance, Attribute[type[T]], object], None]:
    if not isinstance(cls, type):
        raise TypeError("'cls' must be a class")

    def _validator_func(
        self: AttrsInstance, attr: Attribute[type[T]], value: object
    ) -> None:
        if not isinstance(value, type):
            raise ValueError(f"'{type(self).__name__}.{attr.name}': not a type")
        if not issubclass(value, cls):
            raise ValueError(
                f"'{type(self).__name__}.{attr.name}': "
                f"not a subclass of '{cls.__name__}'"
            )

    return _validator_func


def object_class_field[T](
    base_cls: type[T],
    *,
    is_default: bool = False,
    init: bool = True,
) -> type[T]:
    """Field for an object class attribute.

    This attribute accepts either a class that inherits from `base_cls` or a string
    giving its name. In the latter case, the name can be an absolute path to a module,
    or a relative path that will be resolved relative to `seagull.api.objects`.

    :param base_cls: Base class the attribute value must be of.
    :param is_default: Whether `base_cls` should be used as the default value.
    :param init: Whether this attribute is an init attribute.
    :return: An object class attribute.
    """

    def _converter_func(value: type[T] | str) -> type[T]:
        if isinstance(value, str):
            return cast(
                "type[T]", load_object_from_module(value, "seagull.api.objects")
            )
        return value

    if not isinstance(base_cls, type):
        raise TypeError("'base_cls' must be a class")

    if is_default:
        return field(
            default=base_cls,
            converter=_converter_func,
            validator=validator_subclass_of(base_cls),
            init=init,
        )
    return field(
        converter=_converter_func,
        validator=validator_subclass_of(base_cls),
        init=init,
    )
