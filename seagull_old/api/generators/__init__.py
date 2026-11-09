"""Generator classes.

A generator creates a specific type of seagull object, collecting data from the disk.
"""

from .assets import AssetsGenerator
from .generator import Generator
from .indexes import IndexesGenerator

__all__ = [
    "AssetsGenerator",
    "Generator",
    "IndexesGenerator",
]
