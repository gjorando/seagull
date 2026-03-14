from dataclasses import dataclass

from seagull.contents.content import Content


@dataclass
class Page(Content):
    """A seagull static page object."""
