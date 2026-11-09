from attrs import define, field

from seagull.api.objects import Index, SeagullObject
from seagull.api.utils import (
    GeneratorPaths,
    load_object_from_module,
    object_class_field,
)

from .generator import Generator


@define
class IndexesGenerator(Generator):
    """Generator for `Index` objects."""

    object_class: type[Index] = object_class_field(Index, is_default=True)
    default_indexes: list[type[SeagullObject]] = field(
        factory=list,
        converter=lambda l: [
            load_object_from_module(v, "seagull.api.objects")
            if isinstance(v, str)
            else v
            for v in l
        ],
    )
    """List of seagull object types for which an index should be generated anyways."""

    def __call__(
        self, generator_paths: GeneratorPaths | None = None, /, **kwargs: object
    ) -> None:
        super().__call__(generator_paths, **kwargs)
        # TODO find a way to handle this with languages
        for obj_cls in self.default_indexes:
            pass
            # self.objects.append(self.object_class(obj_cls))
