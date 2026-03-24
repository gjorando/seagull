from abc import abstractmethod
from contextlib import contextmanager
from importlib.machinery import PathFinder
from importlib.util import find_spec, module_from_spec
import locale
from pathlib import Path
from string import Formatter
import sys
from typing import TYPE_CHECKING, NamedTuple, Protocol, runtime_checkable

from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sized
    from datetime import datetime
    from types import ModuleType

    from seagull.contents import SeagullObject


class Comparable[T](Protocol):
    """Protocol for annotating comparable types."""

    @abstractmethod
    def __lt__(self: T, other: T, /) -> bool: ...


@runtime_checkable
class PluginType[T](Protocol):
    """Protocol for annotating plugin classes."""

    @abstractmethod
    def register(self) -> None: ...


class PaginationRule(NamedTuple):
    """Pagination rule for the paginator."""

    min_page: int
    url: str
    save_as: str


def get_installed_themes_path() -> Path | None:
    """Retrieve the directory where installed themes are stored.

    :return: The path for installed themes, or `None` if it couldn't be found.
    """
    result = None
    if seagull_spec := find_spec(__package__):
        # the installed themes are stored in <seagull package>/themes/
        package_dir = Path(seagull_spec.origin).parent
        result = package_dir / "themes"
    if not (result and result.exists()):
        result = None
        logger.warning(
            "Couldn't find the installed themes path: 'simple' and "
            "the other installed themes won't be available."
        )
    return result


def ensure_paths(p: Path | str | list[Path | str]) -> Path | list[Path]:
    """Ensure a path-like or list of path-like uses `pathlib.Path`."""
    if isinstance(p, list):
        return [Path(v) for v in p]
    return Path(p)


def strftime_jinja_filter(date: datetime, date_format: str, locale_: str = "") -> str:
    """A locale aware date-formatter for Jinja.

    :param date: `datetime` object to format.
    :param date_format: Format string.
    :param locale_: Locale to use. If empty, it uses the currently defined locale for
    `LC_TIME`.
    :return: Formatted `datetime` using `strftime`.
    """
    if not locale_:
        locale_ = locale.setlocale(locale.LC_TIME)
    # on OSX, encoding from LC_CTYPE determines the Unicode output
    # So make sure it's same as LC_TIME
    with temporary_locale(locale_, (locale.LC_TIME, locale.LC_CTYPE)):
        return date.strftime(date_format)


@contextmanager
def temporary_locale(
    temp_locale: str, lc_category: int | tuple[int, ...] = locale.LC_ALL
) -> Generator[None]:
    """Context manager for running code with a temporary locale.

    Resets the locale back when exiting context.

    :param temp_locale: Temporary locale to use.
    :param lc_category: Locale category or list of locale categories that are affected.
    """
    if not isinstance(lc_category, tuple):
        lc_category = [lc_category]
    orig_locales = {lcc: locale.setlocale(lcc) for lcc in lc_category}

    # Change the desired locale categories, then enter the context manager
    for lcc in lc_category:
        locale.setlocale(lcc, temp_locale)
    yield
    # After exiting the context manager, restore the categories to their old locale
    for lcc in lc_category:
        locale.setlocale(lcc, orig_locales[lcc])


def order_by_factory(
    value: str,
) -> tuple[Callable[[SeagullObject], Comparable], bool]:
    """Convert an `*_ORDER_BY` setting to a key function and `reverse` parameter.

    See [the Python documentation](https://docs.python.org/3/howto/sorting.html)
    for details about key functions.

    :return: A function that takes a seagull object and return a value for sorting; a
    boolean that tells whether to reverse the sorting order.
    """
    # Whether to reverse the sorting order
    reverse = False
    if value.startswith("reversed-"):
        value = value.replace("reversed-", "", 1)
        reverse = True
    # Special case basename: order by filename
    if value == "basename":

        def key_func(obj: SeagullObject) -> Comparable:
            if obj.source_path:
                return obj.source_path.name
            return obj.title
    # Otherwise, sort by a given metadata key
    else:

        def key_func(obj: SeagullObject) -> object:
            return getattr(obj, value)

    return key_func, reverse


