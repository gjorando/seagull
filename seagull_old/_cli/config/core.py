from pathlib import Path

from attrs import define, field
import click_extra as clickx

from seagull import Seagull

from .base import BaseConfig, multi_config_field
from .generator import GeneratorConfig
from .parser import ParserConfig
from .utils import instance_class_field, instance_field


@define(kw_only=True)
class CoreConfig(BaseConfig):
    """Configuration schema for the Seagull command-line front-end.

    This is the root configuration object for Seagull's default front-end
    implementation."""

    instance_class: type[Seagull] = instance_class_field(
        default=Seagull,
        base_module="seagull.api.seagull",
    )
    instance: Seagull = instance_field(
        config_path="core",
    )
    delete_output_directory: bool = field(default=False, converter=bool)
    """Whether to clear the output directory before building the website."""
    output_retention: list[Path] = field(
        factory=list, converter=lambda v: [Path(p) for p in v]
    )
    """Filenames that shouldn't be deleted from the output directory if
    `delete_output_directory` is `True`."""
    generators: dict[str, GeneratorConfig] = multi_config_field(
        target_config=GeneratorConfig
    )
    """Mapping of generator configurations to use for object generation."""
    parsers: dict[str, ParserConfig] = multi_config_field(target_config=ParserConfig)
    """Mapping of parser configurations for parser pre-loading."""

    def execute(self, *, progress: bool = False, timer: bool = False) -> None:
        """Execute the Seagull run with an optional spinner animation.

        :param progress: Whether to enable the spinner.
        :param timer: Whether to display the time on the spinner.
        """
        with clickx.Spinner(
            f"Generating website '{self.instance.name}'...",
            enabled=None if progress else False,
            timer=timer,
            spinner=clickx.SPINNERS["dotsCircle"],
        ) as spinner:
            if self.delete_output_directory:
                self.instance.clear_output_dir(self.output_retention)
            self.instance.run(
                [g.instance for g in self.generators.values() if g.enabled]
            )
            spinner.ok()
