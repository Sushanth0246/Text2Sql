"""Steps 6-7: score by comparing RESULTS of generated vs gold SQL (never the SQL text)."""
import json
import time
from collections import Counter
from datetime import datetime

import sqlglot

from . import config
from .agent import TextToSQLAgent
from .executor import ExecutionError, execute_readonly
from .llm import LLM

CONFIGS = {
    "baseline": dict(use_retries=False, use_descriptions=False, use_examples=False),
    "retry": dict(use_retries=True, use_descriptions=False, use_examples=False),
    "improved_noretry": dict(use_retries=False, use_descriptions=True, use_examples=True),
    "improved": dict(use_retries=True, use_descriptions=True, use_examples=True),
}


def _norm_cell(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        s = v.strip()
        try:
            return round(float(s), 2)
        except ValueError:
            return s
    return v


def _norm_rows(rows) -> list[tuple]:
    return [tuple(_norm_cell(c) for c in r) for r in rows]


def has_order_by(sql: str) -> bool:
    try:
        return sqlglot.parse_one(sql, read="sqlite").args.get("order") is not None
    except Exception:
        return False


def results_match(gold_rows, pred_rows, ordered: bool) -> bool:
    g, p = _norm_rows(gold_rows), _norm_rows(pred_rows)
    if ordered:
        return g == p
    return Counter(g) == Counter(p)


def load_questions(path=None) -> list[dict]:
    return json.loads((path or config.BENCHMARK_PATH).read_text(encoding="utf-8"))


def evaluate(llm: LLM, config_name: str, questions: list[dict], sleep_s: float = 0.0,
             verbose: bool = True) -> dict:
    agent = TextToSQLAgent(llm, **CONFIGS[config_name])
    records = []
    for q in questions:
        gold = execute_readonly(q["gold_sql"], max_rows=10_000)
        ordered = has_order_by(q["gold_sql"])
        try:
            r = agent.run(q["question"], summarize=False)
        except Exception as exc:  # e.g. API failure: count as wrong, keep going
            records.append({**q, "pred_sql": None, "attempts": 0, "correct": False,
                            "first_attempt_correct": False, "error": f"LLM error: {exc}"})
            continue

        correct = r.success and results_match(gold.rows, r.rows, ordered)
        first_ok = bool(r.attempts) and r.attempts[0].error is None and correct
        records.append({
            **q, "pred_sql": r.sql, "attempts": len(r.attempts), "correct": correct,
            "first_attempt_correct": first_ok, "error": r.error,
        })
        if verbose:
            print(f"[{config_name}] #{q['id']:>2} {'OK ' if correct else 'BAD'} "
                  f"attempts={len(r.attempts)}  {q['question']}")
        if sleep_s:
            time.sleep(sleep_s)

    n = len(records)
    return {
        "config": config_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n": n,
        "execution_accuracy": sum(r["correct"] for r in records) / n,
        "first_attempt_accuracy": sum(r["first_attempt_correct"] for r in records) / n,
        "avg_attempts": sum(r["attempts"] for r in records) / n,
        "records": records,
    }


def save_report(report: dict) -> str:
    config.RESULTS_DIR.mkdir(exist_ok=True)
    path = config.RESULTS_DIR / f"{report['config']}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def summary_table(reports: list[dict]) -> str:
    lines = ["| config | exec. accuracy | first-attempt accuracy | avg attempts |",
             "|---|---|---|---|"]
    for r in reports:
        lines.append(f"| {r['config']} | {r['execution_accuracy']:.1%} | "
                     f"{r['first_attempt_accuracy']:.1%} | {r['avg_attempts']:.2f} |")
    return "\n".join(lines)
