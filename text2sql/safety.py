"""Step 3a: static check that the model produced exactly one SELECT statement."""
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class UnsafeSQLError(ValueError):
    """Raised when generated SQL is not a single read-only SELECT."""


_QUERY_TYPES = (exp.Select, exp.Union, exp.Except, exp.Intersect)
_FORBIDDEN_NAMES = (
    "Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command", "Pragma",
    "Attach", "Detach", "Merge", "TruncateTable", "Transaction", "Commit", "Rollback", "Set", "Use",
)
_FORBIDDEN = tuple(getattr(exp, n) for n in _FORBIDDEN_NAMES if hasattr(exp, n))


def validate_select(sql: str) -> str:
    """Return the cleaned SQL if it is a single SELECT; raise UnsafeSQLError otherwise."""
    cleaned = (sql or "").strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQLError("Empty query.")
    try:
        statements = [s for s in sqlglot.parse(cleaned, read="sqlite") if s is not None]
    except ParseError as exc:
        raise UnsafeSQLError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeSQLError("Exactly one SQL statement is allowed.")
    tree = statements[0]
    if not isinstance(tree, _QUERY_TYPES):
        raise UnsafeSQLError("Only SELECT statements are allowed.")
    if tree.find(*_FORBIDDEN) is not None:
        raise UnsafeSQLError("Query contains a forbidden (non-SELECT) operation.")
    return cleaned
