import pytest
from seagull import Settings


@pytest.fixture(scope="session")
def sandbox_dirs(tmp_path_factory):
    """Create a temporary path structure."""
    tmp_path = tmp_path_factory.getbasetemp()
    dirs = {"output_path": tmp_path / "output", "path": tmp_path / "content"}
    for dir_ in dirs.values():
        dir_.mkdir()
    return dirs


@pytest.fixture(scope="class")
def settings(sandbox_dirs):
    """Some baseline settings."""
    # FIXME request temporary directories
    return Settings(**sandbox_dirs)
