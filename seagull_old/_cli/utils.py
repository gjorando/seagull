from functools import wraps
import ipaddress
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Concatenate, cast

import click_extra as clickx
from click_extra.decorators import decorator_factory

from seagull.api.parsers import HTMLParser

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from ipaddress import IPv4Address, IPv6Address

    from seagull import Seagull
    from seagull._cli.config import CoreConfig


def default_watched_files() -> tuple[Path, ...]:
    """Default watched files."""
    ctx = clickx.get_current_context().find_root()
    seagull: Seagull = clickx.get_tool_config(ctx).instance
    html_parser = HTMLParser()
    return tuple(
        p.relative_to(Path.cwd(), walk_up=True)
        for p in (
            Path(ctx.meta[clickx.context.CONF_SOURCE]),
            seagull.content_path.resolve(),
            *(p.resolve() for p in html_parser.template_overrides),
            html_parser.theme.path.resolve(),
        )
    )


def seagull_version() -> str:
    """Use click_extra's version option to retrieve the package version."""
    version_options = [
        p
        for p in clickx.get_current_context().find_root().command.params
        if isinstance(p, clickx.VersionOption)
    ]
    return version_options[0].version if version_options else "(unknown)"


def pass_config[T, **P](
    func: Callable[Concatenate[CoreConfig, P], T],
) -> Callable[P, T]:
    """Pass the `SeagullConfig` object to the command."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return func(cast("CoreConfig", clickx.get_tool_config()), *args, **kwargs)

    return wrapper


class SeagullVerboseOption(clickx.VerboseOption):
    """Verbose option without click_extra's clutter.

    A simple override of click_extra.VerboseOption that doesn't change click_extra's
    internal log level.
    """

    @property
    def all_loggers(self) -> Iterable[logging.Logger]:
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
