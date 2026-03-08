from io import StringIO
from itertools import chain
from typing import TYPE_CHECKING, Any, ClassVar

import docutils
import docutils.core
import docutils.io
import docutils.readers
from docutils.parsers.rst.languages import get_language
from docutils.writers.html5_polyglot import HTMLTranslator
from docutils.writers.html5_polyglot import Writer as HTMLWriter

from seagull.log import logger
from seagull.readers.reader import Reader

if TYPE_CHECKING:
    from pathlib import Path

    from docutils.nodes import abbreviation as docutils_abbr
    from docutils.nodes import document as docutils_document
    from docutils.nodes import field_body
    from docutils.nodes import image as docutils_image

    from seagull import Settings


class SeagullHTMLTranslator(HTMLTranslator):
    """Tweaked version of the docutils HTML 5 translator class."""

    def visit_abbreviation(self, node: docutils_abbr) -> None:
        """
        The base docutils implementation is incomplete, lacking the `title` attribute.
        """
        attrs = {}
        if node.hasattr("explanation"):
            attrs["title"] = node["explanation"]
        self.body.append(self.starttag(node, "abbr", "", **attrs))

    def visit_image(self, node: docutils_image):  # noqa: ANN201
        """
        Set an empty `alt` attribute so that docutils doesn't set it to src.
        """
        node.setdefault("alt", "")
        return super().visit_image(node)


class FormattedFieldTranslator(SeagullHTMLTranslator):
    """HTML 5 translator class for formatted fields."""

    def astext(self) -> str:
        return "".join(self.body)

    def visit_field_body(self, node: field_body) -> None:
        pass

    def depart_field_body(self, node: field_body) -> None:
        pass


class RstReader(Reader):
    """reStructuredText reader class."""

    enabled = bool(docutils)
    file_extensions: ClassVar[list[str | None]] = ["rst"]

    def __init__(self, settings: Settings):
        super().__init__(settings)

        lang_code = self.settings.default_lang
        if not get_language(lang_code):
            logger.warning(
                f"Docutils doesn't have a localization for '{lang_code}' "
                f"(falling back to 'en' instead)."
            )
            lang_code = "en"
        self._language_code = lang_code

    def _parse_metadata(self, data: docutils_document, path: Path) -> dict[str, Any]:
        """Parse metadata from the parsed data.

        :param data: An object containing the parsed content.
        :param path: Source path.
        :return: A dictionary of parsed, unprocessed metadata.
        """
        metadata = {}
        try:
            metadata["title"] = data.next_node(docutils.nodes.title).astext()
        except AttributeError:
            logger.warning(
                f"Document title missing in file {path}: "
                f"Ensure exactly one top level section"
            )

        # Iterate over all metadata nodes
        for field in chain.from_iterable(
            n.children for n in data.findall(docutils.nodes.docinfo)
        ):
            # Extract the name and value for each metadata
            match tag_name := field.tagname:
                case "authors":  # List of authors
                    name = tag_name
                    value = [author.astext() for author in field.children]
                case "field":  # Custom fields
                    name = field.next_node(docutils.nodes.field_name).astext()
                    field_body = field.next_node(docutils.nodes.field_body)
                    # If a field is a formatted field, it should be parsed
                    if name.lower() in self.settings.formatted_fields:
                        visitor = FormattedFieldTranslator(data)
                        field_body.walkabout(visitor)
                        value = visitor.astext()
                    else:
                        value = field_body.astext()
                case _:  # Standard fields
                    name = tag_name
                    value = field.astext()
            name = name.lower()
            metadata[name] = value
        return metadata

    def _parse_data(self, path: Path) -> tuple[str, dict[str, Any]]:
        # Docutils settings overrides
        extra_params = {
            "initial_header_level": "2",
            "syntax_highlight": "short",
            "input_encoding": "utf-8",
            "language_code": self._language_code,
            "halt_level": 2,
            "traceback": True,
            "warning_stream": StringIO(),
            "embed_stylesheet": False,
        }
        # User-defined overrides
        extra_params.update(self.settings.docutils_settings)

        # Create a docutils publisher and parse the document
        du_parser = docutils.parsers.get_parser_class("restructuredtext")()
        du_writer = HTMLWriter()
        du_writer.translator_class = SeagullHTMLTranslator
        du_publisher = docutils.core.Publisher(
            reader=docutils.readers.get_reader_class("standalone")(du_parser),
            parser=du_parser,
            writer=du_writer,
            destination_class=docutils.io.StringOutput,
        )
        du_publisher.process_programmatic_settings(None, extra_params, None)
        du_publisher.set_source(source_path=path)
        du_publisher.publish()

        content = du_publisher.writer.parts.get("body")
        metadata = self._parse_metadata(du_publisher.document, path)
        return content, metadata
