from collections import defaultdict
from functools import partial
from itertools import groupby
import locale
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit

from attrs import AttrsInstance, Converter, asdict, define, field, validators

from seagull.generators import Generator
from seagull.logging import PluralFormatter, info_with_paths, logger, warning_with_paths
from seagull.objects import BaseObject
from seagull.theme import Theme
from seagull.typeshed import ObjectSortingFunc, ObjectSortingSpec
from seagull.utils import (
    JinjaRenderable,
    clear_directory,
    load_object_from_module,
    path_repr_func,
    temporary_locale,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from attrs import Attribute

    from seagull.typeshed import JinjaContext


def _locale_dict_converter(
    value: str | list[str] | dict[str, str | list[str]], instance: AttrsInstance
) -> dict[str, str]:
    """Converter for `Seagull.locales`."""
    instance: Seagull
    if not isinstance(value, dict):
        value = {instance.default_lang: value}

    result = {k: _locale_converter(v) for k, v in value.items()}
    if instance.default_lang not in result:
        fallback_locale = next(iter(result.values()))
        logger.warning(
            f"No locale set for default language '{instance.default_lang}', "
            f"'{fallback_locale}' will be used."
        )
        result[instance.default_lang] = fallback_locale

    return result


def _locale_converter(locales: str | list[str]) -> str:
    """Test a locale or list of locales and return the first one that works."""
    if isinstance(locales, str):
        locales = [locales]
    for candidate_locale in locales:
        try:
            # Try the candidate locale
            with temporary_locale(candidate_locale, locale.LC_ALL):
                pass
            # If no error, we return the candidate
            return candidate_locale
        except locale.Error:
            pass
    log_locales = ", ".join(f"'{loc}'" for loc in locales)
    fallback_locale = locale.setlocale(locale.LC_ALL)
    logger.warning(
        f"No valid locale among {log_locales}. Check the 'locales' attribute, "
        f"ensuring at least one of them is valid and available on your system. "
        f"Falling back to '{fallback_locale}'."
    )
    # We fall back to the currently defined locale
    return fallback_locale


def _sort_objects_converter(
    value: dict[str | type[BaseObject], ObjectSortingFunc | ObjectSortingSpec],
) -> dict[type[BaseObject], ObjectSortingFunc]:
    """Converter for `Seagull.sort_objects`."""

    # TODO case insensitive sorting, Unicode normalized sorting
    def _sort_func(objs: list[BaseObject], specs: Sequence[str]) -> list[BaseObject]:
        for spec in reversed(specs):
            if spec.startswith("-"):
                objs = sorted(objs, key=attrgetter(spec[1:]), reverse=True)
            else:
                objs = sorted(objs, key=attrgetter(spec))
        return objs

    result: dict[type[BaseObject], ObjectSortingFunc] = {}
    for k, v in value.items():
        obj_class = k
        if isinstance(obj_class, str):
            obj_class = load_object_from_module(obj_class, "seagull.objects")
        if not (isinstance(obj_class, type) and issubclass(obj_class, BaseObject)):
            raise ValueError(f"'{obj_class}' is not a Seagull object class")
        if callable(v):
            result[obj_class] = v
        elif isinstance(v, str):
            result[obj_class] = partial(_sort_func, specs=[v])
        else:
            result[obj_class] = partial(_sort_func, specs=v)
    return result


@define
class Seagull(JinjaRenderable):
    """Seagull instance."""

    # Config attributes
    name: str
    """Name of the site."""
    url: str = field(default="", converter=str)
    """URL of the site."""
    relative_urls: bool = field(default=False, converter=bool)
    """Whether to use relative or absolute URLs. If set, `url` must be set."""
    default_lang: str = "en"
    """Default language for the website."""
    # FIXME allow overrides for other languages
    locales: dict[str, str] = field(
        converter=Converter(_locale_dict_converter, takes_self=True),
    )
    """Mapping of per-lang locales.

    You can either pass a dictionary mapping a lang to a locale*, or a single locale*
    that will be used for all languages.

    * Each value can either be a single locale, or a sequence of locales. In the latter
    case, the first locale that works will be used.
    """
    content_path: Path = field(
        default=Path("content"), converter=Path, repr=path_repr_func()
    )
    """Directory where the source files are."""
    output_path: Path = field(
        default=Path("output"), converter=Path, repr=path_repr_func()
    )
    """Directory where to generate the output site."""
    sort_objects: dict[type[BaseObject], ObjectSortingFunc] = field(
        factory=dict, converter=_sort_objects_converter, repr=False
    )
    """Sorting strategies for each type of object."""
    generators: dict[str, Generator] = field(
        factory=dict,
        validator=validators.deep_mapping(
            key_validator=validators.instance_of(str),
            value_validator=validators.instance_of(Generator),
        ),
        repr=False,
    )
    """Generators for the instance."""
    theme: Theme = field(
        factory=lambda: Theme.load("simple"),
        converter=lambda t: Theme.load(t) if isinstance(t, (str, Path)) else t,
    )
    """Theme for the site."""
    delete_output_directory: bool = False
    """Whether to clear the output directory before generating the site."""

    # Runtime attributes
    processed_paths: dict[Path, bool] = field(factory=dict, init=False, repr=False)
    """Maps processed paths to whether they were successfully processed."""
    objects: dict[type[BaseObject], list[BaseObject]] = field(
        factory=partial(defaultdict, list), init=False, repr=False
    )
    """Objects created by all generators, mapped by type."""

    @locales.default
    def _attrs_locales_default(self) -> dict[str, str]:
        return {
            self.default_lang: locale.setlocale(locale.LC_ALL),
        }

    @url.validator
    def _attrs_url_validator(self, attribute: Attribute, value: str) -> None:
        """Ensure the 'url' attribute has a scheme and a FQDN set, at least."""
        # The URL can be left empty
        if not value:
            return
        parsed_url = urlsplit(value)
        if not (parsed_url.scheme and parsed_url.netloc):
            raise ValueError(
                f"'{value}': invalid URL for '{type(self).__name__}.{attribute.name}' "
                f"(both a scheme and domain name must be set)"
            )

    @relative_urls.validator
    def _attrs_relative_urls_validator(self, attribute: Attribute, value: bool) -> None:  # noqa: FBT001
        """If we use absolute urls, the `url` attribute must be set."""
        if not (value or self.url):
            raise ValueError(
                f"'{type(self).__name__}.{attribute.name}' is false; "
                f"'{type(self).__name__}.url' must be set as well"
            )

    def run(self) -> None:
        """Main generation sequence.

        In order, it runs the following methods:
        * `clear_output_dir`;
        * `reset`;
        * `generate_objects`;
        * `post_generation_steps`;
        * `sanity_checks`;
        * `write_output`.
        """
        self.clear_output_dir()
        self.reset()
        self.generate_objects()
        logger.info("Running post-generation routines...")
        self.post_generation_steps()
        logger.info("Running sanity checks...")
        self.sanity_checks()
        logger.info("Writing output files...")
        self.write_output()

    def clear_output_dir(
        self,
        retention_paths: Sequence[str | Path] | None = None,
        *,
        force: bool = False,
    ) -> None:
        """Clear the output directory according to a retention policy.

        This method ensures `output_path` exists by the end of its normal execution.
        If both `self.delete_output_directory` and `force` are `False`, the call is a
        no-op.

        :param retention_paths: Paths, relative to `output_path`, to preserve from
        deletion.
        :param force: Bypass the `self.delete_output_directory` flag.
        """
        if not (self.delete_output_directory or force):
            return
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

    def reset(self) -> None:
        """Ensure the instance is in a blank state."""
        # Remove all objects that may have been generated in a past run
        self.objects.clear()
        # Clear processed source paths
        self.processed_paths.clear()

    def generate_objects(self) -> None:
        """Run all generators."""
        default_values = {
            "site_lang": self.default_lang,
            "site_url": None if self.relative_urls else self.url,
            "theme": self.theme,
        }
        for name, generator in self.generators.items():
            logger.info(f"Running the '{name}' generator...")
            # Keep track of all generated objects
            self.objects[generator.object_class].extend(
                generator(
                    self.content_path,
                    self.processed_paths,
                    default_values=default_values,
                )
            )

    def post_generation_steps(self) -> None:
        """Run post-generation methods on all objects."""
        # FIXME move elsewhere?
        # Sort objects that have a defined sorting function
        for obj_class in self.objects:
            if sort_func := self.sort_objects.get(obj_class):
                self.objects[obj_class] = sort_func(self.objects[obj_class])

        for obj in self.all_objects:
            obj.post_generation(self.objects)

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
        if (
            failed_count := (
                len(self.processed_paths) - sum(self.processed_paths.values())
            )
            > 0
        ):
            warning_with_paths(
                PluralFormatter().format(
                    "{count} source path{count:plural,s} couldn't be processed.",
                    count=failed_count,
                ),
                paths=dict(filter(lambda x: x[1], self.processed_paths.items())),
            )

        # Warn of paths that will be overridden
        # FIXME use generator order for precedence
        write_counts: dict[Path, int] = defaultdict(int)
        for obj in self.all_objects:
            dest_path = self.output_path / obj.save_as
            write_counts[dest_path] += 1
        for dest_path in (k for k, v in write_counts.items() if v > 1):
            logger.warning(f"'{dest_path}' will be written more than once.")

    def write_output(self) -> None:
        """Write the site's files on disk."""
        for obj in self.all_objects:
            with temporary_locale(
                self.locales.get(obj.lang, self.locales[self.default_lang])
            ):
                obj.save(self.output_path, **self.jinja_context)
            logger.debug(f"Wrote '{self.output_path / obj.save_as}' on disk.")

    @property
    def all_objects(self) -> Iterable[BaseObject]:
        """Iterate over all seagull objects."""
        for objs in self.objects.values():
            yield from objs

    @property
    def jinja_context(self) -> JinjaContext:
        # The mapping of objects is converted so that each list of objects of a given
        # type is indexed by its pluralized, underscore-separated printable name
        def _serialize_objects(_: Self, field_attr: Attribute, value: object) -> object:
            if field_attr.name == "objects":
                value: dict[type[BaseObject], list[BaseObject]]
                return {
                    k.printable_name(count=2, separator="_"): [o.as_dict() for o in v]
                    for k, v in value.items()
                }
            return value

        return {
            "site": asdict(self, value_serializer=_serialize_objects, recurse=False),
        }
