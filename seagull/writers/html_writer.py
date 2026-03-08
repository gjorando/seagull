from dataclasses import fields
from typing import TYPE_CHECKING, ClassVar

from seagull.writers.writer import Writer

if TYPE_CHECKING:
    from seagull.contents import SeagullObject
    from seagull.context import Context


class HTMLWriter(Writer):
    """HTML writer class."""

    file_extensions: ClassVar[list[str | None]] = ["html", "htm"]

    def _parse_data(self, obj: SeagullObject, context: Context) -> str:
        # If an object doesn't have a template, its content is assumed to be final
        if not obj.template_object:
            return obj.content
        # Otherwise, we render the template: we merge the settings, the base render
        # context and that of the object, to create the full render context
        return obj.template_object.render(
            {
                # FIXME add extra_metadata and as_dict to settings
                k: getattr(obj.settings, k)
                for k in [f.name for f in fields(obj.settings)]
                + list(getattr(obj.settings, "__extra_dataclass__attrs__", []))
            }
            | context.base_jinja_context
            | obj.jinja_context
        )
