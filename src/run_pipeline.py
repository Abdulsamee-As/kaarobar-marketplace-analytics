#!/usr/bin/env python3
"""Build the Kaarobar database in PostgreSQL and export the results.

Steps: create the database if needed, load the raw CSVs, profile them, clean,
model, answer the business questions, run the quality checks, then export
every analysis view to outputs/ as CSV. All SQL runs through psql.

Connection settings come from the standard PostgreSQL environment variables,
with these defaults: PGHOST=localhost, PGPORT=5432, PGUSER=postgres,
PGDATABASE=kaarobar. If PGPASSWORD is not set, the script asks once.

Run from the project root:
    python src/run_pipeline.py
"""
from __future__ import annotations

import getpass
import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"


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


def find_psql() -> str:
    """psql on the PATH, or the newest version in the default Windows install folder."""
    found = shutil.which("psql")
    if found:
        return found
    installed = glob.glob(r"C:\Program Files\PostgreSQL\*\bin\psql.exe")
    installed.sort(key=lambda p: int(Path(p).parents[1].name) if Path(p).parents[1].name.isdigit() else 0)
    if installed:
        return installed[-1]
    sys.exit("psql not found: install PostgreSQL, or add its bin folder to PATH")


class Psql:
    def __init__(self) -> None:
        self.exe = find_psql()
        env = os.environ.copy()
        env.setdefault("PGHOST", "localhost")
        env.setdefault("PGPORT", "5432")
        env.setdefault("PGUSER", "postgres")
        env.setdefault("PGDATABASE", "kaarobar")
        env.setdefault("PGCLIENTENCODING", "UTF8")
        env["PGOPTIONS"] = "-c client_min_messages=warning"  # hide "does not exist, skipping" notices
        if "PGPASSWORD" not in env:
            env["PGPASSWORD"] = getpass.getpass(f"Password for PostgreSQL user {env['PGUSER']}: ")
        self.env = env
        self.database = env["PGDATABASE"]

    def run(self, *args: str, database: str | None = None) -> str:
        cmd = [self.exe, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", database or self.database, *args]
        result = subprocess.run(cmd, cwd=ROOT, env=self.env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            sys.exit(f"psql failed on: {' '.join(args)[:150]}\n{result.stderr.strip()}")
        return result.stdout

    def run_file(self, name: str) -> None:
        self.run("-f", str(SQL_DIR / name))  # runs from ROOT, so \copy finds data/raw/
        print(f"ran {name}")

    def export(self, sql: str, path: Path) -> None:
        self.run("--csv", "-c", sql, "-o", str(path))


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, true_values=["t"], false_values=["f"])  # psql writes booleans as t and f


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    pd.set_option("display.width", 160)
    pg = Psql()
    print(f"psql: {pg.exe}\ndatabase: {pg.database} on {pg.env['PGHOST']}:{pg.env['PGPORT']}")

    exists = pg.run("-tA", "-c", f"SELECT 1 FROM pg_database WHERE datname = '{pg.database}'",
                    database="postgres").strip()
    if exists != "1":
        pg.run("-c", f'CREATE DATABASE "{pg.database}"', database="postgres")
        print(f"created database {pg.database}")

    pg.run_file("00_load_postgres.sql")

    print("\n=== 01 profile of the raw data ===")
    for n, (name, sql) in enumerate(statements(SQL_DIR / "01_profile_raw.sql"), start=1):
        path = OUT_DIR / f"profile_{name or f'query_{n}'}.csv"
        pg.export(sql, path)
        if n == 1:  # the data quality scorecard
            print(read_csv(path).to_string(index=False))

    for name in ("02_clean.sql", "03_model.sql", "04_analysis.sql"):
        pg.run_file(name)

    print("\n=== 05 quality checks on the cleaned data ===")
    checks_path = OUT_DIR / "quality_checks.csv"
    pg.export(statements(SQL_DIR / "05_quality_checks.sql")[0][1], checks_path)
    checks = read_csv(checks_path)
    checks["result"] = checks.apply(
        lambda r: "PASS" if r.failing_rows == 0 else ("WARN" if "(warning)" in r.check_name else "FAIL"), axis=1)
    checks.to_csv(checks_path, index=False)
    print(checks.to_string(index=False))

    rows = pg.run("-tA", "-c",
                  "SELECT c.table_name, COUNT(*) FROM information_schema.columns c "
                  "JOIN information_schema.views v ON v.table_schema = c.table_schema AND v.table_name = c.table_name "
                  "WHERE c.table_schema = 'mart' GROUP BY c.table_name ORDER BY c.table_name")
    views = [line.split("|") for line in rows.splitlines() if line.strip()]
    for view, n_cols in views:
        order_by = ", ".join(str(i) for i in range(1, int(n_cols) + 1))  # stable row order between runs
        pg.export(f"SELECT * FROM mart.{view} ORDER BY {order_by}", OUT_DIR / f"{view.removeprefix('v_')}.csv")
    print(f"\nexported {len(views)} analysis views to outputs/")

    failed = int((checks.result == "FAIL").sum())
    if failed:
        print(f"{failed} quality check(s) failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
