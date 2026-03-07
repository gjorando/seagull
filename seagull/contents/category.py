from dataclasses import dataclass

from seagull.contents.taxonomy import Taxonomy


@dataclass(repr=False)
class Category(Taxonomy):
    template: str | None = "category"
