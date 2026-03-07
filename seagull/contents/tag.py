from dataclasses import dataclass

from seagull.contents.taxonomy import Taxonomy


@dataclass(repr=False)
class Tag(Taxonomy):
    template: str | None = "tag"
