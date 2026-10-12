# Text-to-SQL Analyst

Ask questions in plain English, get an answer **and the SQL behind it**. The agent writes a SELECT query over a real database (Chinook), runs it safely, fixes its own errors, and explains the result. Includes a 40-question execution-accuracy benchmark.

## How it works

```
question -> prompt (schema + samples) -> LLM -> SQL
         -> safety check (single SELECT, sqlglot)
         -> read-only execution (timeout + row limit)
         -> error? send error + query back to LLM, retry (max 3)
         -> rows -> LLM -> plain-English answer (+ SQL shown in UI)
```

## Project structure

```
text2sql-analyst/
├── app.py                      # Streamlit UI
├── run_benchmark.py            # CLI: run the 40-question benchmark
├── download_db.py              # fetches data/chinook.sqlite (already included)
├── requirements.txt
├── .env.example                # copy to .env
├── data/
│   ├── chinook.sqlite
│   ├── benchmark.json          # 40 questions + gold SQL
│   ├── column_descriptions.json  # step 7: added to schema prompt
│   └── few_shot_examples.json    # step 7: added to prompt (not overlapping benchmark)
├── text2sql/
│   ├── config.py               # paths, timeout, row limit, max attempts
│   ├── llm.py                  # Gemini / Anthropic wrapper with backoff on 429s
│   ├── schema.py               # step 1: tables, columns, types, FKs, sample rows
│   ├── prompts.py              # step 2: prompts + SQL extraction
│   ├── safety.py               # step 3: one-SELECT validation (sqlglot)
│   ├── executor.py             # step 3: read-only conn, timeout, row limit, authorizer
│   ├── agent.py                # steps 2-5: generate, validate, execute, retry, answer
│   └── benchmark.py            # steps 6-7: compare RESULTS, not SQL strings
├── tests/                      # 27 tests, no API key needed
└── results/                    # benchmark output (summary.md)
```

## Setup (Windows, Python 3.11)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then put your GEMINI_API_KEY in .env
python -m pytest            # sanity check, no key needed
streamlit run app.py
```

Never commit `.env` or paste keys into chats/READMEs (`.gitignore` already excludes it).
To use Claude instead of Gemini, set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env`.
Model names change over time; override them with `GEMINI_MODEL` / `ANTHROPIC_MODEL` if needed.

## Benchmark (step 6-7)

```powershell
python run_benchmark.py --sleep 1
```

Runs `baseline` (no retries), `retry`, and `improved` (retries + column descriptions + few-shot) and writes `results/summary.md`.
Each config reports **execution accuracy**, **first-attempt accuracy**, and **average attempts per question**.

Scoring executes both generated and gold SQL and compares the result rows
(order-insensitive unless the gold query has `ORDER BY`; numbers rounded to 2 dp; column names ignored).

| config | exec. accuracy | first-attempt accuracy | avg attempts |
|---|---|---|---|
| baseline | _run it_ | | |
| retry | | | |
| improved | | | |

Resume bullet (fill in your numbers):
> Built a text-to-SQL agent with execution-feedback retries, raising execution accuracy from X% to Y% on a 40-question benchmark.

## Safety layers

1. `sqlglot` parse: exactly one statement, must be SELECT/UNION/CTE-SELECT, no DDL/DML/PRAGMA/ATTACH.
2. SQLite opened with `mode=ro` + `PRAGMA query_only=ON`.
3. SQLite authorizer denies anything except reads.
4. Query timeout (default 5s) and row cap (default 200).

## Stretch goal: clarifying questions

Toggle "Ask clarifying question" in the sidebar. The model may reply `CLARIFY: ...` instead of SQL when a question is truly ambiguous (e.g. "best customers recently"), and the UI shows that question.

## Ideas to extend

- Postgres support: swap `schema.py` PRAGMAs for `information_schema` queries and `executor.py` for psycopg with `default_transaction_read_only=on`.
- Try Northwind, add more benchmark questions per category, log failures by category in `results/*.json`.
