#!/usr/bin/env python3
"""Build the Kaarobar database in SQL Server and export the results.

Steps: create the database if needed, load the raw CSVs, profile them, clean,
model, answer the business questions, run the quality checks, then export
every analysis view to outputs/ as CSV. All SQL runs through sqlcmd using
Windows authentication, so there is no password to type.

Set SQLSERVER and SQLDATABASE to override the defaults.

Run from the project root:
    python src/run_pipeline.py
"""
from __future__ import annotations

import glob
import io
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
RAW_DIR = ROOT / "data" / "raw"
TMP_FILE = OUT_DIR / "_sqlcmd_result.txt"
DATABASE = os.environ.get("SQLDATABASE", "Kaarobar")
# SQL Server Express installs with the browser service off, so the usual
# "localhost\SQLEXPRESS" address can fail to resolve. The named pipe always works.
SERVER_CANDIDATES = [os.environ["SQLSERVER"]] if os.environ.get("SQLSERVER") else [
    r"localhost\SQLEXPRESS",
    r"np:\\.\pipe\MSSQL$SQLEXPRESS\sql\query",
]
SEP = "|"  # column separator for sqlcmd output; no value in this data contains it
NOISE = ("Warning:", "Msg ", "Level ")  # sqlcmd status lines that are not data


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


def find_sqlcmd() -> str:
    """sqlcmd on the PATH, or in its usual install folders."""
    found = shutil.which("sqlcmd")
    if found:
        return found
    patterns = [r"C:\Program Files\sqlcmd\sqlcmd.exe",
                r"C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\*\Tools\Binn\sqlcmd.exe"]
    for pattern in patterns:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    sys.exit("sqlcmd not found: install it with  winget install Microsoft.Sqlcmd")


class Sqlcmd:
    def __init__(self) -> None:
        self.exe = find_sqlcmd()
        self.server = self._first_server_that_answers()

    def _first_server_that_answers(self) -> str:
        for server in SERVER_CANDIDATES:
            probe = subprocess.run([self.exe, "-S", server, "-E", "-b", "-d", "master", "-Q", "SELECT 1"],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
            if probe.returncode == 0:
                return server
        sys.exit("cannot reach SQL Server. Is the service running? Tried: " + ", ".join(SERVER_CANDIDATES))

    def run(self, *args: str, database: str | None = None) -> str:
        cmd = [self.exe, "-S", self.server, "-E", "-b", "-d", database or DATABASE, *args]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0:
            detail = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            sys.exit(f"sqlcmd failed on: {' '.join(args)[:150]}\n{detail}")
        return result.stdout

    def run_file(self, name: str, **variables: str) -> None:
        args = ["-i", str(SQL_DIR / name)]
        for key, value in variables.items():
            args += ["-v", f"{key}={value}"]
        self.run(*args)  # runs from ROOT, so relative paths resolve
        print(f"ran {name}")

    def export(self, sql: str, path: Path) -> pd.DataFrame:
        """Run a query and save the result as a real CSV file."""
        self.run("-Q", f"SET NOCOUNT ON; {sql}", "-s", SEP, "-W", "-w", "65535", "-o", str(TMP_FILE))
        # sqlcmd writes a header row, a row of dashes, then the data, and can add
        # status lines such as a warning about NULLs dropped by an aggregate
        rows = [line for line in TMP_FILE.read_text(encoding="utf-8").splitlines()
                if not line.startswith(NOISE)]
        df = pd.read_csv(io.StringIO("\n".join(rows)), sep=SEP, skiprows=[1], na_values=["NULL"])
        df.to_csv(path, index=False)
        return df


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    pd.set_option("display.width", 160)
    sql = Sqlcmd()
    print(f"sqlcmd: {sql.exe}\ndatabase: {DATABASE} on {sql.server}")

    sql.run("-Q", f"IF DB_ID('{DATABASE}') IS NULL CREATE DATABASE [{DATABASE}]", database="master")

    sql.run_file("00_load_sqlserver.sql", DataDir=f"{RAW_DIR}\\")

    print("\n=== 01 profile of the raw data ===")
    for n, (name, query) in enumerate(statements(SQL_DIR / "01_profile_raw.sql"), start=1):
        df = sql.export(query, OUT_DIR / f"profile_{name or f'query_{n}'}.csv")
        if n == 1:  # the data quality scorecard
            print(df.to_string(index=False))

    for name in ("02_clean.sql", "03_model.sql", "04_analysis.sql"):
        sql.run_file(name)

    print("\n=== 05 quality checks on the cleaned data ===")
    checks_path = OUT_DIR / "quality_checks.csv"
    checks = sql.export(statements(SQL_DIR / "05_quality_checks.sql")[0][1], checks_path)
    checks["result"] = checks.apply(
        lambda r: "PASS" if r.failing_rows == 0 else ("WARN" if "(warning)" in r.check_name else "FAIL"), axis=1)
    checks.to_csv(checks_path, index=False)
    print(checks.to_string(index=False))

    rows = sql.run("-h", "-1", "-W", "-w", "65535", "-Q",
                   "SET NOCOUNT ON; SELECT c.TABLE_NAME + '|' + CAST(COUNT(*) AS varchar(10)) "
                   "FROM INFORMATION_SCHEMA.COLUMNS c "
                   "JOIN INFORMATION_SCHEMA.VIEWS v ON v.TABLE_SCHEMA = c.TABLE_SCHEMA AND v.TABLE_NAME = c.TABLE_NAME "
                   "WHERE c.TABLE_SCHEMA = 'mart' GROUP BY c.TABLE_NAME ORDER BY c.TABLE_NAME")
    views = [line.strip().split("|") for line in rows.splitlines() if "|" in line]
    for view, n_cols in views:
        order_by = ", ".join(str(i) for i in range(1, int(n_cols) + 1))  # stable row order between runs
        sql.export(f"SELECT * FROM mart.{view} ORDER BY {order_by}", OUT_DIR / f"{view.removeprefix('v_')}.csv")
    print(f"\nexported {len(views)} analysis views to outputs/")
    TMP_FILE.unlink(missing_ok=True)

    failed = int((checks.result == "FAIL").sum())
    if failed:
        print(f"{failed} quality check(s) failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
