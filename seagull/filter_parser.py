import ast
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from seagull.contents import Article, Tag


class FilterValidation(ast.NodeVisitor):
    """A parser to turn a filter evaluation string into a function.

    A filter string is essentially a valid Python expression that evaluates to `True` or
    `False`.
    """

    ALLOWED_NODES: ClassVar[tuple[type[ast.AST], ...]] = (
        # Root node in eval mode
        ast.Expression,
        # Variables and attributes
        ast.Name,
        ast.Attribute,
        # Variable access context
        ast.Load,
        ast.Store,
        # Literals
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Set,
        ast.Dict,
        # Expressions
        ast.UnaryOp,
        ast.BinOp,
        ast.BoolOp,
        ast.Compare,
        ast.IfExp,
        # Function calls and lambda expressions
        ast.Call,
        ast.Lambda,
        # All operators (regular, unary, boolean and comparison) are allowed
        ast.operator,
        ast.boolop,
        ast.unaryop,
        ast.cmpop,
        # Keyword arguments in functions
        ast.keyword,
        # Starred expressions
        ast.Starred,
        # Bracketed subscripting with slicing
        ast.Subscript,
        ast.Slice,
        # Comprehensions and generator expressions
        # ast.ListComp,
        # ast.SetComp,
        ast.GeneratorExp,
        # ast.DictComp,
        ast.comprehension,
    )
    """Nodes allowed in a filter evaluation string."""

    def __init__(self, filter_str: str):
        tree = ast.parse(filter_str, mode="eval")
        self.visit(tree)
        self.compiled_code = compile(tree, "<filter>", mode="eval")

    def __call__(self, article: Article, tag: Tag) -> bool:
        # FIXME do the parsing ourselves instead to avoid using eval?
        return bool(eval(self.compiled_code, locals={"article": article, "tag": tag}))  # noqa: S307

    def generic_visit(self, node: ast.AST) -> None:
        """Each visited node must be in `self.ALLOWED_NODES`.

        :raise ValueError: If the node is a forbidden node.
        """
        if not isinstance(node, self.ALLOWED_NODES):
            raise ValueError(
                f"'{ast.unparse(node)}': forbidden syntax "
                f"('{type(node).__name__}') in a filter."
            )
        super().generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Only allow a specific subset of functions."""
        # FIXME valid functions
        super().generic_visit(node)
