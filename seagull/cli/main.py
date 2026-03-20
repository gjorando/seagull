import click_extra as clickx


@clickx.group(
    "seagull",
    params=[],
)
@clickx.color_option
@clickx.version_option
def main() -> None:
    """A tool to generate a static blog, with restructured text input files."""
