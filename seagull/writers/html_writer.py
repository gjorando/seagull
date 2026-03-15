from typing import TYPE_CHECKING, ClassVar

from seagull.pagination import Paginator
from seagull.settings import temporary_locale
from seagull.writers.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path

    from seagull.contents import Article, SeagullObject
    from seagull.context import Context


class HTMLWriter(Writer):
    """HTML writer class."""

    file_extensions: ClassVar[list[str | None]] = ["html", "htm"]

    def _parse_data(self, obj: SeagullObject, context: Context) -> dict[Path, str]:
        # If the template name is empty, its content is assumed to be final
        if not obj.template:
            return {obj.settings.output_path / obj.save_as: obj.content}

        jinja_context = self._get_jinja_context(obj, context)

        # Otherwise, we render the template
        template = obj.jinja_template
        with temporary_locale(obj.settings.locale):
            # If we have a paginator, we will render the template multiple times
            if obj.template in obj.settings.paginated_templates:
                articles: list[Article] = jinja_context["articles"]
                paginator = Paginator(obj, articles)
                result = {}
                # We render each page
                for page in paginator:
                    result[obj.settings.output_path / page.save_as] = template.render(
                        jinja_context | page.jinja_context
                    )
                return result
            # Otherwise, we render the template once
            return {
                obj.settings.output_path / obj.save_as: template.render(jinja_context)
            }
