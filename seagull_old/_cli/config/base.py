from pathlib import Path
import tomllib
from typing import Self, cast, overload

from attrs import (
    Attribute,
    AttrsInstance,
    Converter,
    define,
    field,
    fields_dict,
)
import click_extra as clickx

from seagull.logging import logger

from .utils import (
    SEAGULL_EXTENSION_CLASS_METADATA_KEY,
    SEAGULL_FLATTENED_CONFIG_METADATA_KEY,
    _extract_dotted,
    _remove_dotted,
    base_config_field,
    from_config_dict,
    instance_class_field,
    instance_field,
)


def _multi_config_dict_converter[Out: BaseConfig](
    value: dict[str, dict[str, object] | Out], self: BaseConfig, attribute: Attribute
) -> dict[str, Out]:
    """Converter for multi config dictionary extension fields.

    :param value: Raw value to convert.
    :param self: Owner object of the attribute.
    :param attribute: The multi config field.
    :return: A dictionary of configuration objects.
    """
    target_cls: type[BaseConfig] = attribute.metadata[
        SEAGULL_EXTENSION_CLASS_METADATA_KEY
    ]
    # We pop the base config from the config object...
    base_config: dict[str, dict[str, object]] = getattr(self, "_base_config", {}).pop(
        attribute.name, {}
    )
    # And merge each sub-config
    for k, v in base_config.items():
        value[k] = value.get(k, {}) | {"_base_config": v}
    return {
        k: v
        if isinstance(v, BaseConfig)
        else target_cls.from_config_dict(
            v | {"_parent": self},
            **self.from_config_dict_settings,
        )
        for k, v in value.items()
    }


def _multi_config_list_converter[Out: BaseConfig](
    value: list[dict[str, object] | Out], self: BaseConfig, attribute: Attribute
) -> list[Out]:
    """Converter for multi config list extension fields.

    :param value: Raw value to convert.
    :param self: Owner object of the attribute.
    :param attribute: The multi config field.
    :return: A list of configuration objects.
    """
    target_cls: type[BaseConfig] = attribute.metadata[
        SEAGULL_EXTENSION_CLASS_METADATA_KEY
    ]
    # The base config is used as a default
    value = value or getattr(self, "_base_config", {}).pop(attribute.name, {})
    return [
        v
        if isinstance(v, BaseConfig)
        else target_cls.from_config_dict(
            v | {"_parent": self},
            **self.from_config_dict_settings,
        )
        for v in value
    ]


@overload
def multi_config_field[T: BaseConfig](
    *,
    target_config: type[T],
) -> dict[str, T]: ...


@overload
def multi_config_field[T: BaseConfig](
    *,
    target_config: type[T],
    extension_type: type[dict],
) -> dict[str, T]: ...


@overload
def multi_config_field[T: BaseConfig](
    *,
    target_config: type[T],
    extension_type: type[list],
) -> list[T]: ...


def multi_config_field(*, target_config, extension_type=dict):
    """Field for extension points that configure multiple instances.

    The extension point can be a mapping or a sequence.
    :param target_config: Target config class.
    :param extension_type: Type of extension point, either a dictionary or a list.
    :return: An `Attribute` object for a multi config field.
    :raise RuntimeError: If `target_config` is not a configuration class.
    """
    if not issubclass(target_config, BaseConfig):
        raise RuntimeError(f"'{target_config.__name__}': not a configuration class")
    metadata = {
        SEAGULL_EXTENSION_CLASS_METADATA_KEY: target_config,
        clickx.config.schema.EXTENSION_METADATA_KEY: True,
    }
    if extension_type is dict:
        return field(
            factory=dict,
            metadata=metadata,
            converter=Converter(
                _multi_config_dict_converter, takes_self=True, takes_field=True
            ),
        )
    return field(
        factory=list,
        metadata=metadata,
        converter=Converter(
            _multi_config_list_converter, takes_self=True, takes_field=True
        ),
    )


def _load_base_config(path: Path) -> dict[str, object]:
    """Load the base configuration from the config module.

    :param path: Path to the base TOML config file.
    :return: The parsed file. If the path doesn't point to an existing file, or if the
    TOML content couldn't be parsed, or if the parsed content doesn't have a root
    "seagull" key, return an empty dictionary (an error is logged).
    """
    try:
        with open(path, "rb") as fp:
            return tomllib.load(fp)["seagull"]
    except FileNotFoundError:
        logger.error(f"Base configuration file not found in '{path}'.")
    except tomllib.TOMLDecodeError:
        logger.error(f"Couldn't parse the base configuration file '{path}'.")
    except KeyError:
        logger.error(f"Couldn't find a base configuration in '{path}'.")
    return {}


