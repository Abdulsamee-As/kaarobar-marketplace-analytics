#!/usr/bin/env python3
"""Run the SQL pipeline end to end on DuckDB and export the results.

Steps: load the raw CSVs, profile them, clean, model, answer the business
questions, run the quality checks, then write every analysis view to outputs/.

Run from the project root:
    python src/run_pipeline.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
DB_PATH = ROOT / "kaarobar.duckdb"


def statements(path: Path) -> list[tuple[str | None, str]]:
    """Split a SQL file into statements, keeping any '-- name:' tag."""
    chunks = re.split(r";[ \t]*(?:\r?\n|$)", path.read_text(encoding="utf-8"))
    result = []
    for chunk in chunks:
        lines = chunk.strip().splitlines()
        if not any(line.strip() and not line.strip().startswith("--") for line in lines):
            continue
        name = next((line.split("name:", 1)[1].strip() for line in lines
                     if line.strip().startswith("-- name:")), None)
        result.append((name, chunk.strip()))
    return result


def run_file(con: duckdb.DuckDBPyConnection, filename: str) -> None:
    for _, sql in statements(SQL_DIR / filename):
        con.execute(sql)
    print(f"ran {filename}")


def main() -> int:
    os.chdir(ROOT)  # the load script uses paths relative to the project root
    OUT_DIR.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    run_file(con, "00_load_duckdb.sql")

    print("\n=== 01 profile of the raw data ===")
    for name, sql in statements(SQL_DIR / "01_profile_raw.sql"):
        df = con.execute(sql).df()
        df.to_csv(OUT_DIR / f"profile_{name}.csv", index=False)
        if name == "data_quality_scorecard":
            print(df.to_string(index=False))

    for filename in ("02_clean.sql", "03_model.sql", "04_analysis.sql"):
        run_file(con, filename)

    print("\n=== 05 quality checks on the cleaned data ===")
    checks = con.execute(statements(SQL_DIR / "05_quality_checks.sql")[0][1]).df()
    checks["result"] = checks.apply(
        lambda r: "PASS" if r.failing_rows == 0 else ("WARN" if "(warning)" in r.check_name else "FAIL"), axis=1)
    print(checks.to_string(index=False))
    checks.to_csv(OUT_DIR / "quality_checks.csv", index=False)

    views = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'mart' AND table_type = 'VIEW' ORDER BY table_name").fetchall()
    for (view,) in views:
        con.execute(f"SELECT * FROM mart.{view}").df().to_csv(OUT_DIR / f"{view.removeprefix('v_')}.csv", index=False)
    print(f"\nexported {len(views)} analysis views to outputs/")

    failed = (checks.result == "FAIL").sum()
    con.close()
    if failed:
        print(f"{failed} quality check(s) failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
