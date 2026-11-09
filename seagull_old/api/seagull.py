from collections import defaultdict
from functools import partial
from itertools import groupby
import locale
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, Self

from attrs import asdict, define, field

from seagull.api.utils import GeneratorPaths
from seagull.logging import PluralFormatter, info_with_paths, logger, warning_with_paths
from seagull.utils import (
    clear_directory,
    path_repr,
    temporary_locale,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from attrs import Attribute

    from seagull.api.generators import Generator
    from seagull.api.objects import SeagullObject


def validate_locale(locales: str | list[str]) -> str:
    """Test a locale or list of locales and select the first one that works."""
    if isinstance(locales, str):
        locales = [locales]
    for candidate_locale in locales:
        try:
            # Try the candidate locale
            with temporary_locale(candidate_locale, locale.LC_ALL):
                pass
            # If no error, we set self.locale to the candidate and exit the loop
            return candidate_locale
        except locale.Error:
            pass
    log_locales = ", ".join(f"'{loc}'" for loc in locales)
    logger.warning(
        f"No valid locale among {log_locales}. Check the 'locale' attribute, "
        "ensuring at least one of them is valid and available on your system."
    )
    # We fall back to the currently defined locale
    return locale.setlocale(locale.LC_ALL)


@define(kw_only=True)
class Seagull:
    """Seagull instance."""

    name: str
    """Name of the site."""
    url: str
    """URL of the site."""
    relative_urls: bool = False
    """Whether to use relative or absolute URLs."""
    default_lang: str = "en"
    """Default language for the website."""
    # FIXME allow overrides for other languages
    locale: str = field(
        factory=lambda: locale.setlocale(locale.LC_ALL),
        converter=validate_locale,
    )
    """Locale for the website. If a sequence of locales is passed, the first one that
    works will be used."""
    content_path: Path = field(default="content", converter=Path, repr=path_repr)
    """Directory where the source files are."""
    output_path: Path = field(default="output", converter=Path, repr=path_repr)
    """Directory where to generate the output site."""
    objects: dict[type[SeagullObject], list[SeagullObject]] = field(
        factory=partial(defaultdict, list), init=False, repr=False
    )
    """Objects created by all generators, mapped by type."""
    processed_paths: GeneratorPaths = field(
        factory=GeneratorPaths, init=False, repr=False
    )
    """Source paths that were processed by a generator."""

    def run(self, generators: Sequence[Generator]) -> None:
        """Main generation sequence.

        In order, it runs the following methods:
        * `reset`;
        * `generate_objects`;
        * `post_generation_steps`;
        * `sanity_checks`;
        * `write_output`.

        :param generators: `Generator` instances to run.
        """
        # We ensure the instance has a blank state
        self.reset(generators)

        logger.debug("Running generators...")
        self.generate_objects(generators)

        logger.debug("Running post-generation methods...")
        self.post_generation_steps()

        logger.debug("Running sanity checks...")
        self.sanity_checks()

        # Finally, we can write the output
        logger.debug("Writing output files...")
        self.write_output(generators)

    def clear_output_dir(
        self, retention_paths: Sequence[str | Path] | None = None
    ) -> None:
        """Clear the output directory according to a retention policy.

        This method ensures `output_path` exists by the end of its normal execution.

        :param retention_paths: Paths, relative to `output_path`, to preserve from
        deletion.
        """
        # Don't attempt clearing the output directory if it contains the content dir
        if self.content_path.is_relative_to(self.output_path):
            logger.warning(
                "The output directory contains the content directory;"
                " cannot clear the output directory."
            )
            return
        logger.debug(f"Clearing output directory '{self.output_path}'.")
        retained_paths = clear_directory(
            self.output_path, retention_paths, file_okay=True
        )
        if retained_paths:
            info_with_paths(
                PluralFormatter().format(
                    "{count} path{count:plural,s} "
                    "{count:plural,wasn't,weren't} deleted because "
                    "of the retention policy.",
                    count=len(retained_paths),
                ),
                paths=retained_paths,
            )

    def reset(self, generators: Sequence[Generator]) -> None:
        """Ensure the instance is in a blank state."""
        # Remove all objects that may have been generated in a past run
        self.objects.clear()
        # Clear processed source paths
        self.processed_paths.clear()
        # Reset the generators as well
        for generator in generators:
            generator.reset()

    def generate_objects(self, generators: Sequence[Generator]) -> None:
        """Run all generators."""
        for g in generators:
            g(self.processed_paths, default_lang=self.default_lang)
            # Keep track of all generated objects
            self.objects[g.object_class].extend(g.objects)

    def post_generation_steps(self) -> None:
        """Run post-generation methods on all objects."""
        for obj in self.all_objects:
            obj.post_generation(self.objects)

        # FIXME move elsewhere, maybe we should have class-level post generation steps?
        for objs in self.objects.values():
            objs.sort(key=lambda p: p.name.lower())

    def sanity_checks(self) -> None:
        """Run a few sanity checks."""
        # TODO move sanity checks elsewhere? Maybe class methods in seagull objects?
        # Warn of items of a given type with the same slug and lang
        for obj_class, objs in self.objects.items():
            dupe_getter = attrgetter("slug", "lang")
            for (slug, lang), items in groupby(
                sorted(objs, key=dupe_getter), dupe_getter
            ):
                if (items_count := len(list(items))) > 1:
                    warning_with_paths(
                        f"There are {items_count} "
                        f"{obj_class.printable_name(items_count)} "
                        f"'{slug}' with lang '{lang}'.",
                        paths=[o.source_path for o in items],
                    )

        # Warn of failed source paths
        if (failed_count := len(list(self.processed_paths.failed))) > 0:
            warning_with_paths(
                PluralFormatter().format(
                    "{count} source path{count:plural,s} couldn't be processed.",
                    count=failed_count,
                ),
                paths=self.processed_paths.failed,
            )

        # Warn of paths that will be overridden
        write_counts: dict[Path, int] = defaultdict(int)
        for obj in self.all_objects:
            dest_path = self.output_path / obj.save_as
            write_counts[dest_path] += 1
        for dest_path in (k for k, v in write_counts.items() if v > 1):
            logger.warning(f"'{dest_path}' will be written more than once.")

    def write_output(self, generators: Sequence[Generator]) -> None:
        """Write the site's files on disk."""
        for g in generators:
            g.write(**self.jinja_context)

    @property
    def all_objects(self) -> Iterable[SeagullObject]:
        """Iterate over all seagull objects."""
        for objs in self.objects.values():
            yield from objs

    @property
    def jinja_context(self) -> dict[str, object]:
        """Website's Jinja context.

        Each key is passed as a named parameter to all `Generator.write` calls when
        writing the output files to disk. For each object, the object's `jinja_context`
        property gets merged with this property (if the object has a jinja context).
        """

        def _serialize_objects(_: Self, field_attr: Attribute, value: object) -> object:
            if field_attr.name == "objects":
                value: dict[type[SeagullObject], list[SeagullObject]]
                return {
                    k.printable_name(count=2, separator="_"): [o.as_dict() for o in v]
                    for k, v in value.items()
                }
            return value

        return {
            "site": asdict(self, value_serializer=_serialize_objects, recurse=False),
        }
