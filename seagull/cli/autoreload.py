import threading
from pathlib import Path
from typing import TYPE_CHECKING

import click_extra as clickx
import watchfiles

from seagull.cli.click import pass_settings
from seagull.cli.main import main
from seagull.decorators import timed_execution

if TYPE_CHECKING:
    from seagull import Settings


class FileChangeFilter(watchfiles.DefaultFilter):
    """A `watchfiles` filter that considers the `IGNORE_FILES` seagull setting."""

    def __init__(self, ignore_files: list[str | Path], **kwargs: dict):
        super().__init__(**kwargs)
        self.ignore_files = ignore_files

    def __call__(self, change: watchfiles.Change, path: str) -> bool:
        return super().__call__(change, path) and not any(
            Path(path).full_match(pattern) for pattern in self.ignore_files
        )


def default_watched_files() -> tuple[Path, ...]:
    """Default watched files."""
    settings = clickx.get_tool_config(clickx.get_current_context())
    return settings.settings_path, settings.path, settings.theme


@main.command("autoreload")
@clickx.option(
    "--watch",
    "-w",
    "watched_files",
    type=clickx.path(exists=True),
    multiple=True,
    default=default_watched_files,
    show_default=False,
    help="Paths to watch for.  [default: settings file, theme path, content path]",
)
@pass_settings
@clickx.pass_obj
def autoreload(
    thread_list: list, settings: Settings, watched_files: tuple[Path, ...]
) -> None:
    """Rerun seagull each time a modification occurs on the content files."""

    def process() -> None:
        log_watched_files = ", ".join(
            f"'{p.relative_to(Path.cwd()) if p.is_relative_to(Path.cwd()) else p}'"
            for p in watched_files
        )
        clickx.echo(f"Autoreload watching for changes in {log_watched_files}.")
        for changed in watchfiles.watch(
            *watched_files,
            watch_filter=FileChangeFilter(ignore_files=settings.ignore_files),
        ):
            # Log the updated files
            changed_files = [Path(p) for _, p in changed]
            cwd = Path.cwd()
            log_changed_files = ", ".join(
                f"'{p.relative_to(cwd) if p.is_relative_to(cwd) else p}'"
                for p in changed_files
            )
            clickx.echo(f"Modified files: {log_changed_files}. Regenerating...")

            # Reload the settings if required
            # FIXME do the settings reload
            if settings.settings_path in changed_files:
                clickx.echo("Settings changed, reloading not implemented.")

            # Re-run seagull
            seagull = settings.seagull_class(settings)
            timed_run = timed_execution(
                seagull.run,
                msg="Generation took {exec_time:.2f} seconds to complete.",
            )
            timed_run()
            clickx.echo("Done!")

    t = threading.Thread(target=process, daemon=True)
    thread_list.append(t)