def absolute_from_base_path(
    paths: Path | str | list[Path | str], base: Path
) -> Path | list[Path]:
    """Ensure a path or list of paths is absolute.

    :param paths: `Path` or list of `Path` objects.
    :param base: Base path for relative paths to be turned absolute.
    :return: `Path` or list of `Path` objects, ensured to be absolute.
    """

    def _absolute_from_base_path(o: Path) -> Path:
        return o if o.is_absolute() else (base / o).resolve()

    paths = ensure_paths(paths)
    if isinstance(paths, Path):
        return _absolute_from_base_path(paths)
    return [_absolute_from_base_path(o) for o in paths]


class PluralFormatter(Formatter):
    """A small helper class to format pluralized strings in a Python f-string.

    Format spec looks like this: `"plural,"val1[,val2[,val3]]`.
    - If only `val1` is defined, it gives a replacement if the value is not 1.
    - If `val2` is defined as well, `val1` gives a replacement if the value is 1. `val2`
    gives a replacement otherwise.
    - If `val3` is defined as well, it gives a replacement if the value is greater than
    one, `val2` if the value is 1, and `val1` otherwise.

    This works on integer, and objects which define a `__len__` method.

    Based on https://tobywf.com/2015/12/sane-pluralisation/.
    """

    def format_field(self, value: int | Sized, format_spec: str) -> str:
        if format_spec.startswith("plural,"):
            replacement_specs = format_spec.split(",")[1:]
            replacement_values = [""] * 3
            match len(replacement_specs):
                case 1:
                    replacement_values[0] = replacement_values[2] = replacement_specs[0]
                case 2:
                    replacement_values[0] = replacement_values[2] = replacement_specs[1]
                    replacement_values[1] = replacement_specs[0]
                case 3:
                    replacement_values = replacement_specs
                case _:
                    raise ValueError(f"Invalid pluralizer format '{format_spec}'.")
            # If the value is not int, we try to assume it has a length, and use it
            if not isinstance(value, int):
                value = len(value)

            if value > 1:
                return replacement_values[2]
            if value == 1:
                return replacement_values[1]
            return replacement_values[0]
        return super().format_field(value, format_spec)


def find_plugin(
    plugin_name: str, plugin_paths: list[str | Path]
) -> tuple[ModuleType | PluginType, str]:
    """Helper function that tries to import a plugin module or class.

    :param plugin_name: Name of the plugin we want to load.
    :param plugin_paths: Additional paths where to look for plugins.
    :return: The plugin (either a module or a class) and the plugin name.
    :raise ValueError: If the plugin couldn't be found.
    """
    # importlib functions require a string object
    plugin_paths = [str(p) for p in plugin_paths]
    cls_name = ""
    plugin_spec = PathFinder.find_spec(plugin_name, plugin_paths + sys.path)
    # If we can't find the plugin spec, let's assume we have a plugin class
    if not plugin_spec:
        plugin_package, _, cls_name = plugin_name.rpartition(".")
        plugin_spec = PathFinder.find_spec(plugin_package, plugin_paths + sys.path)
    # If we still don't have a plugin_spec at this point, raise an exception
    if not plugin_spec:
        raise ValueError(f"Cannot find plugin '{plugin_name}'.")
    plugin_module = sys.modules.setdefault(
        # If the plugin is already in sys.modules, simply use this
        plugin_spec.name,
        # Otherwise, load it from its specs, and add it to sys.modules
        module_from_spec(plugin_spec),
    )
    # Now, let's load our module
    plugin_spec.loader.exec_module(plugin_module)
    # return the plugin class if we have one, or the module directly
    if plugin_class := getattr(plugin_module, cls_name, None):
        return plugin_class, plugin_class.__qualname__
    return plugin_module, plugin_module.__name__