@define(kw_only=True)
class BaseConfig[T]:
    """Base class for configuration schemas.

    A configuration schema instantiates a class based on a passed configuration, usually
    sourced from the command line/configuration file.

    This class and its subclasses should never be instantiated through the regular
    `cls()` call. Instead, use `cls.from_config_dict`, passing a parsed configuration
    dictionary as the first argument.
    """

    _strict: bool = field(default=False, alias="_strict")
    _normalize: bool = field(default=True, alias="_normalize")
    _parent: BaseConfig | None = field(default=None, alias="_parent")
    """Parent configuration object for multi-config fields."""
    _base_config: dict[str, object] = base_config_field()
    """Base configuration for the current config object."""
    instance_class: type[T] = instance_class_field()
    """Class of object to create."""
    instance: T = instance_field()
    """Instantiated object."""

    @classmethod
    def from_config_dict(
        cls,
        config_dict: dict[str, object],
        *,
        strict: bool = False,
        normalize: bool = True,
    ) -> Self:
        """Build the configuration object from a raw configuration dict.

        :param config_dict: Raw configuration dictionary, usually loaded from a config
        file through the command-line front-end.
        section in `BaseConfig._base_config`.
        :param strict: Whether to fail on unknown key metadata.
        :param normalize: Whether to normalize the config keys.
        :return: A new configuration object.
        """
        attribute = fields_dict(cls)["instance"]
        # Init fields of cls, mapped by name
        all_fields = dict(filter(lambda x: x[1].init, fields_dict(cls).items()))
        # Fetch the base configuration
        base_config = config_dict.pop("_base_config", None)
        # If there's no _base_config key in the dict, load the full root config
        if base_config is None:
            base_config = _load_base_config(Path(__file__).parent / "base_config.toml")
        base_config: dict[str, object]
        # We need to pre-normalize the top-level keys
        if normalize:
            config_dict = clickx.normalize_config_keys(
                config_dict, opaque_keys=frozenset(config_dict.keys())
            )
            base_config = clickx.normalize_config_keys(
                base_config, frozenset(base_config.keys())
            )
        # If the configuration for instance is flattened, we need to separate
        # the keys for the instance and those for the config object itself
        if attribute.metadata.get(SEAGULL_FLATTENED_CONFIG_METADATA_KEY, False):
            # Separate them from the remaining config keys
            obj_config = {k: v for k, v in config_dict.items() if k not in all_fields}
            config_dict = {k: v for k, v in config_dict.items() if k in all_fields}
            base_obj_config = {
                k: v for k, v in base_config.items() if k not in all_fields
            }
            base_config = {k: v for k, v in base_config.items() if k in all_fields}
        # Otherwise, get its config path
        else:
            # If a click_extra.config_path wasn't given, its path is the attribute name
            config_path = attribute.metadata.get(
                clickx.config.schema.CONFIG_PATH_METADATA_KEY, attribute.name
            )
            # Get the base configuration path
            # We try to find the path inside the config dict for instance's config
            obj_config, found = _extract_dotted(config_dict, config_path)
            base_obj_config, base_found = _extract_dotted(base_config, config_path)
            # If we did find it, and it is a dictionary, remove it from the config dict
            if found and isinstance(obj_config, dict):
                config_dict = _remove_dotted(config_dict, config_path)
            #  Otherwise, use an empty dict for the instance's configuration
            else:
                obj_config = {}
            # Same for the bae
            if base_found and isinstance(base_obj_config, dict):
                base_config = _remove_dotted(base_config, config_path)
            else:
                base_obj_config = {}
        # Put the configuration back into its proper place
        config_dict[attribute.name] = obj_config
        base_config[attribute.name] = base_obj_config

        # If strict mode is disabled, prune unknown keys
        if not strict:
            config_dict = {k: v for k, v in config_dict.items() if k in all_fields}
        config_dict["_base_config"] = base_config
        config_dict["_strict"] = strict
        config_dict["_normalize"] = normalize
        # We carry on with the general from_config_dict function
        return from_config_dict(
            cls,
            config_dict,
            strict=strict,
            normalize=normalize,
        )

    @property
    def base_config(self) -> dict[str, object]:
        """Base configuration dictionary."""
        return self._base_config

    @property
    def parent(self) -> BaseConfig | None:
        """Parent configuration object."""
        return self._parent

    @property
    def from_config_dict_settings(self) -> dict[str, bool]:
        """`strict` and `normalize` settings."""
        return {
            "strict": self._strict,
            "normalize": self._normalize,
        }

    @property
    def root_config(self) -> BaseConfig:
        """Get the root configuration object."""
        current = self
        while current.parent is not None:
            current = cast("BaseConfig", current.parent)
        return current
