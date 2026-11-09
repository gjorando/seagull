"""Object classes.

An object is the base component of a seagull site. It can be a static page, an article,
a static file, etc.
"""

from .asset import Asset
from .content import Content
from .index import Index
from .page import Page
from .seagull_object import SeagullObject

__all__ = ["Asset", "Content", "Index", "Page", "SeagullObject"]
