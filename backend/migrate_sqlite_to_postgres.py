"""
SQLite -> PostgreSQL Data Migration Script
Migrates all data from rag_seo.db to the PostgreSQL container.

Handles:
- Boolean: SQLite 0/1 -> PostgreSQL True/False
- JSON: dict/list objects -> json.dumps() for psycopg2
- Type coercion for strict PostgreSQL type checking

Usage:
    1. Ensure PostgreSQL container is running: docker compose up -d postgres
    2. Run: python migrate_sqlite_to_postgres.py
"""

import sqlite3
import json
import sys
import os
from sqlalchemy import create_engine, text, inspect, Boolean, JSON
from sqlalchemy.dialects.postgresql import JSONB

# Source: SQLite
SQLITE_PATH = "./rag_seo.db"

# Target: PostgreSQL (matches docker-compose.yml)
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://raguser:changeme@localhost:5432/rag_seo")


def migrate():
    print("=" * 60)
    print("SQLite -> PostgreSQL Migration")
    print("=" * 60)

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL directly
    pg_engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

    # Initialize the PostgreSQL schema using the app's models
    print("\n[1/4] Initializing PostgreSQL schema...")
    sys.path.insert(0, os.path.dirname(__file__))
    os.environ["USE_POSTGRES"] = "true"
    os.environ["POSTGRES_URL"] = POSTGRES_URL

    from app.db.session import Base
    from app.models import (
        Product, ContentDraft, SupplierPart, ScrapingJob, AIAnalysisCache,
        Library, Document, DocumentChunk, PromptTemplate, GenerationHistory,
        StoreSnapshot, IntelligenceReport, AIRecommendation, MetricTrend,
        KeywordDailyMetric, PageDailyMetric, KeywordPageMapping,
        GA4FunnelDaily, ContentGapResult, SEOAlert
    )
    try:
        import app.models.collection_optimizer_models
    except Exception:
        pass
    try:
        import app.models.solution_engine
    except Exception:
        pass
    try:
        import app.models.aeo_models
    except Exception:
        pass

    Base.metadata.create_all(bind=pg_engine)
    print("   Schema created successfully.")

    # Build a map of PostgreSQL column types for type coercion
    pg_inspector = inspect(pg_engine)
    pg_tables = pg_inspector.get_table_names()

    # Build column type map: {table: {col: type_obj}}
    pg_col_types = {}
    for tbl in pg_tables:
        pg_col_types[tbl] = {}
        for col_info in pg_inspector.get_columns(tbl):
            pg_col_types[tbl][col_info["name"]] = col_info["type"]

    # Get all SQLite tables
    sqlite_cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
    )
    tables = [row[0] for row in sqlite_cursor.fetchall()]
    print(f"\n[2/4] Found {len(tables)} tables in SQLite")
    print(f"   PostgreSQL has {len(pg_tables)} tables.")

    # Determine table order (tables with FKs should come after their parents)
    # Simple approach: put known parent tables first
    parent_tables = ["products", "prompt_templates", "libraries", "documents", "fault_codes", "collection_optimizer"]
    ordered_tables = [t for t in parent_tables if t in tables]
    ordered_tables += [t for t in tables if t not in ordered_tables]

    # Migrate each table
    print("\n[3/4] Migrating data...")
    total_rows = 0
    errors = []

    for table_name in ordered_tables:
        if table_name not in pg_tables:
            continue

        # Count rows
        sqlite_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        count = sqlite_cursor.fetchone()[0]
        if count == 0:
            continue

        # Get PG column names
        pg_columns = list(pg_col_types[table_name].keys())

        # Get SQLite data
        sqlite_cursor.execute(f'SELECT * FROM "{table_name}"')
        sqlite_columns = [desc[0] for desc in sqlite_cursor.description]
        common_columns = [c for c in sqlite_columns if c in pg_columns]

        if not common_columns:
            continue

        rows = sqlite_cursor.fetchall()

        # Identify boolean and JSON columns in PostgreSQL
        bool_cols = set()
        json_cols = set()
        for col in common_columns:
            col_type = pg_col_types[table_name].get(col)
            if col_type is not None:
                type_str = str(col_type).upper()
                if "BOOLEAN" in type_str:
                    bool_cols.add(col)
                elif "JSON" in type_str:
                    json_cols.add(col)

        inserted = 0
        table_errors = 0

        with pg_engine.begin() as conn:
            conn.execute(text(f'TRUNCATE "{table_name}" CASCADE'))

            for row in rows:
                row_dict = dict(row)
                values = {}

                for col in common_columns:
                    val = row_dict.get(col)

                    # Convert booleans: SQLite stores 0/1
                    if col in bool_cols:
                        if val is not None:
                            val = bool(val)

                    # Convert JSON columns
                    elif col in json_cols:
                        if isinstance(val, (dict, list)):
                            val = json.dumps(val, default=str)
                        elif isinstance(val, str):
                            # Validate it's proper JSON, pass as-is
                            try:
                                json.loads(val)
                            except (json.JSONDecodeError, ValueError):
                                val = json.dumps(val)
                        elif val is not None:
                            val = json.dumps(val, default=str)

                    # Handle dict/list in non-JSON columns (shouldn't happen but safety)
                    elif isinstance(val, (dict, list)):
                        val = json.dumps(val, default=str)

                    values[col] = val

                cols_str = ", ".join(f'"{c}"' for c in values.keys())
                placeholders = ", ".join(f":{c}" for c in values.keys())

                # For JSON columns, cast the placeholder
                parts = []
                for c in values.keys():
                    if c in json_cols:
                        parts.append(f"CAST(:{c} AS JSON)")
                    else:
                        parts.append(f":{c}")
                placeholders = ", ".join(parts)

                try:
                    conn.execute(
                        text(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'),
                        values
                    )
                    inserted += 1
                except Exception as e:
                    table_errors += 1
                    if table_errors <= 1:
                        err_msg = str(e)[:150]
                        errors.append(f"{table_name}: {err_msg}")

        total_rows += inserted
        status = "OK" if inserted == count else "PARTIAL"
        if inserted == 0 and count > 0:
            status = "FAIL"
        print(f"   {status} {table_name}: {inserted}/{count} rows" +
              (f" ({table_errors} errors)" if table_errors else ""))

    # Reset sequences for PostgreSQL auto-increment
    print("\n[4/4] Resetting PostgreSQL sequences...")
    with pg_engine.begin() as conn:
        for table_name in pg_tables:
            try:
                result = conn.execute(text(
                    f"SELECT MAX(id) FROM \"{table_name}\" WHERE id ~ '^[0-9]+$'"
                ))
                max_id = result.scalar()
                if max_id:
                    conn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {int(max_id)})"
                    ))
            except Exception:
                pass

    print(f"\n{'=' * 60}")
    print(f"Migration complete! {total_rows} total rows migrated.")
    if errors:
        print(f"\nFirst errors per table:")
        for e in errors:
            print(f"  - {e}")
    print(f"{'=' * 60}")

    sqlite_conn.close()


if __name__ == "__main__":
    migrate()
