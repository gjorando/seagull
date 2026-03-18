from collections import defaultdict
from collections.abc import Collection
from dataclasses import fields
from typing import TYPE_CHECKING, Any, cast

from seagull.contents import (
    Article,
    Author,
    Category,
    Content,
    GranularArchive,
    Page,
    SeagullObject,
    Static,
    Tag,
    Taxonomy,
)
from seagull.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import Path

    from seagull.utils import Comparable


class SeagullObjectContextDescriptor[T: Context, C: SeagullObject]:
    """Descriptor for lists of seagull objects in the context.

    It allows to define shorthands for accessing a specific list of objects in a shared
    context object.
    """

    def __init__(self, obj_class: type[C]):
        """
        :param obj_class: Type of seagull object to get.
        :raise ValueError: If `obj_class` is not a subclass of `SeagullObject`.
        """
        if not issubclass(obj_class, SeagullObject):
            raise ValueError(obj_class)
        self.obj_class = obj_class

    def __get__(
        self, instance: T | None, owner: type[T] | None = None
    ) -> list[C] | None:
        """Attribute getter.

        :param instance: A `Context` instance if accessed through the class.
        :param owner: Owner class.
        :return: The list of objects, or `None` if class attribute access.
        """
        if instance is None:
            return None
        return instance.objects[self.obj_class]


