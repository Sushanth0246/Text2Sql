"""Step 1: extract schema (tables, columns, types, FKs) plus a few sample rows per table."""
import json
import sqlite3
from pathlib import Path


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _ro_conn(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)


def _short(value, limit: int = 40):
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return "<blob>"
    s = str(value)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def extract_schema(db_path: Path, n_samples: int = 3) -> list[dict]:
    conn = _ro_conn(db_path)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        schema = []
        for t in tables:
            cols = [
                {"name": r[1], "type": r[2] or "TEXT", "notnull": bool(r[3]), "pk": bool(r[5])}
                for r in conn.execute(f"PRAGMA table_info({_q(t)})")
            ]
            fks = {r[3]: f"{r[2]}.{r[4]}" for r in conn.execute(f"PRAGMA foreign_key_list({_q(t)})")}
            cur = conn.execute(f"SELECT * FROM {_q(t)} LIMIT {int(n_samples)}")
            samples = [[_short(v) for v in row] for row in cur.fetchall()]
            schema.append({"table": t, "columns": cols, "fks": fks, "samples": samples})
        return schema
    finally:
        conn.close()


def load_descriptions(path: Path) -> dict[str, str]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def format_schema(schema: list[dict], descriptions: dict[str, str] | None = None) -> str:
    descriptions = descriptions or {}
    lines: list[str] = []
    for t in schema:
        name = t["table"]
        header = f"TABLE {name}"
        if descriptions.get(name):
            header += f"  -- {descriptions[name]}"
        lines.append(header)
        for c in t["columns"]:
            parts = [f"  - {c['name']} {c['type']}"]
            if c["pk"]:
                parts.append("PRIMARY KEY")
            if c["name"] in t["fks"]:
                parts.append(f"-> {t['fks'][c['name']]}")
            desc = descriptions.get(f"{name}.{c['name']}")
            if desc:
                parts.append(f"-- {desc}")
            lines.append(" ".join(parts))
        if t["samples"]:
            lines.append("  sample rows (" + " | ".join(c["name"] for c in t["columns"]) + "):")
            for row in t["samples"]:
                lines.append("    " + " | ".join(row))
        lines.append("")
    return "\n".join(lines).strip()


def build_schema_text(db_path: Path, descriptions_path: Path | None = None,
                      use_descriptions: bool = False, n_samples: int = 3) -> str:
    descs = load_descriptions(descriptions_path) if (use_descriptions and descriptions_path) else {}
    return format_schema(extract_schema(db_path, n_samples), descs)
