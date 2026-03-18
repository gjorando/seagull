import pytest
from seagull.contents import SeagullObject


class TestSeagullObject:
    object_class = SeagullObject

    @pytest.fixture(scope="class")
    def minimal_init_fields(self, settings):
        """Minimum mandatory fields for the object type."""
        return {
            "settings": settings,
            "title": "Test object",
            "save_as": settings.output_path / "object.html",
        }

    @pytest.fixture(scope="class", autouse=True)
    def obj(self, minimal_init_fields):
        return self.object_class(**minimal_init_fields)

    @pytest.mark.parametrize("field_name", SeagullObject.MANDATORY_FIELDS)
    def test_mandatory_fields(self, obj, field_name):
        """Mandatory fields should all be set."""
        assert getattr(obj, field_name)

    def test_unchanged_defaults(self, obj, minimal_init_fields, subtests):
        """All values defined in the arguments shouldn't have been modified"""
        for field_name in minimal_init_fields:
            with subtests.test(
                msg=f"'{field_name}' value should not deviate from init arguments"
            ):
                assert getattr(obj, field_name) == minimal_init_fields[field_name]
