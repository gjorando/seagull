from typing import TYPE_CHECKING

from seagull.contents import Static
from seagull.generators.generator import Generator
from seagull.readers import Reader
from seagull.writers import Writer

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class StaticGenerator[T: Static](Generator):
    """Generate static content."""

    content_class = Static

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
        return Reader.from_extension(self.settings, extension=None)

    def _get_writer(self, _: T) -> Writer:
        # Once again, extension=None -> reader for static files
        return Writer.from_extension(self.settings, extension=None)

    def has_valid_extension(self, _: Path) -> bool:
        # A static file can have any extension
        return True

    def add_object_to_context(self, obj: T):
        # Static files are recorded separately
        self.context.static_content[obj.source_path] = obj

    @property
    def base_path(self) -> Path:
        return self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return self.settings.static_paths

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return self.settings.static_excludes

    @property
    def _extra_files(self) -> set[Path]:
        """Extra files to process.

        :return: A set of absolute paths to process in addition to `self.files`.
        """
        # The `StaticGenerator` also processes discovered static links
        return self.context.static_links
