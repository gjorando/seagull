from seagull.api.utils import seagull_object

from .content import Content


@seagull_object
class Page(Content):
    """A static page."""
