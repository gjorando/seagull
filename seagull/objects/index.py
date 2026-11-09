from pathlib import Path
from typing import TYPE_CHECKING, Self

from attrs import Attribute, field

from seagull.typeshed import SeagullStatus
from seagull.utils import object_class_converter

from .base_object import BaseObject
from .content import Content
from .utils import post_generate, seagull_object

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@seagull_object
class Index[T: BaseObject](Content):
    """An index holds a list of seagull objects of a given type."""

    # TODO maybe a more general "filtering" method?
    object_class: type[T] = field(
        converter=object_class_converter(default_module="seagull.objects"),
    )
    """Type of objects held by the index."""
    objects: list[T] = field(factory=list, converter=lambda v: list(v), init=False)
    """List of objects held by the index."""
    auto_index: bool = field(default=False, init=False)
    """Indicates an auto-generated index."""
    # FIXME we need to entirely redefine this field in order to be able to use object_class in the default method, there has to be a better way to do that
    # template: str = field()
    #
    # @template.default
    # def _attrs_default_template(self) -> str:
    #     return self.object_class.printable_name(count=2, separator="_")

    def default_save_as(self) -> Path:
        save_as = Path(self.slug) / "index.html"
        if self.status == SeagullStatus.DRAFT:
            return "drafts" / self.printable_name(separator="_") / save_as
        if not self.in_default_lang:
            return self.lang / save_as
        return save_as

    @objects.validator
    def _attrs_validator_objects(self, attr: Attribute, value: list[T]) -> None:
        """Ensure `objects` only holds instances of `object_class`."""
        del attr  # Unused argument
        if not all(isinstance(o, self.object_class) for o in value):
            raise ValueError(
                f"Not all objects in index '{self}' are "
                f"instances of '{self.object_class.__name__}'"
            )

    @object_class.validator
    def _attrs_object_class_validator(self, attribute: Attribute, value: type) -> None:
        """Ensure `object_class` is a subclass of `BaseObject`."""
        if not (isinstance(value, type) and issubclass(value, BaseObject)):
            raise ValueError(
                f"'{attribute.name}' must be a subtype of 'seagull.objects.BaseObject'"
            )

    @post_generate
    def populate_index(
        self,
        objs: Mapping[type[Self], Iterable[Self]],
    ) -> None:
        """Populate the index with the appropriate Seagull objects."""

        def filter_func(obj: BaseObject) -> bool:
            return obj.lang == self.lang and obj.status not in (
                SeagullStatus.DRAFT,
                SeagullStatus.HIDDEN,
            )

        self.objects.extend(filter(filter_func, objs.get(self.object_class, [])))
