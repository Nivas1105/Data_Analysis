import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional
    pass

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
REPORT_DIR = ROOT / "reports"


def env(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def engine_name():
    return env("FQ_ENGINE", "duckdb")


def duckdb_path():
    return env("FQ_DUCKDB_PATH", str(ROOT / "data" / "fq.duckdb"))


def llm_provider():
    return env("FQ_LLM_PROVIDER", "none")
