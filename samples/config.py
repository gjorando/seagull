from pathlib import Path

# We import our base configuration
from seagull.config import readers, generators
from seagull.objects import Page, Article, BaseObject
from seagull.typeshed import SeagullStatus

# Basic configuration

name = "Test website"

relative_urls = True

default_lang = "en"
locales = {"en": "en_CA.UTF-8",
           "fr": "fr_CA.UTF-8",
           "jp": "ja_JP.UTF-8"}
timezone = "America/Montreal"

sort_objects = {
    Page: "name",
    Article: "-date",
}

# Default overrides
