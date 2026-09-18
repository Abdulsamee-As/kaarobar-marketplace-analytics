#!/usr/bin/env python3
"""Run one SQL file, or one query, against kaarobar.duckdb and print the results.

Build the database first with:  python src/run_pipeline.py

Examples, from the project root:
    python src/run_sql.py sql/01_profile_raw.sql
    python src/run_sql.py -q "SELECT * FROM mart.v_headline_kpis"
    python src/run_sql.py -q "SELECT * FROM mart.v_courier_scorecard" --rows 50
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_pipeline import DB_PATH, ROOT, statements  # noqa: E402

ROW_RETURNING = {"SELECT", "WITH", "FROM", "VALUES", "SHOW", "DESCRIBE", "SUMMARIZE", "EXPLAIN", "PRAGMA"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a SQL file or query against kaarobar.duckdb.")
    parser.add_argument("file", nargs="?", help="SQL file to run, statement by statement")
    parser.add_argument("-q", "--query", help="a single query to run instead of a file")
    parser.add_argument("--rows", type=int, default=20, help="rows to print per result (default 20)")
    args = parser.parse_args()
    if not args.file and not args.query:
        parser.error("give a SQL file or -q QUERY")
    if not DB_PATH.exists():
        sys.exit("kaarobar.duckdb not found: run python src/run_pipeline.py first")

    stmts = [(None, args.query)] if args.query else statements(Path(args.file).resolve())
    os.chdir(ROOT)  # the load scripts use paths relative to the project root
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)

    con = duckdb.connect(str(DB_PATH))
    for name, sql in stmts:
        first_line = next(line.strip() for line in sql.splitlines()
                          if line.strip() and not line.strip().startswith("--"))
        label = name or first_line[:90]
        result = con.execute(sql)
        if first_line.split()[0].upper() not in ROW_RETURNING:
            print(f"ok: {label}")  # CREATE, DROP, and similar statements return no rows
            continue
        df = result.df()
        print(f"\n-- {label}  ({len(df):,} rows)")
        print(df.head(args.rows).to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
