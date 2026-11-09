from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Self

from attrs import asdict, field, setters
from attrs.converters import optional
from slugify import slugify

from seagull.logging import PluralFormatter
from seagull.typeshed import SeagullStatus
from seagull.utils import (
    IntrasiteLink,
    path_repr_func,
)

from .utils import (
    SeagullObjectMeta,
    derived_field,
    in_as_dict,
    post_generate,
    seagull_object,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from seagull.typeshed import StrPath


@seagull_object
class BaseObject(ABC, metaclass=SeagullObjectMeta):
    """Base class for Seagull objects.

    A Seagull object is a structural element of a Seagull website: an article, an index,
    a static asset, etc.
    """

    site_lang: str = field(default="en", converter=str, on_setattr=setters.frozen)
    """Expected default language of the website."""
    site_url: str | None = field(
        default=None,
        converter=optional(
            # If we use an absolute URL, we must ensure there's a trailing slash so that
            # urljoin doesn't crap its pants later down the pipeline
            lambda x: f"{x}/" if not (x is None or str(x).endswith("/")) else str(x)
        ),
        on_setattr=setters.frozen,
    )
    """Base website URL for intrasite links. If `None`, relative URLs are used."""
    name: str = field(converter=str)
    """Name of the Seagull object."""
    slug: str = derived_field(converter=str, on_setattr=setters.frozen)
    """Slug that functions as an identifier for the object.

    Two objects of a given type who have the same slug should have a different `lang`
    attribute, indicating they're translated versions of one another."""
    lang: str = field(converter=str, on_setattr=setters.frozen)
    """Language of the object."""
    source_path: Path | None = field(
        default=None,
        converter=optional(Path),
        repr=path_repr_func(),
        on_setattr=setters.frozen,
    )
    """Optional relative source path, if the object was created from a file. It should
    be relative to `self._base_path`."""
    status: SeagullStatus = field(
        default=SeagullStatus.PUBLISHED, converter=SeagullStatus, repr=str
    )
    """Status of the seagull object."""
    translations: list[Self] = field(
        factory=list,
        init=False,
        repr=lambda val: f"({', '.join(v.lang for v in val)})",
    )
    """Register the translations of a given object."""
    save_as: Path = derived_field(converter=Path, repr=path_repr_func())
    """Output path for the object, relative to an output directory."""
    url: str = derived_field(converter=str)
    """URL for the resource."""
    metadata: dict[str, str] = field(factory=dict, repr=False)
    """Additional user-defined metadata."""
    base_path: Path | None = field(
        factory=Path.cwd,
        repr=False,
        on_setattr=setters.frozen,
    )
    """Keep track of the base path from which the object was created."""

    @lang.default
    def _attrs_default_lang(self) -> str:
        return self.site_lang

    def default_save_as(self) -> Path:
        # TODO user-customizable defaults?
        save_as = self.printable_name(separator="_") / Path(self.slug) / "index.html"
        if self.status == SeagullStatus.DRAFT:
            return "drafts" / save_as
        if not self.in_default_lang:
            return self.lang / save_as
        return save_as

    def default_url(self) -> str:
        return (
            f"{self.save_as.parent}/"
            if self.save_as.name in ("index.html", "index.htm")
            else str(self.save_as)
        )

    def default_slug(self) -> str:
        return slugify(self.name)

    def matches_intrasite_link(self, link: IntrasiteLink, obj: BaseObject) -> bool:
        """Test if an intrasite link matches the current object.

        Each type of seagull object can define its own ways of being identified from an
        intrasite link target.

        The base implementation adds support for two methods.
        * `filename:<path>`: matches objects by their source path. The path can be
        absolute (it is then rooted in `self._base_path`, or relative to the object
        from which the intrasite link comes from.
        * `<obj_type>:<slug>[:<lang>]`: matches objects of a given type (in snake case)
          by their slug. If the lang is omitted, the lang of the source object is used.

        :param link: Intrasite link.
        :param obj: Object from which the intrasite link comes from.
        :return: `True` if the current object matches the intrasite link.
        """
        if link.identifier == "filename":
            if not (self.source_path and obj.source_path):
                return False
            target_path = Path(link.target)
            # If it has a leading slash path, it is rooted in the base path;
            # otherwise, it is relative to the source object's source directory
            target_path = (
                self.base_path / target_path.relative_to("/")
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

    @in_as_dict
    @property
    def site_root(self) -> str:
        """URL of the site root, depending on whether we use relative URLs."""
        return (
            str(Path(".").relative_to(self.save_as.parent, walk_up=True))
            if self.site_url is None
            else self.site_url
        )

    def post_generation(self, objs: Mapping[type[Self], Iterable[Self]]) -> None:
        """Run the post-generation methods.

        A post-generation method is defined using the `@post_generate` decorator. It
        modifies the current object using information from all the other generated
        site's objects.

        :param objs: All the site's Seagull objects, mapped by type.
        """
        for method in self.__post_generate_methods__.values():
            method(self, objs)

    @post_generate
    def link_translations(
        self, objs: Mapping[type[BaseObject], Iterable[BaseObject]]
    ) -> None:
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

    @abstractmethod
    def save(self, output_path: StrPath, **kwargs: object) -> None:
        """Write the object to disk.

        :param output_path: Base output directory.
        :param kwargs: Additional rendering context.
        :raise OSError: If the object cannot be written to disk for any reason.
        """

    def as_dict(self) -> dict[str, object]:
        """Dictionary representation of the object."""
        return (
            asdict(
                self,
                # metadata dict is flattened into the return value, so we don't include
                # the metadata attribute; we don't include private attributes either
                filter=lambda a, _: a.name != "metadata" and not a.name.startswith("_"),
                # TODO smarter recursion so that seagull objects are as_dicted' too, but without going into an infinite recursion of conversion
                recurse=False,
            )
            # Flatten the metadata dictionary into the output
            | self.metadata
            # Also include properties decorated with `in_as_dict`
            | {name: getattr(self, name) for name in self.__as_dict_props__}
        )

    @in_as_dict
    @property
    def absolute_path(self) -> Path | None:
        """Absolute path of the object, if applicable."""
        if self.source_path is None:
            return None
        return (self.base_path / self.source_path).resolve()

    @in_as_dict
    @property
    def in_default_lang(self) -> bool:
        """Whether the object is in the default language."""
        return self.site_lang == self.lang

    @classmethod
    def printable_name(cls, count: int = 1, separator: str = " ") -> str:
        """Get a human-readable name for the object type.

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
