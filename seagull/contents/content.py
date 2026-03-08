from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from slugify import slugify

from seagull.contents.seagull_object import SeagullObject, reserved_property

if TYPE_CHECKING:
    from datetime import datetime

    from seagull.contents.author import Author
    from seagull.contents.tag import Tag


class AuthorDescriptor[T: Content]:
    """A descriptor for the 'author' metadata key.

    This descriptor provides a shorthand for getting and setting the first author in the
    authors list of a `Content` object. This allows us to set either authors or author
    when initializing content.

    If both the `AuthorDescriptor` attribute and its associated authors list are set in
    the object creation, this attribute overrides the first author in the list.
    """

    def __set_name__(self, owner: type[T], name: str) -> None:
        """Store the attribute name and that of its associated authors list.

        :param owner: Owner class of the attribute.
        :param name: Name of the attribute.
        """
        # The associated author list is the name of the descriptor field, with an added
        # 's' at the end (author -> authors)
        self._author_list = f"{name}s"
        self._name = name

    def __get__(
        self, instance: Content | type[T], owner: type[T] | None = None
    ) -> Author | None:
        """Author attribute getter.

        Python dataclasses try accessing the attribute through the owner class to
        retrieve the default value of the descriptor. This method returns `None` as the
        default value, which is then used by `AuthorDescriptor.__set__` upon
        instantiation.

        :param instance: Instance holding the attribute, or owner class if `owner` is
        `None`.
        :param owner: Owner class of the attribute, or `None` if the attribute is
        accessed through the owner class.
        :return: An `Author` object, or `None` if the attribute is accessed through the
        class, or if there is no author in the authors list.
        :raise AttributeError: If the authors list attribute can't be found in the
        instance.
        """
        # Default value is set to None
        if instance is None:
            return None
        authors = getattr(instance, self._author_list)
        return authors[0] if authors else None

    def __set__(self, instance: T, value: Author | None) -> None:
        """Author attribute setter.

        Upon initialization of a python dataclass, this attribute will be set with the
        default value, which a dataclass retrieved by getting this descriptor attribute
        through the owner class instead of an instance. `AuthorDescriptor.__get__`
        returns `None` in this case. As such, a `None` value is a no-op, so that the
        first author in the authors list is not overridden.

        :param instance: Instance holding the attribute.
        :param value: New value for the author, or `None` for the initialization special
        case.
        :raise AttributeError: If the authors list attribute can't be found in the
        instance.
        """
        authors = getattr(instance, self._author_list)
        # No-op if the value is None
        if value is None:
            return
        # Update the first author...
        if authors:
            authors[0] = value
        # Or create it if the authors list was empty
        else:
            authors.append(value)


@dataclass(repr=False)
class Content(SeagullObject):
    """Base class for seagull content."""

    # FIXME use Enum
    allowed_statuses: ClassVar[tuple[str, ...]] = (
        "published",
        "hidden",
        "draft",
        "skip",
    )

    date: datetime | None = None
    modified: datetime | None = None
    summary: str = ""
    tags: list[Tag] = field(default_factory=list)
    authors: list[Author] = field(default_factory=list)
    author: AuthorDescriptor = AuthorDescriptor()
    status: str = "published"

    def __post_init__(self) -> None:
        super().__post_init__()

        if self.status not in self.allowed_statuses:
            raise ValueError(f"'{self.status}': invalid status")

        # Add tzinfo to our dates if necessary
        for key in ("date", "modified"):
            value: datetime
            if not (value := getattr(self, key)):
                continue
            if not value.tzinfo:
                setattr(self, key, value.replace(tzinfo=self.settings.timezone))

    def _setting_key_fragments(self, field_name: str) -> list[str]:
        fragments = super()._setting_key_fragments(field_name)
        # Add the draft fragment if the content is a draft
        if self.status == "draft":
            fragments.insert(0, "draft")

        return fragments

    def _slugify(self) -> str:
        # Get the source for the slug
        match self.settings.slugify_source, self.source_path:
            case ("title", _):
                value = self.title
            case ("basename", path) if path is not None:
                value = path.stem
            case _:
                value = None
        # If there is no source, return an empty slug
        if not value:
            return ""
        return slugify(text=value, **self.settings.slugify_settings)

    @reserved_property
    def locale_date(self) -> str:
        if self.date:
            return self.date.strftime(self.date_format)
        return ""

    @reserved_property
    def locale_modified(self) -> str:
        if self.modified:
            return self.modified.strftime(self.date_format)
        return ""

    @reserved_property
    def date_format(self) -> str:
        result = self.settings.date_formats.get(
            self.lang, self.settings.default_date_format
        )
        # FIXME tuple locale format
        if isinstance(result, tuple):
            return result[1]
        return result
