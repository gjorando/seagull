import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Self

from attrs import asdict, field, fields_dict
from attrs.converters import optional, pipe
from slugify import slugify

from seagull.api.utils import (
    IntrasiteLink,
    SeagullStatus,
    post_generate,
    seagull_object,
)
from seagull.logging import PluralFormatter

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class SeagullObjectMeta(type):
    """Metaclass for seagull objects.

    This metaclass allows for registering post generate steps.
    """

    def __init__(cls, name: str, bases: tuple[type], dct: dict[str, object]):
        super().__init__(name, bases, dct)
        cls.__post_generate_methods__ = {}
        # Inherit the post generate steps from base classes
        for base in bases:
            cls.__post_generate_methods__.update(
                getattr(base, "__post_generate_methods__", {})
            )
        # Record post generate methods defined in the new class
        for obj_name, obj in dct.items():
            if getattr(obj, "__is_post_generate_method__", False):
                cls.__post_generate_methods__[obj_name] = obj


@seagull_object
class SeagullObject(c):
    """Base class for Seagull objects."""

    name: str = field(converter=str)
    """Name of the object."""
    slug: str = field(repr=False)
    """Slug of the object."""
    lang: str = field(default="en", converter=str)
    """Language for the object."""
    # FIXME Maybe the best solution is to remove save_as?
    default_lang: str = field(default="en", converter=str)
    """Site's default lang."""
    save_as: Path = field(default=None, converter=optional(Path), repr=False)
    """Destination path for the object (relative to an output path)."""
    url: str = field(default=None, converter=optional(str))
    """URL path for the object."""
    source_path: Path | str | None = field(
        default=None, converter=optional(Path), repr=lambda val: f"'{val}'"
    )
    """Optional source path if the object was created from a file."""
    source_root: Path | str = field(
        default=".", converter=pipe(Path, Path.resolve), repr=False
    )
    """Root of the source path. Meaningless if `source_path` is None."""
    status: SeagullStatus = field(
        default=SeagullStatus.PUBLISHED, converter=SeagullStatus
    )
    """Status of the seagull object."""
    translations: list[Self] = field(
        factory=list,
        init=False,
        repr=lambda val: f"({', '.join(v.lang for v in val)})",
    )
    metadata: dict[str, str] = field(factory=dict, repr=False)
    """Additional user-defined metadata."""

    def __attrs_post_init__(self) -> None:
        # TODO mechanism to customize defaults
        if not self.save_as:
            self.save_as = "{obj_type}/{slug}/index.html".format(
                obj_type=self.printable_name(separator="_"),
                obj_type_plural=self.printable_name(count=2, separator="_"),
                **self.as_dict(),
            )
            if self.status == SeagullStatus.DRAFT:
                self.save_as = "drafts" / self.save_as
            if not self.in_default_lang:
                self.save_as = self.lang / self.save_as
        if not self.url:
            self.url = (
                f"{self.save_as.parent}/"
                if self.save_as.name in ("index.html", "index.htm")
                else str(self.save_as)
            )

    @slug.default
    def _default_slug(self) -> str:
        return slugify(self.name)

    @classmethod
    def from_parsed(cls, **kwargs: object) -> Self:
        """Builder method for parsers.

        This class method quietly filters out arguments that are not present in the
        signature of `__init__`, and puts them in the `metadata` attribute.
        """
        # Regular fields are init fields. We rule-out 'metadata' as a regular field as
        # well, because we do not want a user field named 'metadata' to override ours.
        all_fields = {
            k: v for k, v in fields_dict(cls).items() if v.init and k != "metadata"
        }
        attributes = {k: v for k, v in kwargs.items() if k in all_fields}
        attributes["metadata"] = {
            k: v for k, v in kwargs.items() if k not in all_fields
        }
        return cls(**attributes)

    def matches_intrasite_link(self, link: IntrasiteLink, obj: SeagullObject) -> bool:
        """Test if an intrasite link matches the current object.

        Each type of seagull object can define its own ways of being identified from an
        intrasite link target.

        The base implementation adds support for two methods.
        * `filename:<path>`: matches objects by their source path. The path can be
        absolute, or relative to the object from which the intrasite link comes from.
        * `<obj_type>:<slug>[:<lang>]`: matches objects of a given type (in snake case)
          by their slug. If the lang is omitted, the lang of the source object is used.

        :param link: Intrasite link.
        :param obj: Object from which the intrasite link comes from.
        :return: `True` if the current object matches the intrasite link.
        """
        if link.identifier == "filename":
            target_path = Path(link.target)
            # If it has a leading slash path, it is rooted in the source root;
            # otherwise, it is relative to the source object's source directory
            target_path = (
                self.source_root / target_path.relative_to("/")
                if target_path.is_relative_to("/")
                else obj.source_path.parent / target_path
            )
            return target_path.resolve() == self.source_path.resolve()
        if link.identifier == self.printable_name(separator="_"):
            left_part, _, right_part = link.target.rpartition(":")
            target_slug = left_part or right_part
            target_lang = right_part if left_part else obj.lang
            return target_slug == self.slug and target_lang == self.lang
        return False

    def post_generation(self, objs: Mapping[type[Self], Iterable[Self]]) -> None:
        """Run the cleaning steps.

        :param objs: All generated objects, mapped by type.
        """
        for method in self.__post_generate_methods__.values():
            method(self, objs)

    @post_generate
    def link_translations(self, objs: Mapping[type[Self], Iterable[Self]]) -> None:
        """Link object translations.

        This method populates the `translations` attribute from all objects of the same
        type; the slug is used to identify those translations.

        :param objs: All generated objects, mapped by type.
        """
        candidates = objs.get(type(self), [])
        self.translations.extend(
            filter(
                # Look for objects with the same slug
                lambda o: o.slug == self.slug
                # Do not put `self` in its own list of translations
                and o is not self
                # Do not put the object twice in the list of translations
                and o not in self.translations,
                candidates,
            )
        )

    def as_dict(self) -> dict[str, object]:
        """Dictionary representation of the object."""
        return (
            asdict(
                self,
                # metadata dict is flattened into the return value
                filter=lambda a, _: a.name != "metadata",
                recurse=False,
            )
            | self.metadata
            # TODO automatically add some properties
            | {
                "relative_source_path": self.relative_source_path,
                "site_root": self.site_root,
                "in_default_lang": self.in_default_lang,
            }
        )

    @property
    def relative_source_path(self) -> Path | None:
        """Source path, relative to the source root."""
        if self.source_path:
            return self.source_path.resolve().relative_to(self.source_root)
        return None

    @property
    def site_root(self) -> str:
        """Relative site root.

        :return: Returns the URL to the site root, relative to the current object's
        output directory.
        """
        if self.save_as:
            return str(Path(".").relative_to(self.save_as.parent, walk_up=True))
        # This should only occur during post init if save_as wasn't passed
        return ""

    @property
    def in_default_lang(self) -> bool:
        """Whether the object's lang is the default lang."""
        return self.lang == self.default_lang

    @classmethod
    def printable_name(cls, count: int = 1, separator: str = " ") -> str:
        """Get a human-readable name for the class.

        :param count: Count value for pluralization.
        :param separator: Separator to put between words.
        :return: the name of the class, pluralized. Uppercase characters are converted
        to lowercase, and preceded by the separator (excepted for the first character of
        the name, that's lowercased without prepending a separator).
        """
        cls_name = cls.__name__
        name = (
            cls_name[0].lower()  # No leading separator
            + "".join(
                c if c.islower() else f"{separator}{c.lower()}" for c in cls_name[1:]
            )
        ).strip()

        if name.endswith("y"):
            return PluralFormatter().format(
                f"{name[:-1]}{{count:plural,y,ies}}", count=count
            )
        return PluralFormatter().format(f"{name}{{count:plural,s}}", count=count)

    def __str__(self) -> str:
        """The string representation of an object is its slug."""
        return self.slug
