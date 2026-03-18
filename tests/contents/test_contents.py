import pytest
from seagull.contents import Content

from .test_seagull_object import TestSeagullObject


class TestContent(TestSeagullObject):
    object_class = Content

    @pytest.fixture(scope="class")
    def minimal_init_fields(self, settings):
        return {
            "settings": settings,
            "title": "Test content",
            "save_as": settings.output_path / "content.html",
            "source_path": settings.path / "content.rst",
        }
