import ipaddress
import json
import logging
from logging import Logger
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING, Any

import click_extra as clickx

from seagull.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterable
    from ipaddress import IPv4Address, IPv6Address


class JsonKeyValueType(clickx.ParamType):
    """Validate A JSON key-value pair."""

    name = "key-value pair"

    def convert(
        self, value: str, param: clickx.Parameter | None, ctx: clickx.Context | None
    ) -> tuple[str, Any]:
        """Validation callback for a key-value pair.

        It fails if `value` cannot be parsed to a valid JSON key-value pair.
        """
        try:
            value = str(value)
            k, v = value.split("=", 1)
            v = json.loads(v)
            return k, v
        except ValueError, json.decoder.JSONDecodeError:
            self.fail(
                f"{value!r} cannot be parsed to a valid json key-value pair", param, ctx
            )

    @staticmethod
    def option_callback(
        ctx: clickx.Context | None,
        param: clickx.Parameter | None,
        value: tuple[str, str] | tuple[tuple[str, str]],
    ) -> dict[str, str]:
        """Callback for an option of type `JsonKeyValueType`.

        It converts the key-value tuple(s) into a dictionary. Both multiple and
        non-multiple options are supported.
        """
        if not value:  # Empty value returns an empty dictionary
            return {}
        # For non-multiple parameters, value is a single tuple[str, str]
        if not param.multiple:
            value = (value,)
        try:
            return dict(value)
        except ValueError:
            raise clickx.BadParameter("Invalid key-value pair(s)", ctx, param) from None


def parse_overrides(settings_path: Path, overrides: dict[str, Any]) -> None:
    """Parse the command line overrides inplace.

    It keeps valid setting keys, extend it with `extra_settings`, and removes unset
    values.
    :param settings_path: Path to the settings file.
    :param overrides: Parsed command line options.
    """
    # The working directory will be the directory containing the settings file
    cwd = settings_path.parent
    # Put the extra settings aside for now
    extra_settings = overrides.pop("extra_settings", {})
    for key in list(overrides):
        value = overrides.pop(key)
        # Rewrite all path overrides so that they're relative to the settings file
        if isinstance(value, Path):
            value = value.relative_to(cwd, walk_up=True)
        # Only re-insert valid setting keys; "path" (lowercase) is valid because click
        # forces the names of arguments to be lowercase
        if not (Settings.is_valid_param_key(key) or key == "path"):
            continue
        # If a value override is unset, ignore it so that it doesn't override the
        # value in the settings file
        if value is None:
            continue
        overrides[key.upper()] = value
    # Update our params with the extra settings overrides
    overrides.update(extra_settings)


def do_print_settings(ctx: clickx.Context, _: clickx.Parameter, value: object) -> None:
    """Print the settings on the command line and exit."""
    if not value or ctx.resilient_parsing:
        return
    # Retrieve the settings path
    settings_path = ctx.params.pop("settings_path", None)
    # Fallback to the parameter's default value
    if not settings_path:
        settings_path = Path(
            next(
                filter(lambda p: p.name == "settings_path", ctx.command.params)
            ).default
        )
        if not settings_path.is_file():
            ctx.fail(f"Settings file '{settings_path}' not found.")
    # Parse the overrides
    overrides = ctx.params
    parse_overrides(settings_path, overrides)
    # Load the settings and display its values
    settings = Settings.from_settings_file(settings_path, **overrides)
    settings_dict = settings.as_dict()
    for k, v in settings_dict.items():
        if k.startswith("_"):
            continue
        match v:
            case dict() | list():
                display_value = pformat(v)
            case Path() | str():
                display_value = f"'{v}'"
            case _:
                display_value = str(v)
        clickx.echo(f"{k.upper()}={display_value}")
    ctx.exit()


class IPAddressType(clickx.ParamType):
    """Validate an IP address."""

    name = "ip address"

    def convert(
        self, value: str, param: clickx.Parameter | None, ctx: clickx.Context | None
    ) -> IPv4Address | IPv6Address:
        """Validation callback for an IP address.

        It converts the value to an IP address object from Python's `ipaddress` builtin
        module.
        """
        try:
            return ipaddress.ip_address(value)
        except ValueError:
            raise clickx.BadParameter("Invalid IP address", ctx, param) from None


class CliVerboseOption(clickx.VerboseOption):
    """Verbose option without click_extra's clutter.

    A simple override of click_extra.VerboseOption that doesn't change click_extra's
    internal log level.
    """

    @property
    def all_loggers(self) -> Iterable[Logger]:
        yield logging.getLogger(self.logger_name)


class CliVerbosityOption(clickx.VerbosityOption):
    """Verbosity without click_extra's clutter.

    A simple override of click_extra.VerbosityOption that doesn't change click_extra's
    internal log level.
    """

    all_loggers = CliVerboseOption.all_loggers
