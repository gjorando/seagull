from typing import TYPE_CHECKING, ClassVar

from seagull.writers.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path

    from seagull.contents import SeagullObject
    from seagull.context import Context


class StaticWriter(Writer):
    """Static files writer class."""

    file_extensions: ClassVar[list[str | None]] = [None]

    def _parse_data(self, obj: SeagullObject, context: Context) -> dict[Path, Path]:
        del context  # Unused argument
        # StaticWriter simply instructs write_file to copy the source file to the output
        return {
            self.settings.output_path / obj.save_as: self.settings.path
            / obj.source_path
        }
