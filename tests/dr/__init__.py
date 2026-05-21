"""DR (Disaster Recovery) verification tests — P4.

4-layer verification:
  V1: sha256 file integrity
  V2: pg_restore schema recovery
  V3: AGE catalog consistency
  V4: total row count comparison

Joint resolution 16/0, 2026-05-20.
"""
