#!/usr/bin/env python3
"""Install the idempotent PostgreSQL boundary storage schema."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', default='pf_boundary')
    parser.add_argument('--runtime-role', help='existing runtime role to grant data access after migration')
    args = parser.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    store = PostgresBoundaryStore(dsn, schema=args.schema)
    store.migrate()
    if args.runtime_role:
        store.grant_runtime(args.runtime_role)
    store.check_schema()
    print("Boundary storage schema v2 migration applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
