"""Step 3b: run SQL on a read-only connection with a timeout and a row limit."""
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from . import config


class ExecutionError(Exception):
    """Raised when the database rejects or fails to run the query."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_s: float


_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


def _authorizer(action, *_args):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def execute_readonly(sql: str, db_path: Path | None = None,
                     timeout_s: float | None = None, max_rows: int | None = None) -> QueryResult:
    db_path = Path(db_path or config.DB_PATH)
    timeout_s = config.QUERY_TIMEOUT_S if timeout_s is None else timeout_s
    max_rows = config.MAX_ROWS if max_rows is None else max_rows

    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        conn.set_authorizer(_authorizer)  # defence in depth: deny anything but reads
        deadline = time.monotonic() + timeout_s
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)

        start = time.monotonic()
        try:
            cur = conn.execute(sql)
            fetched = cur.fetchmany(max_rows + 1)
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise ExecutionError(f"Query timed out after {timeout_s:g}s.") from exc
            raise ExecutionError(str(exc)) from exc
        except sqlite3.Error as exc:
            raise ExecutionError(str(exc)) from exc

        columns = [d[0] for d in cur.description] if cur.description else []
        truncated = len(fetched) > max_rows
        return QueryResult(columns, [tuple(r) for r in fetched[:max_rows]], truncated,
                           time.monotonic() - start)
    finally:
        conn.close()
