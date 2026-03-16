AUTHOR = "John Doe"
SITENAME = "Test website"
SITEURL = "http://localhost:8000"

PATH = "content"

TIMEZONE = "Europe/Paris"

DEFAULT_LANG = "en"
LOCALE = "en_US.UTF-8"
DATE_FORMAT = "%B %d, %Y"
LANGS = {
    "fr": {
        "SITENAME": "Site de test",
        "LOCALE": "fr_FR.UTF-8",
        "DATE_FORMAT": "%A %d %B %Y",
    },
    "jp": {
        "SITENAME": "テストサイト",
        "LOCALE": "ja_JP.UTF-8",
        "DATE_FORMAT": "%Y年%B%d日（%a）",
    }
}

INDEX_URL = "posts/"
INDEX_SAVE_AS = INDEX_URL + "index.html"
INDEX_LANG_URL = "{lang}/posts/"
INDEX_LANG_SAVE_AS = INDEX_LANG_URL + "index.html"

# Feed generation is usually not desired when developing
# FEED_TYPES = []

THEME_LANG = "en"

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
RELATIVE_URLS = True
DELETE_OUTPUT_DIRECTORY = True
