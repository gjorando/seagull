from abc import ABCMeta
from typing import TYPE_CHECKING, dataclass_transform

from attrs import converters, define, field, validators

if TYPE_CHECKING:
    from attrs import Attribute, AttrsInstance

    from seagull.typeshed import PostGenerateMethod

DERIVED_FIELD_METADATA = "__seagull_derived_field"
DERIVED_FIELD_DEFAULT_NAME_METADATA = "__seagull_derived_field_default_name"


def derived_field[T](
    *,
    default_name: str | None = None,
    metadata: dict[str, object] | None = None,
    **kwargs: object,
) -> T:
    """Decorator for derived seagull object fields.

    A derived field is computed upon each access, like a property. However, it can also
    be overridden by the user if desired.
    """
    metadata = metadata or {}
    metadata[DERIVED_FIELD_METADATA] = True
    metadata[DERIVED_FIELD_DEFAULT_NAME_METADATA] = default_name
    return field(metadata=metadata, **kwargs)


def _derived_field_property[T](attr_name: str, default_name: str) -> property:
    """Create the property for a derived field."""

    def _fget(self: AttrsInstance) -> T:
        if (r := getattr(self, attr_name)) is not None:
            return r
        return getattr(self, default_name)()

    def _fset(self: AttrsInstance, value: object) -> None:
        setattr(
            self,
            attr_name,
            value,
        )

    return property(fget=_fget, fset=_fset)


def _seagull_object_field_transformer(
    cls: type, fields: list[Attribute]
) -> list[Attribute]:
    """Field transformer for Seagull objects.

    It takes care of derived fields."""
    result = []
    # For each derived field, add a corresponding property
    for f in fields:
        if not f.metadata.get(DERIVED_FIELD_METADATA, False):
            result.append(f)
            continue
        # Derived fields can be None
        new_field = f.evolve(default=None)
        # Ensure the derived field is private
        if not f.name.startswith("_"):
            new_field = f.evolve(name=f"_{f.name}")
        # Converters and validators are optional, since the value can be None
        if f.converter:
            new_field = new_field.evolve(converter=converters.optional(f.converter))
        if f.validator:
            new_field = new_field.evolve(validator=validators.optional(f.validator))
        setattr(
            cls,
            # The property's name doesn't have the leading underscore
            new_field.name[1:],
            _derived_field_property(
                new_field.name,
                new_field.metadata.get(DERIVED_FIELD_DEFAULT_NAME_METADATA, None)
                or f"default{new_field.name}",
            ),
        )
        result.append(new_field)
    return result


# TODO modify the repr function to handle the derived properties properly
@dataclass_transform(kw_only_default=True, field_specifiers=(derived_field, field))
def seagull_object[C: type](cls_: C) -> C:
    """Decorator for Seagull objects."""
    return define(
        cls_, field_transformer=_seagull_object_field_transformer, kw_only=True
    )


def post_generate(
    method: PostGenerateMethod,
) -> PostGenerateMethod:
    """Decorator for marking a seagull object's method as a post generate step."""
    method.__is_post_generate_method__ = True
    return method


def in_as_dict(method: property) -> property:
    """Decorator for properties in Seagull objects.

    A property marked with this decorator will appear in the output of Seagull objects'
    `as_dict` method.

    :param method: Property to decorate.
    :return: The property.
    :raise TypeError: If `method` is not a property.
    """
    if not isinstance(method, property):
        raise TypeError(f"'{method.__name__}' is not a property")
    method.fget.__in_as_dict__ = True
    return method


class SeagullObjectMeta(ABCMeta):
    """Metaclass for Seagull objects."""

    def __init__(cls, name: str, bases: tuple[type], dct: dict[str, object]):
        super().__init__(name, bases, dct)
        cls.__post_generate_methods__ = {}
        cls.__as_dict_props__ = set()
        # Inherit the post generate steps and as_dict props from base classes
        for base in bases:
            cls.__post_generate_methods__.update(
                getattr(base, "__post_generate_methods__", {})
            )
            cls.__as_dict_props__.update(getattr(base, "__as_dict_props__", set()))
        # Record post generate methods and as_dict props defined in the new class
        for obj_name, obj in dct.items():
            if getattr(obj, "__is_post_generate_method__", False):
                cls.__post_generate_methods__[obj_name] = obj
            if isinstance(obj, property) and getattr(obj.fget, "__in_as_dict__", False):
                cls.__as_dict_props__.add(obj_name)
