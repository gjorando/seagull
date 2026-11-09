from collections.abc import Callable, Mapping
from enum import IntEnum
from functools import cache
from typing import cast, get_origin, get_type_hints

from attrs import (
    NOTHING,
    Attribute,
    AttrsInstance,
    Converter,
    NothingType,
    field,
    fields_dict,
    has,
)
import click_extra as clickx

from seagull.api.utils import load_object_from_module
from seagull.logging import PluralFormatter, logger

SEAGULL_CLASS_METADATA_KEY: str = "seagull.class"
"""`attrs` metadata key for the fields that `from_config_dict` should recurse into.

The value of this metadata key can either be an `attrs` class, or a string for an init
attribute that stores the `attrs` class."""
SEAGULL_EXTENSION_CLASS_METADATA_KEY: str = "seagull.extension_class"
"""`attrs` metadata key for the fields that `from_config_dict` should recurse into.

The value of this metadata key should be an `attrs` class, and is used by `click_extra`
extension fields (either mappings, or with an explicit `click_extra.extension` metadata
key set to `True`)."""
SEAGULL_CLASS_BASE_MODULE_METADATA_KEY: str = "seagull.class_base_module"
"""`attrs` metadata key for the fields that `from_config_dict` should recurse into.

The value of this metadata must be a string that gives a default module for looking into
a class when the resolution of the `seagull.class` key yields a module path. The value
can be a class name, which will then be look into the module given by the
`seagull.class_base_module` metadata.
"""
SEAGULL_FLATTENED_CONFIG_METADATA_KEY: str = "seagull.flattened_config"
"""`attrs` metadata key for the fields that `from_config_dict` should recurse into.

If this key is `True`, then `from_config_dict` ignores the config path of the field
(its name, or the value of the `click_extra.config_path` metadata if defined) and
assumes the configuration keys for this field are flattened with the other attributes.
"""


class GeneratorPriority(IntEnum):
    """Priority shorthands for the `GeneratorConfig` objects."""

    PRE_CONTENT = -1000
    """Generators that must be called before the main content."""
    CONTENT = 0
    """Main content generators."""
    POST_CONTENT = 1000
    """Generators that must be called after the main content."""
    ASSETS = 2000
    """Static assets generators."""


@cache
def _safe_get_type_hints[T: AttrsInstance](cls: type[T]) -> dict[str, type]:
    try:
        return get_type_hints(cls)
    except (NameError, AttributeError, TypeError, RecursionError):
        return {}


def _is_extension_field(attr_field: Attribute) -> bool:
    """Return a boolean indicating whether an attribute is an extension field."""
    return bool(
        attr_field.metadata.get(clickx.config.schema.EXTENSION_METADATA_KEY, False)
    ) or get_origin(attr_field.type) in (dict, Mapping)


def _extract_dotted(conf: dict[str, object], path: str) -> tuple[object, bool]:
    """Extract a value at a dotted path from a nested dict.

    Taken from `click_extra`'s source code.

    :param conf: Nested dict to search.
    :param path: Config path. If empty, `(conf, True)` is returned.
    :return: `(result, True)` if found, `(None, False)` otherwise.
    """
    current = conf
    if not path:
        return current, True
    for part in path.split("."):
        if not (isinstance(current, dict) and part in current):
            return None, False
        current = current[part]
    return current, True


def _remove_dotted(conf: dict[str, object], path: str) -> dict[str, object]:
    """Remove a value at a dotted path from a config dict.

    Parent dicts that become empty after removal are also pruned.

    Taken from `click_extra`'s source code.

    :param conf: Nested dict to prune from.
    :param path: Config path.
    :return: A shallow copy of `conf` dict, pruned from the value at the dotted path.
    """
    path_root, _, path_remainder = path.partition(".")

    # If we only have a root, simply return a shallow copy of conf without the root key
    if not path_remainder:
        return {k: v for k, v in conf.items() if k != path_root}

    # If the path root doesn't exist in the conf, or is not a dict, return conf as-is
    if not isinstance(conf_part := conf.get(path_root), dict):
        return conf

    # Otherwise, recurse into this sub-config dict
    sub_conf = _remove_dotted(conf_part, path_remainder)

    # If the updated sub_conf is empty, it is not added back to the result
    result = {k: v for k, v in conf.items() if k != path_root}
    if sub_conf:
        result[path_root] = sub_conf
    return result


