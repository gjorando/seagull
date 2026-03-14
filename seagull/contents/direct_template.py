from dataclasses import dataclass
from typing import ClassVar

from seagull.contents.seagull_object import SeagullObject


@dataclass
class DirectTemplate(SeagullObject):
    """A direct template object."""

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        *SeagullObject.MANDATORY_FIELDS,
        "template",
    )

    def _field_setting_key(self, field_name: str) -> str:
        # Direct templates' setting keys are prefixed with the name of the template
        template_fragment = self.template.lower()
        lang_fragment = "" if self.in_default_lang else "lang"
        # Fallback to direct_template
        for name_fragment in (template_fragment, "direct_template"):
            setting_key = "_".join(
                f for f in (name_fragment, lang_fragment, field_name) if f
            )
            if hasattr(self.settings, setting_key):
                break
        return setting_key

    @property
    def _slug_source(self) -> str:
        # The source for the slug is the name of the template
        return self.template
