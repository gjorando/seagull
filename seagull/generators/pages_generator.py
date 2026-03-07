from typing import TYPE_CHECKING

from seagull.contents import Page
from seagull.generators.generator import Generator
from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class PagesGenerator[T: Page](Generator):
    """Generate static pages."""

    content_class: type[T] = Page

    def _update_context(self, objs: list[T]):
        super()._update_context(objs)
        # Add our original pages to the context
        for obj in self.original_content:
            try:
                self._context_list_from_status(obj.status).append(obj)
            except KeyError:
                logger.warning(
                    f"'{obj.source_path}': the shared context doesn't have "
                    f"a specific list for its status '{obj.status}'."
                )

    def _context_list_from_status(self, status: str) -> list[T]:
        """Subroutine for getting the context list from a publication status.

        :param status: A valid status.
        :return: The context list where objects with this status should go.
        :raise AttributeError: If the context doesn't have a destination for objects
        with this status.
        """
        match status:
            case "published":
                return self.context.all_pages
            case "hidden":
                return self.context.hidden_pages
            case "draft":
                return self.context.draft_pages
        raise AttributeError(status)

    def add_object_to_context(self, obj: T):
        self.context.generated_content[obj.source_path] = obj

    @property
    def base_path(self) -> Path:
        return self.settings.path

    @property
    def valid_paths(self) -> Iterable[Path]:
        return self.settings.page_paths

    @property
    def excluded_paths(self) -> Iterable[Path]:
        return self.settings.page_excludes
