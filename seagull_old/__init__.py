"""Main Seagull package, exposing the backend API as well as various shared code such
as logging utilities."""

from seagull import api, logging, utils
from seagull.api import Seagull

__all__ = [
    "Seagull",
    "api",
    "logging",
    "utils",
]
