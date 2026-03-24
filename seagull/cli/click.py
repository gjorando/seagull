from functools import wraps
import ipaddress
import logging
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, Any, Concatenate
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click_extra as clickx
from click_extra.decorators import decorator_factory

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from ipaddress import IPv4Address, IPv6Address

    from boltons.urlutils import URL

    from seagull.settings import Settings


class SeagullConfigOption(clickx.ConfigOption):
    """A config option that allows for config overrides.

    A root key config `extends` is a configuration path or a list of configuration paths
    to extend the config file.
    """

    def read_and_parse_conf(
        self,
        pattern: str,
    ) -> tuple[Path | URL, dict[str, Any]] | tuple[None, None]:
        path, config = super().read_and_parse_conf(pattern)
        if extends := config.get("extends"):
            if isinstance(extends, str):
                extends = [extends]
            for extend in extends:
                _, base_config = super().read_and_parse_conf(extend)
                config.update(base_config)
                config = base_config | config
        return path, config


seagull_config_option = decorator_factory(
    dec=clickx.decorators.option, cls=SeagullConfigOption
)


def seagull_version() -> str:
    """Use click_extra's version option to retrieve the package version."""
    version_options = [
        p
        for p in clickx.get_current_context().command.params
        if isinstance(p, clickx.ExtraVersionOption)
    ]
    return version_options[0].version if version_options else "(unknown)"


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


class TimezoneType(clickx.ParamType):
    """Validate a timezone."""

    name = "timezone"

    def convert(
        self,
        value: str | ZoneInfo,
        param: clickx.Parameter | None,
        ctx: clickx.Context | None,
    ) -> ZoneInfo:
        """Validation callback for a timezone.

        It must be a valid IANA timezone, and if so, returns a `ZoneInfo` object.
        """
        if isinstance(value, ZoneInfo):
            return value
        try:
            return ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise clickx.BadParameter("Invalid timezone", ctx, param) from None


class SeagullVerboseOption(clickx.VerboseOption):
    """Verbose option without click_extra's clutter.

    A simple override of click_extra.VerboseOption that doesn't change click_extra's
    internal log level.
    """

    @property
    def all_loggers(self) -> Iterable[Logger]:
        yield logging.getLogger(self.logger_name)


class SeagullVerbosityOption(clickx.VerbosityOption):
    """Verbosity without click_extra's clutter.

    A simple override of click_extra.VerbosityOption that doesn't change click_extra's
    internal log level.
    """

    all_loggers = SeagullVerboseOption.all_loggers


seagull_verbose_option = decorator_factory(
    dec=clickx.decorators.option, cls=SeagullVerboseOption
)
seagull_verbosity_option = decorator_factory(
    dec=clickx.decorators.option, cls=SeagullVerbosityOption
)


def pass_settings[T, **P](
    func: Callable[Concatenate[Settings, P], T],
) -> Callable[P, T]:
    """Pass the `Settings` object to the command."""

    @wraps(func)
    @clickx.pass_context
    def wrapper(ctx: clickx.Context, *args: P.args, **kwargs: P.kwargs) -> object:
        settings = ctx.meta["click_extra.tool_config"]
        settings.settings_path = Path(ctx.meta["click_extra.conf_source"])
        return ctx.invoke(func, settings, *args, **kwargs)

    return wrapper


def pass_output_path[T, **P](func: Callable[Concatenate[Path, P], T]) -> Callable[P, T]:
    """Pass seagull's output path to the command."""

    @wraps(func)
    @clickx.pass_context
    def wrapper(ctx: clickx.Context, *args: P.args, **kwargs: P.kwargs) -> object:
        settings = clickx.get_tool_config(ctx)
        return ctx.invoke(func, settings.output_path, *args, **kwargs)

    return wrapper
