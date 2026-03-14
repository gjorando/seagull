AUTHOR = "John Doe"
SITENAME = "Test website"
SITEURL = "https://getseagull.com"

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

INDEX_SAVE_AS = "articles.html"
INDEX_LANG_SAVE_AS = "articles-{lang}.html"

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

THEME_LANG = "en"

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
RELATIVE_URLS = True
DELETE_OUTPUT_DIRECTORY = True
