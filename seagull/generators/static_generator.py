from typing import TYPE_CHECKING

from seagull.contents import Static
from seagull.generators.generator import Generator
from seagull.readers import Reader
from seagull.writers import Writer

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from seagull.context import Context
    from seagull.settings import Settings


class StaticGenerator[T: Static](Generator):
    """Generate static content."""

    content_class = Static

    def __init__(
        self, settings: Settings, context: Context, *, theme_static: bool = False
    ):
        """
        :param theme_static: If `True` the generator will work on the theme's static
        files instead.
        """
        self.theme_static = theme_static
        super().__init__(settings, context)

    @property
    def files(self) -> set[Path]:
        return set(
            filter(
                # Do not export a source file as a static file
                lambda f: f not in self.context.generated_content,
                super().files | self._extra_files,
            )
        )

    def _get_reader(self, _: Path) -> Reader:
        # extension=None indicates we want the reader for static files
        return Reader.from_extension(None)(self.settings)

    def _get_writer(self, _: T) -> Writer:
        # Once again, extension=None -> reader for static files
        return Writer.from_extension(None)(self.settings)

    def has_valid_extension(self, _: Path) -> bool:
        # A static file can have any extension
        return True

    @property
    def base_path(self) -> Path:
        return self.settings.theme if self.theme_static else self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return (
            self.settings.theme_static_paths
            if self.theme_static
            else self.settings.static_paths
        )

    @property
    def excluded_paths(self) -> Iterable[Path]:
        # No excluded paths for the theme static files
        return [] if self.theme_static else self.settings.static_excludes

    @property
    def _extra_files(self) -> set[Path]:
        """Extra files to process.

        :return: A set of absolute paths to process in addition to `self.files`.
        """
        # The `StaticGenerator` also processes discovered static links
        # ... Not for the theme `StaticGenerator` instance though
        return set() if self.theme_static else self.context.static_links
