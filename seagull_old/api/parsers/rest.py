from io import StringIO
from itertools import chain
import re
from typing import TYPE_CHECKING, ClassVar

from attrs import define, field
import docutils.core
from docutils.io import StringInput, StringOutput
import docutils.nodes
from docutils.parsers.rst import Parser as DocutilsParser
import docutils.parsers.rst.roles
from docutils.readers.standalone import Reader
import docutils.utils
from docutils.writers.html5_polyglot import HTMLTranslator, Writer

from seagull.logging import logger

from .parser import Parser

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from seagull.api.objects import SeagullObject


_BASE_PUBLISHER_PROGRAMMATIC_SETTINGS = {
    "initial_header_level": "2",
    "syntax_highlight": "short",
    "input_encoding": "utf-8",
    # TODO customize language code?
    "language_code": "en",
    "halt_level": 2,
    "traceback": True,
    "warning_stream": StringIO(),
    "embed_stylesheet": False,
}
"""Base programmatic settings for `_docutils_publisher_factory`."""

_ABBR_REGEX = re.compile(r"\((.*)\)$", re.DOTALL)
"""Compiled abbreviation regex for the :abbr: role."""


def abbr_role(  # noqa: PLR0913
    typ: str,
    rawtext: str,
    text: str,
    lineno: int,
    inliner: docutils.parsers.rst.states.Inliner,
    options: Mapping[str, object] | None = None,
    content: Sequence[str] | None = None,
) -> tuple[list, list]:
    """Custom docutils role for abbreviations."""
    del typ, rawtext, lineno, inliner, options, content  # Unused arguments
    text = docutils.utils.unescape(text)
    m = _ABBR_REGEX.search(text)
    if m is None:
        return [docutils.nodes.abbreviation(text, text)], []
    abbr = text[: m.start()].strip()
    expl = m.group(1)
    return [docutils.nodes.abbreviation(abbr, abbr, explanation=expl)], []


class _SeagullHTMLTranslator(HTMLTranslator):
    """Tweaked version of the docutils HTML 5 translator class."""

    def visit_abbreviation(self, node: docutils.nodes.abbreviation) -> None:
        """
        The base docutils implementation is incomplete, lacking the `title` attribute.
        """
        attrs = {}
        if node.hasattr("explanation"):
            attrs["title"] = node["explanation"]
        self.body.append(self.starttag(node, "abbr", "", **attrs))

    def visit_image(self, node: docutils.nodes.image) -> None:
        """
        Set an empty `alt` attribute so that docutils doesn't set it to src.
        """
        node.setdefault("alt", "")
        return super().visit_image(node)


class _FormattedFieldTranslator(_SeagullHTMLTranslator):
    """HTML 5 translator class for formatted fields."""

    def astext(self) -> str:
        return "".join(self.body)

    def visit_field_body(self, node: docutils.nodes.field_body) -> None:
        pass

    def depart_field_body(self, node: docutils.nodes.field_body) -> None:
        pass


def _docutils_publisher_factory(**kwargs: object) -> docutils.core.Publisher:
    """Default `docutils.core.Publisher` factory.

    :param kwargs: Programmatic settings. They are merged with
    `BASE_PUBLISHER_PROGRAMMATIC_SETTINGS`.
    :return: A new publisher object.
    """
    # We create a publisher...
    parser = DocutilsParser()
    reader = Reader(parser)
    writer = Writer()
    writer.translator_class = _SeagullHTMLTranslator
    publisher = docutils.core.Publisher(
        writer=writer,
        reader=reader,
        parser=parser,
        source_class=StringInput,
        destination_class=StringOutput,
    )
    # ... And process these settings
    publisher.process_programmatic_settings(
        None,
        _BASE_PUBLISHER_PROGRAMMATIC_SETTINGS | kwargs,
        None,
    )
    # TODO register custom roles and directives
    docutils.parsers.rst.roles.register_local_role("abbr", abbr_role)
    return publisher


def _docutils_publisher_converter(
    value: docutils.core.Publisher | dict[str, object],
) -> docutils.core.Publisher:
    """Convert a dictionary of programmatic settings to a `docutils.core.Publisher`.

    :param value: Either a `docutils.core.Publisher` or a `dict` of programmatic
    settings.
    :return: `value` if it is already a `docutils.core.Publisher`, or a new instance
    with its settings programmatically set using `_docutils_publisher_factory`.
    """
    # If the raw value isn't a publisher, it is assumed to be programmatic settings
    if isinstance(value, docutils.core.Publisher):
        return value
    return _docutils_publisher_factory(**value)


@define(kw_only=True, slots=False)
class ReSTParser[T: SeagullObject](Parser):
    """A class that reads and writes reStructuredText data."""

    file_extensions: ClassVar[tuple[str, ...]] = ("rst",)

    publisher: docutils.core.Publisher = field(
        factory=_docutils_publisher_factory,
        converter=_docutils_publisher_converter,
    )
    """`Publisher` object for the ReSTParser."""
    formatted_fields: set[str] = field(
        factory=set, converter=lambda v: {e.lower() for e in v}
    )
    """ReST fields that should be formatted in addition to the file's body."""

    def _loads(self, text: str) -> dict[str, object]:
        def _node_to_text(
            name: str, node: docutils.nodes.Node, doc: docutils.nodes.document
        ) -> str:
            # If a field is a formatted field, it should be parsed
            if name in self.formatted_fields:
                visitor = _FormattedFieldTranslator(doc)
                node.walkabout(visitor=visitor)
                return visitor.astext()
            return node.astext()

        self.publisher.set_source(source=text)
        self.publisher.publish()

        # Load fields from the parsed document
        object_fields: dict[str, object] = {
            "content": self.publisher.writer.parts.get("body") or "",
        }
        if (document := self.publisher.document) is None:
            raise RuntimeError("docutils Publisher failed to produce a document")
        document: docutils.nodes.document
        if (title_node := document.next_node(docutils.nodes.title)) is not None:
            object_fields["name"] = title_node.astext()
        else:
            logger.warning(
                "Document title missing: ensure there's exactly one top level section."
            )

        # Iterate over all metadata nodes
        for f in chain.from_iterable(
            n.children for n in document.findall(docutils.nodes.docinfo)
        ):
            f: docutils.nodes.Element
            # Our metadata is either in a single node or a list of nodes (for authors)
            metadata_nodes: docutils.nodes.Node | list[docutils.nodes.Node]
            # Extract the name and value for each field
            match tag_name := f.tagname.lower():
                case "author":  # Single author
                    # Treated as list of authors with a single value
                    attr_name = "authors"
                    metadata_nodes = [f]
                case "authors":  # List of authors
                    attr_name = tag_name
                    metadata_nodes = f.children
                case "field":  # Custom fields
                    # Ignore if <field> is malformed
                    if not (
                        (field_name := f.next_node(docutils.nodes.field_name))
                        and (field_body := f.next_node(docutils.nodes.field_body))
                    ):
                        continue
                    attr_name = field_name.astext()
                    metadata_nodes = field_body
                case _:  # Other standard fields
                    attr_name = tag_name
                    metadata_nodes = f
            # Convert the node or list of nodes to text
            object_fields[attr_name] = (
                [_node_to_text(attr_name, e, document) for e in metadata_nodes]
                if isinstance(metadata_nodes, list)
                else _node_to_text(attr_name, metadata_nodes, document)
            )
        return object_fields

    def dumps(self, obj: T, /, **kwargs: object) -> str:
        raise NotImplementedError
