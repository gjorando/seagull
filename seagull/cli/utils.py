from functools import wraps
import ipaddress
import logging
from pathlib import Path
from runpy import run_path
from typing import TYPE_CHECKING, Concatenate

from boltons.pathutils import shrinkuser
import click_extra as clickx
from click_extra.decorators import decorator_factory

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence
    from ipaddress import IPv4Address, IPv6Address

    from seagull import Seagull


class SeagullVerboseOption(clickx.VerboseOption):
    """Verbose option without click_extra's clutter.

    A simple override of click_extra.VerboseOption that doesn't change click_extra's
    internal log level.
    """

    @property
    def all_loggers(self) -> Generator[logging.Logger]:
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


def default_watched_files() -> tuple[Path, ...]:
    """Default watched files."""
    ctx = clickx.get_current_context().find_root()
    seagull: Seagull = clickx.get_tool_config(ctx)
    return tuple(
        p.relative_to(Path.cwd(), walk_up=True)
        for p in (
            # Configuration file
            Path(ctx.meta[clickx.context.CONF_SOURCE]),
            # Content path
            seagull.content_path.resolve(),
            # TODO Template overrides
            # *(p.resolve() for p in html_parser.template_overrides),
            # Theme
            seagull.theme.path.resolve(),
        )
    )


def seagull_version(fallback_version: str = "(unknown)") -> str:
    """Use click_extra's version option to retrieve the package version.

    :param fallback_version: The fallback string to use if no version could be found.
    :return: Package version.
    """
    try:
        return (
            # Return the first VersionOption param's version attribute
            next(
                filter(
                    lambda p: isinstance(p, clickx.VersionOption),
                    clickx.get_current_context().find_root().command.params,
                )
            ).version
            # If the version attribute is None -> return the fallback
            or fallback_version
        )
    # StopIteration is raised if there's no VersionOption param -> return the fallback
    except StopIteration:
        return fallback_version


def pass_seagull[T, **P](
    func: Callable[Concatenate[Seagull, P], T],
) -> Callable[P, T]:
    """Pass the `SeagullConfig` object to the command."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return func(clickx.get_tool_config(), *args, **kwargs)

    return wrapper


class PyConfigOption(clickx.ExtraOption):
    """A pre-configured option adding `--config PYTHON_CONFIG_FILE`.

    This allows a click app to be configured using a Python file. It is inspired by the
    way Qtile (a Python-based window manager) works.

    This option loads the module into `click_extra.context.TOOL_CONFIG`. If
    `config_schema` was set, the module's variables are consumed.
    `click_extra.context.CONF_SOURCE` and `click_extra.context.CONF_SOURCES` are set as
    well.
    """

    def __init__(
        self,
        param_decls: Sequence[str] = ("--config", "config"),
        metavar: str = "PY_FILE",
        config_schema: type | Callable[[dict[str, object]], object] | None = None,
        **kwargs: object,
    ) -> None:
        """"""
        self.config_schema = config_schema
        super().__init__(
            param_decls=param_decls,
            metavar=metavar,
            # Merge kwargs with its default values
            **{
                "default": self.default_pattern,
                "help": "Location of the Python configuration file.",
                "type": clickx.path(exists=True, dir_okay=False),
                "is_eager": True,
                "expose_value": False,
                "callback": self.load_conf,
            }
            | kwargs,
        )

    def get_help_extra(self, ctx: clickx.Context) -> clickx.types.OptionHelpExtra:
        extra = super().get_help_extra(ctx)
        extra["default"] = shrinkuser(self.get_default(ctx))
        return extra

    # TODO support glob patterns and multiple configuration files (like ConfigOption)
    @staticmethod
    def default_pattern() -> str:
        """Default search pattern for the configuration file."""
        ctx = clickx.get_current_context()
        cli_name = ctx.find_root().info_name
        if not cli_name:
            raise ValueError
        app_dir = Path(clickx.get_app_dir(cli_name)).resolve()
        return str(Path(app_dir) / "config.py")

    def load_conf(
        self,
        ctx: clickx.Context,
        param: clickx.Parameter,
        conf_path: Path,
    ) -> None:
        """Load a configuration module.

        If a configuration schema has been set, the module's variables are passed down
        for initializing the schema.
        """
        del param  # Unused argument

        # Skip file I/O and ctx.meta writes during help rendering, shell
        # completion, and any `make_context(resilient_parsing=True)` path.
        if ctx.resilient_parsing:
            return

        # The full imported configuration dictionary is all the globals variables in the
        # configuration script that do not start with "_"
        user_conf = {
            k: v for k, v in run_path(str(conf_path)).items() if not k.startswith("_")
        }
        # Create the config schema if required
        if self.config_schema:
            ctx.meta[clickx.context.TOOL_CONFIG] = self.config_schema(user_conf)

        conf_path = conf_path.resolve()
        ctx.meta.update(
            {
                clickx.context.CONF_SOURCE: conf_path,
                clickx.context.CONF_SOURCES: (conf_path,),
                clickx.context.CONF_FULL: user_conf,
            }
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


def seagull_run(
    instance: Seagull, *, progress: bool = False, timer: bool = False
) -> None:
    """Execute the Seagull run with an optional spinner animation.

    :param instance: The instance to run.
    :param progress: Whether to enable the spinner.
    :param timer: Whether to display the time on the spinner.
    """
    with clickx.Spinner(
        f"Generating website '{instance.name}'...",
        enabled=None if progress else False,
        timer=timer,
        spinner=clickx.SPINNERS["dots-circle"],
    ) as spinner:
        instance.run()
        spinner.ok()
