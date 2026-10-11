"""Thin engine adapter so the same pipeline runs on Snowflake (production) or
DuckDB (local dev / CI). SQL in /sql is written in the ANSI subset both support."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from . import config


class Engine:
    dialect = "duckdb"

    def execute(self, sql: str, params=None) -> None:
        raise NotImplementedError

    def query(self, sql: str, params=None) -> pd.DataFrame:
        raise NotImplementedError

    def load_df(self, df: pd.DataFrame, schema: str, table: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def run_script(self, path) -> None:
        text = Path(path).read_text()
        text = re.sub(r"--[^\n]*", "", text)  # strip line comments
        for stmt in (s.strip() for s in text.split(";")):
            if stmt:
                self.execute(stmt)


class DuckDBEngine(Engine):
    dialect = "duckdb"

    def __init__(self, path: str = ":memory:"):
        import duckdb

        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(path)

    def execute(self, sql, params=None):
        self.con.execute(sql, params or [])

    def query(self, sql, params=None):
        return self.con.execute(sql, params or []).df()

    def load_df(self, df, schema, table):
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self.con.register("_load_df", df)
        self.con.execute(f"CREATE OR REPLACE TABLE {schema}.{table} AS SELECT * FROM _load_df")
        self.con.unregister("_load_df")

    def close(self):
        self.con.close()


class SnowflakeEngine(Engine):
    dialect = "snowflake"

    def __init__(self, role: str | None = None):
        import snowflake.connector

        self.con = snowflake.connector.connect(
            account=config.env("SNOWFLAKE_ACCOUNT"),
            user=config.env("SNOWFLAKE_USER"),
            password=config.env("SNOWFLAKE_PASSWORD"),
            role=role or config.env("SNOWFLAKE_ROLE"),
            warehouse=config.env("SNOWFLAKE_WAREHOUSE"),
            database=config.env("SNOWFLAKE_DATABASE"),
        )

    @staticmethod
    def _bind(sql, params):
        # the connector's default paramstyle is pyformat; we write `?` everywhere
        return sql.replace("?", "%s") if params else sql

    def execute(self, sql, params=None):
        cur = self.con.cursor()
        try:
            cur.execute(self._bind(sql, params), params)
        finally:
            cur.close()

    def query(self, sql, params=None):
        cur = self.con.cursor()
        try:
            cur.execute(self._bind(sql, params), params)
            cols = [c[0].lower() for c in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
        finally:
            cur.close()
        for c in df.columns:  # Snowflake returns NUMBER as Decimal
            if df[c].dtype == object and len(df) and df[c].map(lambda v: hasattr(v, "as_tuple")).all():
                df[c] = df[c].astype(float)
        return df

    def load_df(self, df, schema, table):
        from snowflake.connector.pandas_tools import write_pandas

        self.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        d = df.copy()
        d.columns = [c.upper() for c in d.columns]  # unquoted identifiers resolve to UPPER
        write_pandas(self.con, d, table.upper(), schema=schema.upper(),
                     auto_create_table=True, overwrite=True)

    def close(self):
        self.con.close()


def get_engine(readonly: bool = False) -> Engine:
    if config.engine_name() == "snowflake":
        role = config.env("SNOWFLAKE_READONLY_ROLE") if readonly else None
        return SnowflakeEngine(role=role)
    return DuckDBEngine(config.duckdb_path())
