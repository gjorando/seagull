"""
Module holding base configuration objects.
"""

from seagull import generators, objects
from seagull.objects import Article
from seagull.readers import BaseReader
from seagull.utils import subclasses

__all__ = ["generators", "readers"]


readers = [r() for r in subclasses(BaseReader)]
"""Default readers."""

generators = {
    "pages": generators.Generator(
        object_class=objects.Page,
        valid_paths={"pages"},
    ),
    "articles": generators.Generator(
        object_class=objects.Article,
        valid_paths={"articles"},
    ),
    "indexes": generators.IndexesGenerator(
        # valid_paths={"indexes"},
        valid_paths=set(),
        auto_index={Article},
    ),
    "assets": generators.AssetsGenerator(
        valid_paths={"images"},
    ),
}
"""Default generators."""
