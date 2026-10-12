import pytest

from text2sql import config
from text2sql.agent import TextToSQLAgent
from text2sql.benchmark import has_order_by, results_match

needs_db = pytest.mark.skipif(not config.DB_PATH.exists(), reason="run download_db.py first")


class ScriptedLLM:
    """Returns pre-set replies in order; records prompts."""
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def test_results_match_ignores_row_order_unless_ordered():
    a, b = [(1, "x"), (2, "y")], [(2, "y"), (1, "x")]
    assert results_match(a, b, ordered=False)
    assert not results_match(a, b, ordered=True)


def test_results_match_float_tolerance_and_column_count():
    assert results_match([(2328.6,)], [(2328.6000000001,)], ordered=False)
    assert not results_match([(1, 2)], [(1,)], ordered=False)


def test_has_order_by():
    assert has_order_by("SELECT a FROM t ORDER BY a")
    assert not has_order_by("SELECT a FROM t")


@needs_db
def test_agent_happy_path_strips_fences():
    llm = ScriptedLLM("```sql\nSELECT COUNT(*) FROM Customer;\n```", "There are 59 customers.")
    r = TextToSQLAgent(llm).run("How many customers?")
    assert r.success and r.rows == [(59,)] and len(r.attempts) == 1 and "59" in r.answer


@needs_db
def test_agent_self_corrects_and_sends_error_back():
    llm = ScriptedLLM("SELECT COUNT(*) FROM Customers", "SELECT COUNT(*) FROM Customer", "59 customers.")
    r = TextToSQLAgent(llm).run("How many customers?")
    assert r.success and len(r.attempts) == 2 and r.attempts[0].error
    assert "no such table" in llm.prompts[1] and "Customers" in llm.prompts[1]


@needs_db
def test_agent_without_retries_stops_after_one_attempt():
    llm = ScriptedLLM("SELECT COUNT(*) FROM Customers")
    r = TextToSQLAgent(llm, use_retries=False).run("How many customers?")
    assert not r.success and len(r.attempts) == 1


@needs_db
def test_agent_gives_up_after_three_attempts():
    llm = ScriptedLLM(*["SELECT x FROM nowhere"] * 3)
    r = TextToSQLAgent(llm).run("anything")
    assert not r.success and len(r.attempts) == 3


@needs_db
def test_agent_rejects_non_select_then_recovers():
    llm = ScriptedLLM("DELETE FROM Customer", "SELECT COUNT(*) FROM Customer", "ok")
    r = TextToSQLAgent(llm).run("wipe it")
    assert r.success and "Only SELECT" in r.attempts[0].error


@needs_db
def test_agent_clarification():
    llm = ScriptedLLM("CLARIFY: Which time period do you mean?")
    r = TextToSQLAgent(llm, allow_clarification=True).run("Who are our best customers recently?")
    assert r.clarification and not r.attempts


@needs_db
def test_agent_refuses_unanswerable_question_without_running_sql():
    llm = ScriptedLLM("CANNOT_ANSWER: The database has no artist nationality column.")
    r = TextToSQLAgent(llm).run("Top 10 Indian singers")
    assert r.refusal and "nationality" in r.refusal and not r.attempts and not r.success
