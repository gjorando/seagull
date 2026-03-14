from typing import TYPE_CHECKING, ClassVar

from seagull.settings import temporary_locale
from seagull.writers.writer import Writer

if TYPE_CHECKING:
    from seagull.contents import SeagullObject
    from seagull.context import Context


class HTMLWriter(Writer):
    """HTML writer class."""

    file_extensions: ClassVar[list[str | None]] = ["html", "htm"]

    def _parse_data(self, obj: SeagullObject, context: Context) -> str:
        # If the template name is empty, its content is assumed to be final
        if not obj.template:
            return obj.content
        # Otherwise, we render the template
        # We merge the settings, the base render context, and that of the object, to
        # create the full render context
        with temporary_locale(obj.settings.locale):
            template = obj.jinja_template
            return template.render(
                obj.settings.as_dict()
                | context.base_jinja_context(obj.lang)
                | obj.jinja_context
            )
