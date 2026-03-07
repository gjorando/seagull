from dataclasses import dataclass

from seagull.contents.taxonomy import Taxonomy


@dataclass(repr=False)
class Author(Taxonomy):
    template: str | None = "author"
