#!/usr/bin/env python3
"""Validate WP boundary snapshots using the runtime validator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathfinder.core.boundary_validation import *  # compatibility for existing consumers
from pathfinder.core.boundary_validation import main

if __name__ == "__main__":
    sys.exit(main())
