import json

import pytest

from text2sql import config
from text2sql.executor import ExecutionError, execute_readonly
from text2sql.safety import UnsafeSQLError, validate_select

needs_db = pytest.mark.skipif(not config.DB_PATH.exists(), reason="run download_db.py first")


@pytest.mark.parametrize("sql", [
    "SELECT * FROM Customer",
    "select count(*) from Track;",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
    "SELECT Name FROM Artist UNION SELECT Name FROM Genre",
])
def test_valid_selects_pass(sql):
    assert validate_select(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE Customer",
    "DELETE FROM Customer",
    "UPDATE Customer SET Country='X'",
    "SELECT 1; DROP TABLE Customer",
    "PRAGMA table_info(Customer)",
    "ATTACH DATABASE 'x.db' AS x",
    "",
    "not sql at all (((",
])
def test_unsafe_sql_rejected(sql):
    with pytest.raises(UnsafeSQLError):
        validate_select(sql)


@needs_db
def test_executor_row_limit_and_columns():
    r = execute_readonly("SELECT TrackId, Name FROM Track", max_rows=5)
    assert r.columns == ["TrackId", "Name"] and len(r.rows) == 5 and r.truncated


@needs_db
def test_executor_blocks_writes_even_if_safety_is_bypassed():
    with pytest.raises(ExecutionError):
        execute_readonly("DELETE FROM Customer")


@needs_db
def test_executor_timeout():
    slow = ("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 500000000) "
            "SELECT COUNT(*) FROM c")
    with pytest.raises(ExecutionError, match="timed out"):
        execute_readonly(slow, timeout_s=0.3)


@needs_db
def test_executor_reports_sql_errors():
    with pytest.raises(ExecutionError, match="no such"):
        execute_readonly("SELECT nope FROM Customer")


@needs_db
def test_all_gold_and_example_sql_runs():
    for path in (config.BENCHMARK_PATH, config.EXAMPLES_PATH):
        for item in json.loads(path.read_text(encoding="utf-8")):
            sql = item.get("gold_sql") or item["sql"]
            execute_readonly(validate_select(sql))


@needs_db
def test_benchmark_has_40_unique_questions():
    qs = json.loads(config.BENCHMARK_PATH.read_text(encoding="utf-8"))
    assert len(qs) == 40 and len({q["question"] for q in qs}) == 40
