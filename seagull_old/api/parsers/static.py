from io import TextIOBase
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, ClassVar

from attrs import define

from seagull.api.objects import Asset
from seagull.logging import logger

from .parser import Parser

if TYPE_CHECKING:
    from io import Reader, Writer


@define(kw_only=True, slots=False)
class StaticParser[T: Asset](Parser):
    """Parser for static assets."""

    file_extensions: ClassVar[tuple[str | None, ...]] = (None,)

    def _loads(self, text: str) -> dict:
        del text  # Unused argument
        # A static asset doesn't parse any content
        return {}

    def load(
        self,
        fp: Reader[str],
        object_class: type[T],
        /,
        **kwargs: object,
    ) -> T:
        del fp  # Unused argument
        return self.loads(
            "",
            object_class,
            **kwargs,
        )

    def read(
        self,
        source_path: Path | str,
        source_root: Path | str,
        object_class: type[T],
        /,
        **kwargs: object,
    ) -> T:
        # The static parser doesn't read a file, it simply records its source path
        return self.loads(
            "",
            object_class,
            name=source_path.name,
            source_root=source_root,
            source_path=Path(source_root) / source_path,
            **kwargs,
        )

    def dumps(self, obj: T, /, **kwargs: object) -> str:
        del kwargs  # Unused argument
        # Try to open the source path of the static asset to directly dump it as-is
        with open(obj.source_path) as obj_fp:
            return obj_fp.read()

    def write(self, obj: T, /, output_path: Path | str = ".", **kwargs: object) -> None:
        del kwargs  # Unused argument
        dest_path = output_path / obj.save_as
        # mkdir -p the output directory if required
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True)
        # If the output path is a directory, delete it first
        elif dest_path.is_dir():
            dest_path.unlink()
        # If the output path is a file, warn about overriding it
        # elif dest_path.is_file():
        #     logger.warning(f"Overriding {dest_path}.")
        # Static parsers directly copy the source into its destination
        # The operation is different depending on whether the source is a dir or a file
        if obj.source_path.is_dir():
            # If the output path is an existing file, delete it first
            if dest_path.is_file():
                dest_path.unlink(missing_ok=True)
            shutil.copytree(obj.source_path, dest_path, dirs_exist_ok=True)
        else:
            shutil.copy2(obj.source_path, dest_path)
