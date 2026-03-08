import ipaddress
import json
import logging
from logging import Logger
from pathlib import Path
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


class SeagullSettingsType(clickx.Path):
    """Load a Seagull settings module.

    The order in which parameters and arguments decorators are declared is important.
    All click options that are settings overrides should come before the
    `SeagullSettingsType` parameter, and other CLI options should come after.
    """

    def __init__(self) -> None:
        super().__init__(exists=True, dir_okay=False, path_type=Path)

    def convert(
        self,
        value: str | Path,
        param: clickx.Parameter | None,
        ctx: clickx.Context | None,
    ) -> Settings:
        """Load a settings module into a `Settings` instance."""
        path = super().convert(value, param, ctx)
        cli_overrides = {}

        for key in list(ctx.params.keys()):
            # "path" (lowercase) is valid because click forces the names of arguments to
            # be lowercase
            if Settings.is_valid_param_key(key) or key == "path":
                # Remove parameter overrides from the parsed click params
                override = ctx.params.pop(key)
                # If a value override is unset, ignore it so that it doesn't override
                # the value in the settings file
                if override is not None:
                    cli_overrides[key.upper()] = override

        # Update our kwargs with the extra settings overrides
        cli_overrides.update(ctx.params.pop("extra_settings"))

        # Load the settings from the settings module
        return Settings.from_settings_file(path, **cli_overrides)


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
