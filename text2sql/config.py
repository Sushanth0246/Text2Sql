import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"


def _path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


DB_PATH = _path(os.getenv("DB_PATH"), DATA_DIR / "chinook.sqlite")
DESCRIPTIONS_PATH = DATA_DIR / "column_descriptions.json"
EXAMPLES_PATH = DATA_DIR / "few_shot_examples.json"
BENCHMARK_PATH = DATA_DIR / "benchmark.json"

QUERY_TIMEOUT_S = float(os.getenv("QUERY_TIMEOUT_S", "5"))
MAX_ROWS = int(os.getenv("MAX_ROWS", "200"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
