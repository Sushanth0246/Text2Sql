import re

SYSTEM_SQL = """You are an expert data analyst who writes SQLite queries.

Rules:
- Output exactly ONE read-only SELECT statement (a WITH ... SELECT is fine). No INSERT/UPDATE/DELETE/DDL/PRAGMA.
- Use only the tables and columns in the schema. Never invent columns.
- Use SQLite syntax: strftime() for dates, LIMIT (not TOP), no ILIKE.
- Return only the columns the question asks for, no extra helper columns.
- Prefer explicit JOINs with the foreign keys shown in the schema.
- Output only the raw SQL. No markdown fences, no explanation.
- If the question CANNOT be answered from this schema (the needed data does not exist, e.g. asking
  for artist nationality when no such column exists) or asks to modify/delete data, do NOT substitute
  a different query. Reply with exactly one line: CANNOT_ANSWER: <short reason, mention the missing data>."""

SYSTEM_SQL_CLARIFY_ADDON = """
- If the question is genuinely ambiguous in a way that would change the result (e.g. an undefined
  metric or time range), do NOT guess. Reply with exactly one line: CLARIFY: <one short question>.
  Only do this when truly necessary; otherwise write the query."""

SYSTEM_ANSWER = """You explain database query results to a business user in plain English.
Be concise (1-3 sentences). Use only the numbers and names in the result rows. If the result is
empty, say no matching data was found. Do not mention SQL unless the user asked."""


def _examples_block(examples: list[dict] | None) -> str:
    if not examples:
        return ""
    shots = "\n\n".join(f"Question: {e['question']}\nSQL: {e['sql']}" for e in examples)
    return f"Examples of good questions and queries:\n{shots}\n\n"


def build_sql_prompt(schema: str, question: str, examples: list[dict] | None = None) -> str:
    return (
        f"Database schema:\n{schema}\n\n"
        f"{_examples_block(examples)}"
        f"Question: {question}\nSQL:"
    )


def build_retry_prompt(schema: str, question: str, bad_sql: str, error: str,
                       examples: list[dict] | None = None) -> str:
    return (
        f"Database schema:\n{schema}\n\n"
        f"{_examples_block(examples)}"
        f"Question: {question}\n\n"
        f"Your previous query failed.\nQuery:\n{bad_sql}\n\nError:\n{error}\n\n"
        "Fix the query. Output only the corrected single SELECT statement.\nSQL:"
    )


def build_answer_prompt(question: str, sql: str, columns: list[str], rows: list[tuple],
                        truncated: bool, max_rows: int = 30) -> str:
    shown = rows[:max_rows]
    table = "\n".join(" | ".join(str(v) for v in r) for r in shown) or "(no rows)"
    note = ""
    if truncated or len(rows) > max_rows:
        note = f"\n(Only the first {len(shown)} rows are shown; there are more.)"
    return (
        f"Question: {question}\n\nSQL used:\n{sql}\n\n"
        f"Result columns: {' | '.join(columns)}\nResult rows:\n{table}{note}\n\nAnswer:"
    )


_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    """Strip markdown fences / stray prose the model may wrap around the query."""
    text = (text or "").strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    m = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
    return text[m.start():].strip() if m else text
