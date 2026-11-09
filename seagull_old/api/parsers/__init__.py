"""Parser classes.

A parser class implements operations for creating seagull objects from an input source,
and writing said objects to an output source.
"""

from .html import HTMLParser
from .parser import Parser
from .rest import ReSTParser
from .static import StaticParser

__all__ = ["HTMLParser", "Parser", "ReSTParser", "StaticParser"]
