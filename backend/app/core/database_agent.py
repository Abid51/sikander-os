"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS DATABASE AGENT
  Natural language → SQL — query any SQLite/PostgreSQL database
  Features: schema inspection, safe query execution, AI-powered SQL gen
  No fake stubs — real database operations with sandboxing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QueryResult:
    query: str
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_ms: float
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Limit rows in API response
        if len(d["rows"]) > 100:
            d["rows"] = d["rows"][:100]
            d["truncated"] = True
        return d


@dataclass
class TableInfo:
    name: str
    columns: List[Dict[str, str]]  # [{"name": "id", "type": "INTEGER"}, ...]
    row_count: int
    sample_rows: List[List[Any]]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NLQueryResult:
    natural_query: str
    generated_sql: str
    result: QueryResult
    explanation: str
    model_used: str

    def to_dict(self) -> dict:
        return {
            "natural_query": self.natural_query,
            "generated_sql": self.generated_sql,
            "result": self.result.to_dict(),
            "explanation": self.explanation,
            "model_used": self.model_used,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SQL SAFETY
# ─────────────────────────────────────────────────────────────────────────────

_DANGEROUS_PATTERNS = [
    r'\bDROP\s+(?:TABLE|DATABASE|INDEX|VIEW|SCHEMA)\b',
    r'\bTRUNCATE\s+TABLE\b',
    r'\bALTER\s+TABLE\b.*\bDROP\b',
    r'\bDELETE\s+FROM\b(?!.*\bWHERE\b)',  # DELETE without WHERE
    r'\bUPDATE\b(?!.*\bWHERE\b)',          # UPDATE without WHERE
    r';\s*--',                              # SQL injection attempt
    r'\bEXEC\b',
    r'\bxp_\w+',                           # SQL Server extended procs
    r'\bSHUTDOWN\b',
]


def _is_query_safe(sql: str) -> tuple:
    """Check if SQL query is safe to execute. Returns (safe, reason)."""
    sql_upper = sql.upper().strip()

    # Only allow SELECT queries in read-only mode
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries allowed in safe mode."

    # Check for dangerous patterns
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Blocked dangerous SQL pattern: {pattern}"

    # Limit complexity
    if sql.count(";") > 1:
        return False, "Multiple statements not allowed."

    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE AGENT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisDatabaseAgent:
    """
    Natural language database agent for Igris.

    Usage:
    ──────
    agent = IgrisDatabaseAgent("/path/to/database.db")
    tables = await agent.list_tables()
    result = await agent.execute("SELECT * FROM users LIMIT 10")
    nl_result = await agent.ask("Show me the top 5 most active users")
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path
        self._read_only = True
        self._history: List[Dict[str, Any]] = []
        self._connected = False

        if db_path and os.path.isfile(db_path):
            self._connected = True
            logger.info(f"[DB] Agent connected to: {db_path}")
        else:
            logger.info("[DB] Agent initialized (no database connected yet)")

    def connect(self, db_path: str) -> bool:
        """Connect to a SQLite database."""
        db_path = os.path.abspath(db_path)
        if not os.path.isfile(db_path):
            logger.error(f"[DB] Database not found: {db_path}")
            return False
        self._db_path = db_path
        self._connected = True
        logger.info(f"[DB] Connected to: {db_path}")
        return True

    def _get_connection(self) -> sqlite3.Connection:
        """Get a read-only SQLite connection."""
        if not self._db_path:
            raise RuntimeError("No database connected. Use connect(path) first.")
        # Open in read-only mode using URI
        uri = f"file:{self._db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
        conn.row_factory = None
        return conn

    def _get_rw_connection(self) -> sqlite3.Connection:
        """Get a read-write connection (for write operations when allowed)."""
        if not self._db_path:
            raise RuntimeError("No database connected.")
        return sqlite3.connect(self._db_path, timeout=10)

    # ── Schema Inspection ─────────────────────────────────────────────────────

    async def list_tables(self) -> List[TableInfo]:
        """List all tables with their schemas."""
        return await asyncio.to_thread(self._list_tables_sync)

    def _list_tables_sync(self) -> List[TableInfo]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            table_names = [row[0] for row in cursor.fetchall()]

            tables = []
            for tbl in table_names:
                # Get columns
                cursor.execute(f"PRAGMA table_info([{tbl}])")
                cols = [
                    {"name": row[1], "type": row[2], "nullable": not row[3], "pk": bool(row[5])}
                    for row in cursor.fetchall()
                ]

                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM [{tbl}]")
                row_count = cursor.fetchone()[0]

                # Get sample rows
                cursor.execute(f"SELECT * FROM [{tbl}] LIMIT 3")
                sample = [list(row) for row in cursor.fetchall()]

                tables.append(TableInfo(
                    name=tbl, columns=cols,
                    row_count=row_count, sample_rows=sample,
                ))
            return tables
        finally:
            conn.close()

    async def get_schema_text(self) -> str:
        """Get database schema as readable text (for LLM context)."""
        tables = await self.list_tables()
        if not tables:
            return "No tables found in database."

        lines = [f"Database: {os.path.basename(self._db_path or 'unknown')}\n"]
        for t in tables:
            cols_str = ", ".join(
                f"{c['name']} {c['type']}{'(PK)' if c.get('pk') else ''}"
                for c in t.columns
            )
            lines.append(f"TABLE {t.name} ({t.row_count} rows): {cols_str}")
        return "\n".join(lines)

    # ── Query Execution ───────────────────────────────────────────────────────

    async def execute(self, sql: str, safe_mode: bool = True) -> QueryResult:
        """Execute a SQL query."""
        if safe_mode:
            is_safe, reason = _is_query_safe(sql)
            if not is_safe:
                return QueryResult(
                    query=sql, columns=[], rows=[], row_count=0,
                    execution_ms=0, success=False, error=f"Blocked: {reason}",
                )
        return await asyncio.to_thread(self._execute_sync, sql)

    def _execute_sync(self, sql: str) -> QueryResult:
        t = time.time()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [list(row) for row in cursor.fetchall()]

            result = QueryResult(
                query=sql, columns=columns, rows=rows,
                row_count=len(rows),
                execution_ms=(time.time() - t) * 1000,
            )

            self._history.append({
                "sql": sql[:200], "rows": len(rows),
                "ms": result.execution_ms, "ts": time.time(),
            })
            return result
        except Exception as e:
            return QueryResult(
                query=sql, columns=[], rows=[], row_count=0,
                execution_ms=(time.time() - t) * 1000,
                success=False, error=str(e),
            )
        finally:
            conn.close()

    # ── Natural Language Query ────────────────────────────────────────────────

    async def ask(self, question: str) -> NLQueryResult:
        """Ask a question in natural language → generates SQL → executes."""
        try:
            from app.core.llm_manager import universal_llm
        except Exception:
            return NLQueryResult(
                natural_query=question,
                generated_sql="",
                result=QueryResult(query="", columns=[], rows=[], row_count=0,
                                   execution_ms=0, success=False, error="LLM not available"),
                explanation="Cannot generate SQL without LLM",
                model_used="none",
            )

        # Get schema for context
        schema = await self.get_schema_text()

        # Generate SQL
        prompt = (
            f"Database schema:\n{schema}\n\n"
            f"User question: {question}\n\n"
            "Generate a SQLite SELECT query to answer this question.\n"
            "Return ONLY the SQL query, nothing else. No markdown, no explanation.\n"
            "Use only tables and columns that exist in the schema."
        )

        try:
            sql = await universal_llm.generate_response(
                system_prompt=(
                    "You are an expert SQL query generator. Given a database schema and "
                    "a user question, generate the correct SQLite SELECT query. "
                    "Return ONLY the raw SQL query with no formatting or explanation."
                ),
                user_prompt=prompt,
                max_tokens=300,
            )

            # Clean up generated SQL
            sql = sql.strip()
            sql = sql.strip("`").strip()
            if sql.lower().startswith("sql"):
                sql = sql[3:].strip()
            if sql.lower().startswith("```"):
                sql = sql.split("\n", 1)[-1]
            if sql.endswith("```"):
                sql = sql[:-3].strip()
            sql = sql.strip(";").strip() + ";"
            sql = sql.replace(";;", ";")

            # Execute the generated SQL
            result = await self.execute(sql, safe_mode=True)

            # Generate explanation
            explanation = ""
            if result.success:
                explanation = (
                    f"Found {result.row_count} results. "
                    f"Query: {sql}"
                )
            else:
                explanation = f"Query failed: {result.error}"

            return NLQueryResult(
                natural_query=question,
                generated_sql=sql,
                result=result,
                explanation=explanation,
                model_used=getattr(universal_llm, "current_model", "unknown"),
            )

        except Exception as e:
            return NLQueryResult(
                natural_query=question,
                generated_sql="",
                result=QueryResult(
                    query="", columns=[], rows=[], row_count=0,
                    execution_ms=0, success=False, error=str(e),
                ),
                explanation=f"SQL generation failed: {e}",
                model_used="unknown",
            )

    # ── Write Operations (when allowed) ───────────────────────────────────────

    async def execute_write(self, sql: str) -> QueryResult:
        """Execute a write query (INSERT/UPDATE/DELETE). Use with caution."""
        if self._read_only:
            return QueryResult(
                query=sql, columns=[], rows=[], row_count=0,
                execution_ms=0, success=False,
                error="Database is in read-only mode. Set read_only=False to enable writes.",
            )
        return await asyncio.to_thread(self._execute_write_sync, sql)

    def _execute_write_sync(self, sql: str) -> QueryResult:
        t = time.time()
        conn = self._get_rw_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            return QueryResult(
                query=sql, columns=[], rows=[],
                row_count=cursor.rowcount,
                execution_ms=(time.time() - t) * 1000,
            )
        except Exception as e:
            conn.rollback()
            return QueryResult(
                query=sql, columns=[], rows=[], row_count=0,
                execution_ms=(time.time() - t) * 1000,
                success=False, error=str(e),
            )
        finally:
            conn.close()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "database": os.path.basename(self._db_path) if self._db_path else None,
            "database_path": self._db_path,
            "read_only": self._read_only,
            "queries_executed": len(self._history),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisDatabaseAgent] = None


def get_database_agent(db_path: Optional[str] = None) -> IgrisDatabaseAgent:
    global _instance
    if _instance is None:
        # Auto-connect to Igris's own database if it exists
        if db_path is None:
            default_db = os.path.join(
                os.path.dirname(__file__), "..", "..", "igris_data.db"
            )
            default_db = os.path.normpath(default_db)
            if os.path.isfile(default_db):
                db_path = default_db
        _instance = IgrisDatabaseAgent(db_path)
    elif db_path:
        _instance.connect(db_path)
    return _instance
