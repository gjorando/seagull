from contextlib import contextmanager
from importlib.util import find_spec
import locale
import logging
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from seagull.logging import logger

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence


def subclasses[T](cls: type[T]) -> Generator[type[T]]:
    """Yield all subclasses."""
    for sub_cls in cls.__subclasses__():
        yield sub_cls
        yield from subclasses(sub_cls)


def clear_directory(
    path: Path,
    retention_paths: Sequence[str | Path] | None = None,
    *,
    file_okay: bool = False,
) -> list[Path]:
    """Clear a directory in order to populate it again.

    This function ensures `path` exists by the end of its normal execution.

    :param path: Path to clear.
    :param retention_paths: Paths, relative to `path`, to preserve from deletion.
    :param file_okay: If `True`, delete `path` if it's a file.
    :return: List of paths relative to `path` that were effectively kept because of the
    retention policy.
    :raise RuntimeError: If `path` is a file and `file_okay` is `False`.
    """
    # Simply create the directory if it doesn't exist yet
    if not path.exists():
        path.mkdir()
        return []
    # Try removing a file if path is a file and file_okay == True
    if not path.is_dir():
        if not file_okay:
            raise RuntimeError(f"Cannot clear {path}, as it is a file.")
        try:
            path.unlink()
        except OSError:
            logger.exception(
                f"Unable to delete the file '{path}'.",
                exc_info=logger.level == logging.DEBUG,
            )
        path.mkdir()
        return []

    # Otherwise, clear the output path contents
    # Ensure retention_paths is a list of paths
    retention_paths = [Path(p) for p in (retention_paths or [])]
    retained_paths = []
    for child in path.iterdir():
        # But not if the file/directory is in the retention paths
        if (rel_child := child.relative_to(path)) in retention_paths:
            retained_paths.append(rel_child)
            continue
        # Try to delete the child
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError:
            child_dir = child.relative_to(path.parent)
            logger.exception(
                f"Unable to delete '{child_dir}'.",
                exc_info=logger.level == logging.DEBUG,
            )
    return retained_paths


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


def installed_themes_path() -> Path | None:
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


def resolve_theme_path(value: str | Path) -> Path:
    """Ensure a theme value is an existing theme path.

    :param value: Path to a theme, or name of an installed theme.
    :return: Resolved path to said theme, if it exists.
    :raise ValueError: If the path doesn't exist.
    """
    result = Path(value)
    if result.exists():
        return result
    base_theme_path = installed_themes_path()
    if not (base_theme_path and (result := base_theme_path / value).exists()):
        raise ValueError(f"'{value}': not a valid theme.")
    return result


def path_repr(value: Path, *, resolve: bool = False) -> str:
    """`repr` callable for Path fields in `attrs` classes.

    :param value: Path value.
    :param resolve: Whether to resolve the path.
    :return: The path, surrounded by single quotes.
    """
    if resolve:
        return f"'{value.resolve()}'"
    return f"'{value}'"
