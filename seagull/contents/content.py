import re
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from bs4 import BeautifulSoup

from seagull.contents.composable_classes import HasStatus, ObjectStatus
from seagull.contents.seagull_object import SeagullObject

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Self

    from seagull.context import Context
    from seagull.settings import Settings


@dataclass
class Content(HasStatus, SeagullObject):
    """Base class for seagull content."""

    MANDATORY_FIELDS: ClassVar[tuple[str, ...]] = (
        "title",
        "lang",
        "template",
        "status",
        "source_path",
        *SeagullObject.MANDATORY_FIELDS,
    )
    GENERATED_FIELDS: ClassVar[tuple[str, ...]] = (
        *SeagullObject.GENERATED_FIELDS,
        "summary",
    )
    # We pre-compile the regexes used by Content._summary to separate and count words
    _WORD_SPLITTER_REGEX: ClassVar[re.Pattern] = re.compile(
        r"{DBC}|(\w[\w'-]*)".format(
            # DBC means CJK-like characters. A character can stand for a word.
            DBC=(
                "([\u4e00-\u9fff])|"  # CJK Unified Ideographs
                "([\u3400-\u4dbf])|"  # CJK Unified Ideographs Extension A
                "([\uf900-\ufaff])|"  # CJK Compatibility Ideographs
                "([\U00020000-\U0002a6df])|"  # CJK Unified Ideographs Extension B
                "([\U0002f800-\U0002fa1f])|"  # CJK Compatibility Ideographs Supplement
                "([\u3040-\u30ff])|"  # Hiragana and Katakana
                "([\u1100-\u11ff])|"  # Hangul Jamo
                "([\uac00-\ud7ff])|"  # Hangul Compatibility Jamo
                "([\u3130-\u318f])"  # Hangul Syllables
            )
        ),
        re.UNICODE,
    )
    _WORD_SEPARATOR_REGEX: ClassVar[re.Pattern] = re.compile(r"\w", re.UNICODE)

    modified: datetime | None = field(default=None, compare=False, repr=False)
    """Last modification date."""
    summary: str = field(default="", compare=False, repr=False)
    """Short summary for the content."""

    def __post_init__(self) -> None:
        super().__post_init__()

        # Add tzinfo to our date fields if necessary
        for f in fields(self):
            key = f.name
            value = getattr(self, key)
            if not isinstance(value, datetime):
                continue
            if not value.tzinfo:
                setattr(self, key, value.replace(tzinfo=self.settings.timezone))

    @classmethod
    def from_parsed_metadata(
        cls,
        settings: Settings,
        context: Context,
        content: str,
        source_path: Path,
        base_path: Path,
        **metadata: object | str,
    ) -> Self:
        # Parse the raw modified date if applicable
        if raw_modified := metadata.get("modified", "").strip():
            metadata["modified"] = datetime.fromisoformat(raw_modified)

        return super().from_parsed_metadata(
            settings, context, content, source_path, base_path, **metadata
        )

    def _field_setting_key(self, field_name: str) -> str:
        # Add the draft fragment
        draft_fragment = "draft" if self.status == ObjectStatus.DRAFT else ""
        return "_".join(
            f for f in (draft_fragment, super()._field_setting_key(field_name)) if f
        )

    @property
    def _summary(self) -> str:
        """Auto-generate the summary."""
        # We begin with the whole content
        summary = self.content

        # Truncate 'summary_max_paragraphs' paragraphs if required
        if self.settings.summary_max_paragraphs is not None:
            tag_end = 0
            paragraphs = []
            for _ in range(self.settings.summary_max_paragraphs):
                summary = summary[tag_end:]
                tag_start = summary.find("<p>")
                tag_end = summary.find("</p>") + len("</p>")
                paragraphs.append(summary[tag_start:tag_end])
            summary = "".join(paragraphs)

        # Truncate 'summary_max_length' words if required
        if self.settings.summary_max_length is not None:
            # Let's use BeautifulSoup for that
            soup = BeautifulSoup(summary, features=self.settings.html_parser)
            # We empty our summary
            summary = ""
            # Keep track of the current number of words processed
            word_count = 0
            maximum_reached = False
            # TODO improve the generation to keep the tags inside the paragraphs, instead of only the text
            # For each paragraph
            for s in soup("p"):
                # Retrieve the text only
                text = s.text
                # Open a paragraph
                summary += "<p>"
                # While we have words in the paragraph
                word_end = 0
                while match := self._WORD_SPLITTER_REGEX.search(text, word_end):
                    # We retain the last word end, so that we pick up the separating
                    # characters between the last word and this one
                    last_word_end, word_end = word_end, match.end()
                    summary += text[last_word_end:word_end]
                    # Increment the word count, break if we reached the maximum
                    word_count += 1
                    if word_count >= self.settings.summary_max_length:
                        maximum_reached = True
                        break
                # If we've reached the maximum count, add the end suffix
                if maximum_reached:
                    summary += self.settings.summary_end_suffix
                # Close the paragraph
                summary += "</p>"
                # And break if we've reached the maximum
                if maximum_reached:
                    break

        return summary

    @property
    def locale_modified(self) -> str:
        """String-formatted modified date."""
        if self.modified:
            return self.modified.strftime(self.settings.date_format)
        return ""
