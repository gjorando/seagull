from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from seagull.contents.content import Content
from seagull.decorators import extra_dataclass

if TYPE_CHECKING:
    from seagull.contents.category import Category


@extra_dataclass
@dataclass(repr=False)
class Article(Content):
    """A seagull article object."""

    mandatory_fields: ClassVar[tuple[str, ...]] = Content.mandatory_fields + (
        "date",
        "category",
        "author",
    )
    category: Category | None = None
    template: str | None = "article"

    def _setting_key_fragments(self, field_name: str) -> list[str]:
        # Special case for draft articles (no leading class name)
        if self.status == "draft":
            lang_fragment = "lang" if self.lang != self.settings.default_lang else None
            return [f for f in ["draft", lang_fragment, field_name] if f]
        return super()._setting_key_fragments(field_name)

    @property
    def jinja_context(self) -> dict[str, Any]:
        return super().jinja_context | {
            # Legacy behaviour of Pelican
            "category": self.category.name
        }
