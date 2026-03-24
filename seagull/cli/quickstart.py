from collections import defaultdict
from enum import StrEnum
from functools import cache
from importlib.util import find_spec
from pathlib import Path
from zoneinfo import ZoneInfo

import click_extra as clickx
from jinja2 import Environment, FileSystemLoader
import tomlkit
import tomlkit.exceptions
import tomlkit.items
from tzlocal import get_localzone

from seagull.cli.click import TimezoneType
from seagull.cli.main import main


class TemplateConfigFile(StrEnum):
    """Name of each TOML configuration template."""

    dev_conf = "seagull.toml"
    publish_conf = "seagull.publish.toml"


zoneinfo_to_toml: tomlkit.items.Encoder


def zoneinfo_to_toml(value: ZoneInfo) -> tomlkit.items.String:
    """Custom encoder for `tomlkit` that converts a ZoneInfo object to a TOML item."""
    if not isinstance(value, ZoneInfo):
        raise tomlkit.exceptions.ConvertError
    return tomlkit.items.String.from_raw(str(ZoneInfo))


@cache
def templates() -> Path:
    """Get the directory where the configuration templates are stored.

    :raise RuntimeError: If the directory couldn't be found.
    """
    if not (
        result := Path(find_spec(__package__).origin).parent / "templates"
    ).exists():
        raise RuntimeError(f"Couldn't locate the configuration templates ('{result}').")
    return result


@main.command("quickstart")
@clickx.option(
    "--path",
    "-p",
    type=clickx.path(file_okay=False, writable=True),
    default=Path.cwd(),
    callback=lambda _, __, p: p.expanduser().resolve(),
    show_default="current directory",
    prompt="Where do you want to create your website?",
    help="The path to generate the site to.",
)
@clickx.option(
    "--title",
    "-t",
    required=True,
    prompt="What will be the title of the website?",
    help="Name of the site.",
)
@clickx.option(
    "--author",
    "-a",
    callback=lambda _, __, author: author.strip(),
    default="",
    show_default="no author",
    prompt="Who will be the main author of the website?",
    help="Author name for the site.",
)
@clickx.option(
    "--lang",
    "-l",
    callback=lambda _, __, lang: lang.lower().strip(),
    default="en",
    prompt="What will be the default language of the website?",
    help="Default language of the site.",
)
def quickstart(path: Path, title: str, author: str, lang: str) -> None:  # noqa: PLR0912, PLR0915
    """Create a new Seagull project quickly and easily.

    This command will help you set up a new Seagull static site.
    """
    # Register a TOML encoder for ZoneInfo objects
    tomlkit.register_encoder(zoneinfo_to_toml)
    # Load the base configuration files
    toml_files = {}
    for conf_name in TemplateConfigFile:
        with open(templates() / conf_name) as fp:
            toml_files[conf_name] = tomlkit.load(fp)
    toml_seagull = toml_files[TemplateConfigFile.dev_conf]["seagull"]

    # Base configuration
    toml_seagull["sitename"] = title
    toml_seagull["author"] = author
    toml_seagull["default_lang"] = lang

    # We ask some additional information for the configuration file
    if clickx.confirm(
        "Do you want to specify a URL prefix (e.g., https://perdu.com)?",
        default=True,
    ):
        # The URL prefix is only for the publication configuration
        toml_files[TemplateConfigFile.publish_conf]["seagull"]["siteurl"] = (
            clickx.prompt("What is the URL prefix (no trailing slash)?").rstrip("/")
        )

    if clickx.confirm(
        "Do you want to enable pagination?",
        default=True,
    ):
        toml_seagull["default_pagination"] = clickx.prompt(
            "How many items per page do you want?",
            type=clickx.IntRange(min=1),
            default=toml_seagull["default_pagination"],
        )

    toml_seagull["timezone"] = clickx.prompt(
        "What is your timezone?", type=TimezoneType(), default=get_localzone()
    ).key

    # Generation of the invoke file
    tasks_context = {}
    if create_invoke_file := clickx.confirm(
        "Do you want to generate a tasks.py invoke script "
        "to automate generation and publishing?",
        default=False,
    ):
        publishing_tasks = defaultdict(dict)
        if clickx.confirm(
            "Do you want to generate a FTP publishing task?", default=False
        ):
            publishing_tasks["ftp"]["host"] = clickx.prompt("Hostname")
            publishing_tasks["ftp"]["user"] = clickx.prompt("Username")
            publishing_tasks["ftp"]["path"] = clickx.prompt("Target directory")

        if clickx.confirm(
            "Do you want to generate a SSH publishing task?", default=False
        ):
            publishing_tasks["ssh"]["host"] = clickx.prompt("Hostname")
            publishing_tasks["ssh"]["port"] = clickx.prompt(
                "Port", type=clickx.IntRange(0, 2**16, max_open=True), default=22
            )
            publishing_tasks["ssh"]["user"] = clickx.prompt("Username")
            publishing_tasks["ssh"]["path"] = clickx.prompt("Target directory")
        if clickx.confirm(
            "Do you want to generate a S3 publishing task?", default=False
        ):
            publishing_tasks["s3"]["bucket"] = clickx.prompt("Name of the bucket")
        if clickx.confirm(
            "Do you want to generate a gh-pages publishing task?", default=False
        ):
            publishing_tasks["gh_pages"]["branch"] = clickx.prompt("Target branch")
        tasks_context.update(publishing_tasks)

    # Now we create our directory structure
    for subdir in ("content", "output"):
        try:
            Path.mkdir(path / subdir, parents=True)
        except OSError as e:
            clickx.echo(f"Couldn't create the {subdir} directory: {e}", err=True)

    # We save the configuration files
    for conf_name in TemplateConfigFile:
        conf_path = path / conf_name
        tasks_context[conf_name.name] = conf_path
        if not conf_path.exists() or clickx.confirm(
            f"'{conf_name}' already exists; override?"
        ):
            try:
                with open(conf_path, "w") as fp:
                    tomlkit.dump(toml_files[conf_name], fp)
            except OSError as e:
                clickx.echo(f"Couldn't create '{conf_name}': {e}", err=True)

    # Create the tasks.py file
    tasks_path = path / "tasks.py"
    if create_invoke_file and (
        not tasks_path.exists()
        or clickx.confirm("'tasks.py' already exists; override?")
    ):
        jinja_env = Environment(
            loader=FileSystemLoader(templates()),
            trim_blocks=True,
            keep_trailing_newline=True,
        )
        try:
            with open(tasks_path, "w") as fp:
                fp.write(
                    jinja_env.get_template("tasks.py.jinja2").render(**tasks_context)
                )
        except OSError as e:
            clickx.echo(f"Couldn't create 'tasks.py': {e}", err=True)
