from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from .base_object import BaseObject
from .utils import seagull_object

if TYPE_CHECKING:
    from seagull.typeshed import StrPath


@seagull_object
class Asset(BaseObject):
    """Static asset on disk, copied as-is into the output site."""

    def save(self, output_path: StrPath, **kwargs: object) -> None:
        del kwargs  # Unused
        if not self.source_path:
            raise OSError(f"{type(self).__name__} object '{self}' has no source path")
        output_path = output_path / self.save_as
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)
        # If the output path is a directory, delete it first
        elif output_path.is_dir():
            output_path.unlink()
        # Static parsers directly copy the source into its destination
        # The operation is different depending on whether the source is a dir or a file
        if self.source_path.is_dir():
            # If the output path is an existing file, delete it first
            if output_path.is_file():
                output_path.unlink(missing_ok=True)
            shutil.copytree(self.source_path, output_path, dirs_exist_ok=True)
        else:
            shutil.copy2(self.source_path, output_path)

    def default_save_as(self) -> Path:
        return Path("static") / self.source_path
