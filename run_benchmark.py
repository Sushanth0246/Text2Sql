"""Usage:
    python run_benchmark.py                       # baseline, retry, improved
    python run_benchmark.py --configs baseline retry
    python run_benchmark.py --limit 5 --sleep 1   # quick smoke test / gentle on rate limits
"""
import argparse

from text2sql import config
from text2sql.benchmark import CONFIGS, evaluate, load_questions, save_report, summary_table
from text2sql.llm import get_llm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["baseline", "retry", "improved"],
                    choices=list(CONFIGS))
    ap.add_argument("--limit", type=int, default=None, help="only run the first N questions")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds to wait between questions")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    llm = get_llm(args.provider, args.model)
    questions = load_questions()[: args.limit]
    reports = []
    for name in args.configs:
        report = evaluate(llm, name, questions, sleep_s=args.sleep)
        print("saved ->", save_report(report))
        reports.append(report)

    table = summary_table(reports)
    print("\n" + table)
    (config.RESULTS_DIR / "summary.md").write_text(table + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
