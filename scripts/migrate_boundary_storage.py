#!/usr/bin/env python3
"""Install the idempotent PostgreSQL boundary storage schema."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    store = PostgresBoundaryStore(dsn)
    store.migrate()
    store.check_schema()
    print("Boundary storage migration applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
