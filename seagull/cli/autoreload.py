from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

import click_extra as clickx
import watchfiles

from seagull.decorators import timed_execution

if TYPE_CHECKING:
    from seagull.settings import Settings


class FileChangeFilter(watchfiles.DefaultFilter):
    """A `watchfiles` filter that considers the `IGNORE_FILES` seagull setting."""

    def __init__(self, ignore_files: list[str | Path], **kwargs: dict):
        super().__init__(**kwargs)
        self.ignore_files = ignore_files

    def __call__(self, change: watchfiles.Change, path: str) -> bool:
        return super().__call__(change, path) and not any(
            Path(path).full_match(pattern) for pattern in self.ignore_files
        )


class Autoreload:
    """Re-run seagull everytime a change is detected on the filesystem."""

    def __init__(
        self,
        settings: Settings,
        watched_files: Path | list[Path] | None = None,
    ):
        """Initialize the autoreload functionality.

        :param settings: Seagull settings.
        """
        self.settings = settings
        if not watched_files:
            watched_files = [settings.path, settings.theme, settings.settings_path]
        if not isinstance(watched_files, list):
            watched_files = [watched_files]
        watched_files = [Path(p) for p in watched_files]
        self.watched_files = watched_files

    def run(self) -> None:
        # We create a dummy watchfiles.FileChange tuple to force a first iteration
        first_change: set[tuple[watchfiles.Change, str]] = {
            (watchfiles.Change.added, "")
        }
        for changed in chain(
            [first_change],
            watchfiles.watch(
                *self.watched_files,
                watch_filter=FileChangeFilter(ignore_files=self.settings.ignore_files),
            ),
        ):
            # Log the updated files
            changed_files = [Path(p) for _, p in changed]
            if changed != first_change:
                cwd = Path.cwd()
                log_changed_files = ", ".join(
                    f"'{p.relative_to(cwd) if p.is_relative_to(cwd) else p}'"
                    for p in changed_files
                )
                clickx.echo(f"Modified files: {log_changed_files}. Regenerating...")
            else:
                clickx.echo("Generating...")

            # Reload the settings if required
            if self.settings.settings_path in changed_files:
                self.settings = self.settings.from_settings_file(
                    self.settings.settings_path, **self.settings.overrides
                )

            # Re-run seagull
            seagull = self.settings.seagull_class(self.settings)
            timed_run = timed_execution(
                seagull.run,
                msg="Generation took {exec_time:.2f} seconds to complete.",
            )
            timed_run()
            clickx.echo("Done!")
