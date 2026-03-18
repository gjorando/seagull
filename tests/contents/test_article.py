from datetime import datetime

import pytest
from seagull.contents import Article, Author, Category

from .test_contents import TestContent


class TestArticle(TestContent):
    object_class = Article

    @pytest.fixture(scope="class")
    def category(self, settings):
        """A placeholder category object."""
        return Category(
            settings=settings,
            title="Category",
            save_as=settings.output_path / "category.html",
        )

    @pytest.fixture(scope="class")
    def author(self, settings):
        """A placeholder author object."""
        return Author(
            settings=settings,
            title="Author",
            save_as=settings.output_path / "author.html",
        )

    @pytest.fixture(scope="class", name="minimal_init_fields")
    def minimal_init_fields_article(self, settings, category, author):
        return {
            "settings": settings,
            "title": "Test article",
            "save_as": settings.output_path / "object.html",
            "source_path": settings.path / "object.rst",
            "date": datetime.now(),
            "category": category,
            "authors": [author],
        }

    def test_unchanged_defaults(self, obj, minimal_init_fields, subtests):
        # Date can change if a timezone was added to it!
        super().test_unchanged_defaults(
            obj,
            dict(filter(lambda t: t[0] != "date", minimal_init_fields.items())),
            subtests,
        )
