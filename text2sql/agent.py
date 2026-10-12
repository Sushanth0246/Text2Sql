"""Steps 2-5: prompt -> safety check -> execute -> self-correct -> plain-English answer."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .executor import ExecutionError, QueryResult, execute_readonly
from .llm import LLM
from .prompts import (SYSTEM_ANSWER, SYSTEM_SQL, SYSTEM_SQL_CLARIFY_ADDON, build_answer_prompt,
                      build_retry_prompt, build_sql_prompt, extract_sql)
from .safety import UnsafeSQLError, validate_select
from .schema import build_schema_text


@dataclass
class Attempt:
    sql: str
    error: str | None = None


@dataclass
class AgentResult:
    question: str
    success: bool = False
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    truncated: bool = False
    attempts: list[Attempt] = field(default_factory=list)
    answer: str = ""
    clarification: str | None = None
    refusal: str | None = None
    error: str | None = None


class TextToSQLAgent:
    def __init__(self, llm: LLM, db_path: Path | None = None, *, use_retries: bool = True,
                 max_attempts: int | None = None, use_descriptions: bool = False,
                 use_examples: bool = False, allow_clarification: bool = False):
        self.llm = llm
        self.db_path = Path(db_path or config.DB_PATH)
        max_attempts = max_attempts or config.MAX_ATTEMPTS
        self.max_attempts = max_attempts if use_retries else 1
        self.allow_clarification = allow_clarification
        self.schema_text = build_schema_text(
            self.db_path, config.DESCRIPTIONS_PATH, use_descriptions=use_descriptions
        )
        self.examples = None
        if use_examples and config.EXAMPLES_PATH.exists():
            self.examples = json.loads(config.EXAMPLES_PATH.read_text(encoding="utf-8"))
        self.system = SYSTEM_SQL + (SYSTEM_SQL_CLARIFY_ADDON if allow_clarification else "")

    def _try(self, sql: str) -> QueryResult:
        return execute_readonly(validate_select(sql), self.db_path)

    def run(self, question: str, summarize: bool = True) -> AgentResult:
        res = AgentResult(question=question)
        prompt = build_sql_prompt(self.schema_text, question, self.examples)

        for i in range(self.max_attempts):
            raw = self.llm.complete(self.system, prompt)
            if self.allow_clarification and i == 0 and raw.strip().upper().startswith("CLARIFY:"):
                res.clarification = raw.strip()[len("CLARIFY:"):].strip()
                return res

            if raw.strip().upper().startswith("CANNOT_ANSWER:"):
                res.refusal = raw.strip()[len("CANNOT_ANSWER:"):].strip()
                res.answer = res.refusal
                return res

            sql = extract_sql(raw)
            try:
                out = self._try(sql)
            except (UnsafeSQLError, ExecutionError) as exc:
                res.attempts.append(Attempt(sql=sql, error=str(exc)))
                res.error = str(exc)
                prompt = build_retry_prompt(self.schema_text, question, sql, str(exc), self.examples)
                continue

            res.attempts.append(Attempt(sql=sql))
            res.success, res.error = True, None
            res.sql, res.columns, res.rows, res.truncated = sql, out.columns, out.rows, out.truncated
            break

        if not res.success:
            res.sql = res.attempts[-1].sql if res.attempts else None
            res.answer = "I couldn't produce a working query for that question."
            return res

        if summarize:
            res.answer = self.llm.complete(
                SYSTEM_ANSWER,
                build_answer_prompt(question, res.sql, res.columns, res.rows, res.truncated),
            )
        return res
