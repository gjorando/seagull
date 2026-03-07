from dataclasses import dataclass

from seagull.contents.content import Content
from seagull.decorators import extra_dataclass


@extra_dataclass
@dataclass(repr=False)
class Page(Content):
    """A seagull static page object."""

    template: str | None = "page"