# TODO remove a lot of unused properties, maybe refactor based on the fact that the lang is now central to accessing data
class Context(Collection[SeagullObject]):
    """Shared context for a seagull run."""

    authors: list[Author] = SeagullObjectContextDescriptor(Author)
    tags: list[Tag] = SeagullObjectContextDescriptor(Tag)
    categories: list[Category] = SeagullObjectContextDescriptor(Category)
    articles: list[Article] = SeagullObjectContextDescriptor(Article)
    pages: list[Page] = SeagullObjectContextDescriptor(Page)
    static: list[Static] = SeagullObjectContextDescriptor(Static)

    def __init__(self) -> None:
        self.objects: dict[type[SeagullObject], list[SeagullObject]] = defaultdict(list)
        self.static_links: set[Path] = set()
        self.failed_source_paths: set[Path] = set()

    def sort_objects[T: SeagullObject](
        self,
        obj_class: type[T],
        key: Callable[[T], Comparable],
        *,
        reverse: bool = False,
    ) -> None:
        """Sort a specific list of objects.

        :param obj_class: The type of seagull object to sort.
        :param key: The sorting function.
        :param reverse: If `True`, the sorting is reversed.
        :raise ValueError: If `obj_class` is not a subclass of `SeagullObject`.
        """
        if not issubclass(obj_class, SeagullObject):
            raise ValueError(obj_class)
        self.objects[obj_class].sort(key=key, reverse=reverse)

    def filter_objects[T: SeagullObject](
        self,
        obj_class: type[T],
        function: Callable[[T], bool],
    ) -> Iterable[T]:
        """Filter a specific list of objects.

        :param obj_class: The type of seagull object to filter.
        :param function: The filtering function.
        :return: The filtered list of objects.
        :raise ValueError: If `obj_class` is not a subclass of `SeagullObject`.
        """
        if not issubclass(obj_class, SeagullObject):
            raise ValueError(obj_class)
        return filter(function, self.objects[obj_class])

    def objects_by_status[T: SeagullObject](
        self, status: str, object_class: type[T]
    ) -> Iterable[T]:
        """Iterate over seagull objects of a specific status.

        :param object_class: The type of object to filter.
        :param status: Status of the objects to retrieve.
        :return: Iterable of objects.
        :raise ValueError: If `obj_class` doesn't have a `status`.
        """

        def filter_func(obj: SeagullObject) -> bool:
            return getattr(obj, "status", "") == status

        if "status" not in (f.name for f in fields(object_class)):
            raise ValueError(
                f"Objects of type '{object_class.__name__}' don't have a status."
            )

        return self.filter_objects(object_class, filter_func)

    def prune_taxonomies(self) -> None:
        """Remove empty taxa."""
        for taxon_class in self.taxonomies:
            self.objects[taxon_class] = list(
                filter(lambda t: t.articles, self.objects[taxon_class])
            )

    def get_or_new_taxon[T: Taxonomy](
        self,
        taxon_class_or_name: type[T] | str,
        slug_or_name: str,
        target_lang: str | None = None,
        **kwargs: object,
    ) -> T:
        """Get or create a taxonomy object.

        We try to retrieve it based on the slug if the taxon is a preprocessed one, or
        by name otherwise. If such a taxonomy doesn't exist, it is created using
        `kwargs`, and stored in `self.objects[taxon_class]`.

        :param taxon_class_or_name: `Taxonomy` subclass or name (case-insensitive).
        :param slug_or_name: Name of the taxonomy to look for.
        :param target_lang: Optional lang to target. This allows us to differentiate
        translations of a given taxon.
        :param kwargs: Metadata attributes for the taxon if it needs to be
        created.
        :return: A taxonomy object.
        :raise ValueError: If `taxon_class_or_name` doesn't refer to a subclass of
        `Taxonomy`.
        """
        try:
            taxon_class: type[T] = (
                # If taxon_class_or_name is a name, retrieve the corresponding class
                next(
                    filter(
                        lambda cls: cls.__name__.lower() == taxon_class_or_name.lower(),
                        Taxonomy.all_object_types(),
                    )
                )
                if isinstance(taxon_class_or_name, str)
                else taxon_class_or_name
            )
        except StopIteration:
            raise ValueError(taxon_class_or_name) from None
        if not issubclass(taxon_class, Taxonomy):
            raise ValueError(taxon_class_or_name)
        candidates = list(
            filter(
                lambda t: (
                    # If source_path is set, it was a preprocessed taxon; try retrieving
                    # an existing taxon by slug
                    (t.slug == slug_or_name)
                    if t.source_path is not None
                    # If source_path is None, it means it was not a preprocessed taxon;
                    # try retrieving an existing taxon by name
                    else (t.name == slug_or_name)
                )
                # We also want the taxon with the target lang if we have one, or the
                # taxon in default lang otherwise
                and ((t.lang == target_lang) if target_lang else t.in_default_lang),
                self.objects[taxon_class],
            )
        )
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) != 0:
            # This shouldn't happen normally
            logger.warning(
                f"Multiple candidates for taxon of type '{taxon_class.__name__}' named "
                f"'{slug_or_name}'."
            )
            return candidates[0]

        # If we're here, it means we have a new taxon, so we create it
        logger.debug(
            f"Creating a new {taxon_class.__name__.lower()} named '{kwargs['title']}'."
        )
        taxon = taxon_class(**kwargs)
        # We add it to our list of taxa
        self.objects[taxon_class].append(taxon)
        return taxon

    def get_by_type[T: SeagullObject](
        self, obj_class_or_name: type[T] | str
    ) -> list[T]:
        """Get a list of objects by type.

        :param obj_class_or_name: Either the type of object, or the name of the type
        (case-insensitive).
        :return: The list of objects.
        :raise KeyError: If `obj_class_or_name` doesn't refer to a subclass of
        `SeagullObject`.
        """
        # Try retrieving the object class by name
        if isinstance(obj_class_or_name, str):
            try:
                obj_class_or_name = next(
                    filter(
                        lambda cls: cls.__name__.lower() == obj_class_or_name.lower(),
                        SeagullObject.all_object_types(),
                    )
                )
            except StopIteration:
                raise KeyError(obj_class_or_name) from None
        # Otherwise, we have a class, check that it's a subclass of SeagullObject
        elif not issubclass(obj_class_or_name, SeagullObject):
            raise KeyError(obj_class_or_name)
        return self.objects[obj_class_or_name]

    def base_jinja_context(self, lang: str | None = None) -> dict[str, Any]:
        """Base context dictionary for Jinja templates rendering.

        The `all_articles` key always contains the full list of published articles,
        while `articles` may be overridden to contain a subset of articles. For instance
        if we are rendering a taxonomy page, `articles` contains the list of articles in
        the taxonomy.

        :param lang: If set, only returns context relevant for this lang.
        """

        def lang_filter(o: SeagullObject) -> bool:
            return o.lang == lang

        # FIXME maybe use a property for this instead?
        period_archives = defaultdict(list)
        obj: GranularArchive
        for obj in self.filter_objects(GranularArchive, lang_filter):
            period_archives[obj.granularity.value].append(obj)

        all_articles = list(filter(lang_filter, self.published_articles))
        return {
            "all_articles": all_articles,
            "articles": all_articles,
            "hidden_articles": list(filter(lang_filter, self.hidden_articles)),
            "drafts": list(filter(lang_filter, self.draft_articles)),
            "period_archives": period_archives,
            # FIXME attributes for hidden taxonomies?
            "authors": list(
                filter(lang_filter, self.objects_by_status("published", Author))
            ),
            "categories": list(
                filter(lang_filter, self.objects_by_status("published", Category))
            ),
            "tags": list(filter(lang_filter, self.objects_by_status("published", Tag))),
            "pages": list(filter(lang_filter, self.published_pages)),
            "hidden_pages": list(filter(lang_filter, self.hidden_pages)),
            "draft_pages": list(filter(lang_filter, self.draft_pages)),
            "index_url": "",  # FIXME
        }

    @property
    def published_articles(self) -> Iterable[Article]:
        return self.objects_by_status(status="published", object_class=Article)

    @property
    def hidden_articles(self) -> Iterable[Article]:
        return self.objects_by_status(status="hidden", object_class=Article)

    @property
    def draft_articles(self) -> Iterable[Article]:
        return self.objects_by_status(status="draft", object_class=Article)

    @property
    def published_pages(self) -> Iterable[Page]:
        return self.objects_by_status(status="published", object_class=Page)

    @property
    def hidden_pages(self) -> Iterable[Page]:
        return self.objects_by_status(status="hidden", object_class=Page)

    @property
    def draft_pages(self) -> Iterable[Page]:
        return self.objects_by_status(status="draft", object_class=Page)

    @property
    def taxonomies(self) -> dict[type[Taxonomy], list[Taxonomy]]:
        """Retrieve a dictionary with all taxonomy objects, mapped by type."""
        return {
            k: cast("list[Taxonomy]", v)
            for k, v in self.objects.items()
            if issubclass(k, Taxonomy)
        }

    @property
    def generated_content(self) -> dict[Path, Content]:
        """Generated content, mapped by source path."""
        return {
            # FIXME this cast shouldn't be necessary, if we ensure that self.objects typing understands that each sublist only stores objects of the type of the key
            obj.source_path: cast("Content", obj)
            for content_class, content_list in self.objects.items()
            for obj in content_list
            if issubclass(content_class, Content) and obj.source_path is not None
        }

    @property
    def static_content(self) -> dict[Path, Static]:
        """Static files, mapped by source path."""
        return {obj.source_path: cast("Static", obj) for obj in self.objects[Static]}

    def __len__(self) -> int:
        """Number of seagull objects in the context."""
        return len(self.objects)

    def __iter__(self) -> Iterator[SeagullObject]:
        """Iterate over all seagull objects in the context."""
        for v in self.objects.values():
            yield from v

    def __contains__(self, obj: object, /) -> bool:
        """Test if an object is a seagull object in the context.

        :param obj: Value to test.
        :return: `True` if `obj` is a seagull object registered in the context.
        """
        return isinstance(obj, SeagullObject) and obj in self.objects[obj.__class__]
