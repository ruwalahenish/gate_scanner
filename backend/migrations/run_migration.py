"""
Run SQL migration against NeonDB when psql is not installed.

Usage:
    python backend/migrations/run_migration.py
    python backend/migrations/run_migration.py backend/migrations/001_initial_schema.sql
"""

import os
import sys
import re
import asyncio
import asyncpg


def get_database_url():
    """Read DATABASE_URL from .env file or environment."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip()

    print("ERROR: DATABASE_URL not found in environment or .env file")
    sys.exit(1)


def strip_comments(line):
    """Strip standard single-line '--' comments not within single quotes."""
    in_quote = False
    i = 0
    while i < len(line) - 1:
        if line[i] == "'":
            in_quote = not in_quote
            i += 1
        elif line[i:i+2] == "--" and not in_quote:
            return line[:i]
        else:
            i += 1
    return line


def split_sql_statements(sql):
    """
    Split SQL into statements, respecting DO $$ ... END $$; blocks
    which contain semicolons internally, and ignoring semicolons inside comments.
    """
    statements = []
    current = []
    in_dollar_block = False

    for line in sql.split("\n"):
        stripped_line = strip_comments(line)
        stripped = stripped_line.strip()

        # Detect start of DO $$ block
        if re.match(r"^DO\s+\$\$", stripped, re.IGNORECASE):
            in_dollar_block = True
            current.append(line)
            continue

        # Detect end of DO $$ block
        if in_dollar_block and re.match(r"^END\s+\$\$\s*;?\s*$", stripped, re.IGNORECASE):
            current.append(line)
            statements.append("\n".join(current))
            current = []
            in_dollar_block = False
            continue

        if in_dollar_block:
            current.append(line)
            continue

        # Normal mode: split on semicolons
        if ";" in stripped_line:
            idx = stripped_line.index(";")
            part0 = line[:idx]
            current.append(part0)
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)
            leftover = line[idx+1:]
            current = [leftover] if leftover.strip() else []
        else:
            current.append(line)

    # Any remaining content
    leftover = "\n".join(current).strip()
    if leftover:
        statements.append(leftover)

    return statements


async def run_migration(sql_file):
    """Execute a SQL migration file statement-by-statement."""
    db_url = get_database_url()
    display_url = db_url.split("@")[-1] if "@" in db_url else db_url
    print(f"\n  Connecting to: ...@{display_url}")

    conn = await asyncpg.connect(db_url)
    
    with open(sql_file, "r", encoding="utf-8") as f:
        sql = f.read()

    statements = split_sql_statements(sql)

    success = 0
    skipped = 0
    errors = 0

    for stmt in statements:
        # Skip pure comment blocks
        lines = [l for l in stmt.split("\n") if l.strip() and not l.strip().startswith("--")]
        if not lines:
            continue

        try:
            async with conn.transaction():
                await conn.execute(stmt)
            success += 1
        except asyncpg.exceptions.DuplicateObjectError as e:
            skipped += 1
            msg = str(e).strip().split("\n")[0]
            print(f"  SKIP: {msg}")
        except asyncpg.exceptions.DuplicateTableError as e:
            skipped += 1
            msg = str(e).strip().split("\n")[0]
            print(f"  SKIP: {msg}")
        except Exception as e:
            errors += 1
            msg = str(e).strip().split("\n")[0]
            first_line = lines[0][:80] if lines else "?"
            print(f"  ERROR: {msg}")
            print(f"    SQL: {first_line}...")

    await conn.close()

    print(f"\n  Migration complete!")
    print(f"    {success} statements executed")
    if skipped:
        print(f"    {skipped} skipped (already exist)")
    if errors:
        print(f"    {errors} errors")
    print()

    return errors == 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]
    else:
        sql_file = os.path.join(os.path.dirname(__file__), "001_initial_schema.sql")

    if not os.path.exists(sql_file):
        print(f"ERROR: SQL file not found: {sql_file}")
        sys.exit(1)

    print(f"  Running migration: {os.path.basename(sql_file)}")
    ok = asyncio.run(run_migration(sql_file))
    sys.exit(0 if ok else 1)