def from_config_dict[T: AttrsInstance](
    cls: type[T],
    config_dict: dict[str, object],
    *,
    base_config: dict[str, object] | None = None,
    strict: bool = False,
    normalize: bool = True,
) -> T:
    if not has(cls):
        raise TypeError(f"'{cls.__name__}': not an attrs class")
    # Store all fields that can be used for initialization
    hints = _safe_get_type_hints(cls)
    all_fields: dict[str, Attribute] = {
        name: f for name, f in fields_dict(cls).items() if f.init
    }

    # We normalize and flatten the keys, excepted extension points (either explicitly
    # defined with the 'click_extra.extension' metadata, or implicitly if it's a dict or
    # a Mapping), and attrs fields
    # TODO maybe not attribute fields but only instance and multi_config fields?
    opaque_keys = frozenset(
        name
        for name, f in all_fields.items()
        if has(hints.get(name, object)) or _is_extension_field(f)
    )
    if normalize:
        config_dict = clickx.normalize_config_keys(config_dict, opaque_keys=opaque_keys)
    config_dict = clickx.flatten_config_keys(config_dict, opaque_keys=opaque_keys)

    # Set the default values using the base config for all non-opaque keys
    base_config = config_dict.get("_base_config", base_config)
    for k in list(base_config):
        if k not in opaque_keys:
            config_dict.setdefault(k, base_config.pop(k))

    # Fail if we have unknown keys and strict mode is enabled
    unknown_keys = [k for k in config_dict if k not in all_fields]
    config_dict = {k: v for k, v in config_dict.items() if k in all_fields}
    if unknown_keys:
        msg = PluralFormatter().format(
            "Unknown configuration key{count:plural,s}: {keys}",
            count=len(unknown_keys),
            keys=", ".join(f"'{k}'" for k in unknown_keys),
        )
        if strict:
            raise ValueError(msg)
        logger.warning(msg)

    return cls(**config_dict)


def _get_target_cls(instance: AttrsInstance, attribute: Attribute) -> type:
    """Retrieve the target class for an instance field.

    :param instance: Owner object of the attribute.
    :param attribute: The instance field.
    :return: The target class.
    :raise RuntimeError: If `attribute` isn't an instance field.
    """
    if not (instance_class := attribute.metadata.get(SEAGULL_CLASS_METADATA_KEY)):
        raise RuntimeError(f"'{attribute.name}': not an instance field")
    instance_class: type | str
    if isinstance(instance_class, str):
        instance_class: type = getattr(instance, instance_class)
    return instance_class


def _instance_field_converter[Out: AttrsInstance](
    value: dict[str, object] | Out, self: AttrsInstance, attribute: Attribute
) -> Out:
    """Converter for instance fields.

    It is able to initialize the field from a config dictionary.

    :param value: Raw value to convert.
    :param attribute: The instance field.
    :param self: Owner object of the attribute.
    :return: An `attrs` object.
    """
    # If we do not have a dictionary, return the value immediately
    if not isinstance(value, dict):
        return value
    # Otherwise, we need to parse the configuration dictionary
    # We pop the base config from the config object...
    base_config = getattr(self, "_base_config", {}).pop(attribute.name, {})
    return from_config_dict(
        cast("type[AttrsInstance]", _get_target_cls(self, attribute)),
        value,
        # ... And use it for from_config_dict's base_config parameter
        base_config=base_config,
        **self.from_config_dict_settings,
    )


def _instance_field_validator(
    self: AttrsInstance, attribute: Attribute, value: AttrsInstance
) -> None:
    """Validator for instance fields.

    :param self: Owner object of the attribute.
    :param attribute: The instance field.
    :param value: Value to convert.
    :raise ValueError: If `value` is not an instance of the instance class.
    """
    instance_class = _get_target_cls(self, attribute)
    if not isinstance(value, instance_class):
        raise ValueError(f"'{value}': not a '{instance_class.__name__}' instance")


