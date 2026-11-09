from collections.abc import Iterable, Mapping
from typing import Self

from attrs import Attribute, field

from seagull.api.utils import object_class_field, post_generate, seagull_object

from .content import Content
from .seagull_object import SeagullObject


@seagull_object
class Index[T: SeagullObject](Content):
    """An index holds a list of seagull objects of a certain type."""

    object_class: type[T] = object_class_field(SeagullObject)
    """Type of objects held by the index."""
    objects: list[T] = field(factory=list, converter=lambda v: list(v), init=False)
    """List of objects held by the index."""

    @objects.validator
    def _validator_objects(self, attr: Attribute, value: list[T]) -> None:
        """Ensure `objects` only holds instances of `object_class`."""
        del attr  # Unused argument
        if not all(isinstance(o, self.object_class) for o in value):
            raise ValueError(
                f"Not all objects in index '{self}' are "
                f"instances of '{self.object_class.__name__}'"
            )

    @post_generate
    def record_objects(
        self,
        objs: Mapping[type[Self], Iterable[Self]],
    ) -> None:
        """Record objects held by the index.

        :param objs: All generated objects, mapped by type.
        """
        self.objects = list(
            filter(
                lambda x: x.lang == self.lang,
                objs.get(self.object_class, []),
            )
        )