def _instance_class_field_converter[Out: AttrsInstance](
    value: str | type[Out], attribute: Attribute
) -> type[Out]:
    """Converter for instance class fields.

    :param value: Raw value to convert. This could be a string for the name of the
    class, that would then be dynamically loaded.
    :param attribute: The instance field.
    :return: An `attrs` class.
    """
    # If we have a string, try to load the class
    if isinstance(value, str):
        return cast(
            "type[Out]",
            load_object_from_module(
                value,
                attribute.metadata.get(SEAGULL_CLASS_BASE_MODULE_METADATA_KEY),
            ),
        )
    return value


def _instance_class_field_validator(
    self: AttrsInstance, attribute: Attribute, value: AttrsInstance
) -> None:
    """Validator for instance fields.

    :param self: Owner object of the attribute.
    :param attribute: The instance field.
    :param value: Value to convert.
    :raise ValueError: If `value` is not an instance of the instance class.
    """
    if not (isinstance(value, type) and has(value)):
        raise ValueError(
            f"'{value.__name__ if isinstance(value, type) else value}': "
            f"not an attrs class"
        )


def instance_class_field[T: AttrsInstance](
    *,
    default: type[T] | NothingType = NOTHING,
    base_module: str | None = None,
) -> type[T]:
    """Companion field of `instance_field`, that stores the instance class.

    :param default: Default class to use.
    :param base_module: Optionally, the base module of the target class (see
    `instance_class()`).
    :return: An `Attribute` object for an instance class field.
    :raise RuntimeError: If `default` is a type that's not an `attrs` class.
    """
    if isinstance(default, type) and not has(default):
        raise RuntimeError(f"'{default.__name__}': not an attrs class")
    metadata = {}
    if base_module:
        metadata[SEAGULL_CLASS_BASE_MODULE_METADATA_KEY] = str(base_module)
    # TODO validate based on type hint (subclass)
    if default is not NOTHING:
        return field(
            default=default,
            metadata=metadata,
            converter=Converter(_instance_class_field_converter, takes_field=True),
            validator=_instance_class_field_validator,
        )
    return field(
        metadata=metadata,
        converter=Converter(_instance_class_field_converter, takes_field=True),
        validator=_instance_class_field_validator,
    )


def instance_field[T: AttrsInstance](
    *,
    target_cls: type[T] | str = "instance_class",
    flattened: bool = False,
    config_path: str | None = None,
) -> T:
    """Field for instantiating an `attrs` class from a config dictionary.

    :param target_cls: The type of the instance field (it must be an `attrs` class), or
    a string targeting another field that will store the type.
    :param flattened: Whether the config dictionary flattens the instance configuration.
    :param config_path: Optionally, the dotted configuration path for the instance. By
    default, the attribute name will be used. It is ignored if `flattened` is `True`.
    :return: An `Attribute` object for an instance field.
    :raise RuntimeError: If `target_cls` is a type that's not an `attrs` class.
    """
    if not (
        isinstance(target_cls, str)
        or (isinstance(target_cls, type) and has(target_cls))
    ):
        raise RuntimeError(f"'{target_cls}': not a valid value for target_cls")

    metadata = {
        SEAGULL_CLASS_METADATA_KEY: target_cls,
        SEAGULL_FLATTENED_CONFIG_METADATA_KEY: bool(flattened),
    }
    if not (flattened or config_path is None):
        metadata[clickx.config.schema.CONFIG_PATH_METADATA_KEY] = str(config_path)
    return field(
        metadata=metadata,
        converter=Converter(
            _instance_field_converter, takes_self=True, takes_field=True
        ),
        validator=_instance_field_validator,
    )


def base_config_field(
    extra_instance_defaults: Callable[
        [AttrsInstance, dict[str, object]], dict[str, object]
    ]
    | None = None,
    /,
) -> dict[str, object]:
    """Field for storing the base configuration in a config object.

    :param extra_instance_defaults: If set, this allows for runtime defaults based on
    the parent. It must be a callable that takes a partially initialized `BaseConfig`
    instance and the default dictionary for the `instance` object, and returns the
    updated default dictionary.
    :return: An `Attribute` object for a base config field.
    """
    if extra_instance_defaults:

        def converter_func(
            v: dict[str, object], self: AttrsInstance
        ) -> dict[str, object]:
            v["instance"] = extra_instance_defaults(
                self,
                cast("dict[str, object]", v.get("instance", {})),
            )
            return v

        return field(
            alias="_base_config", converter=Converter(converter_func, takes_self=True)
        )
    return field(alias="_base_config")
