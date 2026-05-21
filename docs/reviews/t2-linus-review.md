# T2 Review — NetworkX Fallback (Arch Perspective)

**Reviewer**: Linus (Arch)  
**Date**: 2026-05-21  
**Deliverable**: `pathfinder/services/assessment_service.py` — graceful degradation on AGE failure  
**Tests**: 186 passed, 3 new fallback tests, 1 updated core test  
**Verdict**: ACCEPT WITH CONDITIONS

---

## 1. Design Intent vs. Implementation

The original council reform R2 (2026-05-18) mandated: "starting backend without PostgreSQL crashes with clear error, not silent fallback." I was the co-author of that finding with Guido.

However, the joint resolution later evolved to "degradation markers, not silent failure" — explicit markers (`degraded=True`, `confidence=0.0`, `path_backend='networkx_fallback'`) rather than either crashing or silently downgrading. This is the correct evolution. Crashing is appropriate for a startup gate; degradation is appropriate for a running service that must stay available. The implementation delivers this.

**Verdict**: The implementation correctly reflects the degradation-markers design.

## 2. Implementation Correctness

### What works:

- **startup_check()** correctly detects AGE connection failure and swaps to `InMemoryRoadmapGraph` with `_graph_backend = "networkx_fallback"` and `_age_unavailable = True`.
- **status()** correctly reports `degraded=True` with a human-readable `degraded_reason`.
- **generate_recommendation()** (sync) correctly injects `confidence=0.0`, `path_backend="networkx_fallback"`, and a `DEGRADED` warning.
- **Demo mode** correctly bypasses all degradation — no false degraded state.
- Tests cover all three scenarios: trigger, valid recommendation, demo non-degradation.

### What doesn't work:

**CRITICAL — Missing degradation markers in `generate_recommendation_async` (line 291-321):**

The sync path (`generate_recommendation`) applies the fallback markers correctly. The async path (`generate_recommendation_async`) does not. It calls `build_recommendation(path)` directly without checking `self._age_unavailable`. Since the actual API server uses `recommendations` endpoint → `generate_recommendation_async` (see `main.py` line 234), the degradation markers are **effectively dead code in production**.

```python
# Line 310-311 — NO degradation check
path = await self.solver.solve_async(state, self.rules, use_cypher=use_cypher)
recommendation = build_recommendation(path)
```

This is a functional gap. The API server will return recommendations during fallback **without** confidence=0.0 and without the DEGRADED warning. The tests don't catch this because `test_fallback_produces_valid_recommendation` calls the sync `generate_recommendation`, not the async variant.

**MEDIUM — `import_wp3` clobbers `networkx_fallback` backend label (line 388-392):**

```python
if isinstance(self.graph, AgeRoadmapGraph):
    self.graph.load_projection(nodes, edges)
else:
    self.graph = InMemoryRoadmapGraph(nodes, edges)
    self._graph_backend = "inmemory"  # ← overwrites "networkx_fallback"
```

If an admin imports WP3 data while the service is in fallback mode, `_graph_backend` gets set to `"inmemory"` — losing the `"networkx_fallback"` signal. The `_age_unavailable` flag survives (checked in `status()` for `degraded=True`), so the health endpoint is still correct. But `status()["graph_backend"]` would misleadingly report `"inmemory"` instead of `"networkx_fallback"`. This is a confusing inconsistency at best, a misleading status at worst.

**LOW — Dead code in startup_check loop detection (line 172):**

```python
ok = loop.run_until_complete(_check()) if False else None  # unreachable
```

The `if False` makes this dead. The `except RuntimeError` path correctly uses `asyncio.run()`. This is a code smell, not a bug — but it's sloppy. If someone removes the `if False`, this would crash on a running event loop. Just delete the dead branch.

## 3. Edge Cases

### 3.1 AGE reconnects mid-session

**No recovery path exists.** Once `_age_unavailable` is set to `True`, it is never cleared. There is no `reconnect_age()` method, no health-check retry loop, no watchdog. The service degrades and stays degraded until restart.

This is acceptable for V1/demo — the degraded state is honest and explicit. For production, you'd want a reconnect attempt with a backoff timer. But V1 is not production. Defer to V2.

### 3.2 Race condition: startup_check vs. concurrent requests

The startup_check runs synchronously in `__init__`. If the constructor is called during app startup (which it isn't — `main.py` uses `startup_check=False` and calls `connect_age()` separately in the lifespan), there's no race. If someone called `AssessmentService(startup_check=True)` from a request handler while the service is running, the `asyncio.run()` call would fail with "cannot be called from a running event loop" — and that failure would be caught by the outer try/except, leaving the AGE graph in place. Not great, but this is not a production code path.

### 3.3 Solver uses Python BFS in fallback mode

The `PathfinderSolver` constructor takes `InMemoryRoadmapGraph | AgeRoadmapGraph`. Both implement `shortest_path()`. The fallback swaps the graph instance before creating the solver, so the solver always gets a working graph. This is correct.

One subtlety: `solve_async` has a `use_cypher` parameter. If someone calls it with `use_cypher=True` during fallback, it will fall through to the `else` branch (since the graph is not `AgeRoadmapGraph`) and use Python BFS. Correct behavior, but the `path_backend` in the result would say `"python"`, not `"networkx_fallback"`. The sync `solve()` always returns `path_backend="python"` (line 77). These labels are solver-level, not service-level — the service overrides with its own marker in `generate_recommendation()`. No conflict, but the labeling is inconsistent between layers.

### 3.4 Concurrent WP3 import during fallback

If two admins import WP3 simultaneously during fallback, both would create new `InMemoryRoadmapGraph` instances and swap them. The last write wins, and both would clobber `_graph_backend` to `"inmemory"`. No data corruption, just the label issue noted above. Low severity for V1.

## 4. Confidence=0.0 Signal

**Is confidence=0.0 the right signal?**

Yes. When the graph backend is degraded from AGE (Cypher shortest-path on a proper graph database) to NetworkX (Python BFS on in-memory adjacency lists), we cannot assert that the path computation is identical. The path *should* be identical (both are BFS shortest-path on the same node/edge set), but we're running a different code path on different infrastructure. Setting confidence to 0.0 is the honest thing to do — it says "we computed a path, but we have zero confidence it's the same path the production system would have computed."

It's aggressive. In practice, for the same graph, BFS on NetworkX and BFS on AGE Cypher should produce the same shortest path. But "should" is not "proven," and the confidence signal drives downstream behavior. 0.0 ensures the DEGRADED warning gets attention.

**Recommendation**: Keep 0.0. It's the correct architectural choice for a degradation scenario. If the paths are proven identical later (by running both backends side-by-side and comparing results), we could raise it to something like 0.5 with a "verified fallback" tag. But that's V2.

## 5. Architecture Debt Assessment

### Debt inventory:

| Item | Severity | Deferrable? |
|------|----------|-------------|
| `generate_recommendation_async` missing degradation markers | **HIGH** | No — fix now |
| `import_wp3` clobbers `_graph_backend` label | MEDIUM | Yes, if labels are documented as informational |
| Dead code in loop detection (line 172) | LOW | Yes |
| No recovery path from fallback | LOW | Yes (V2) |
| Duplicated `_graph_backend` management (set in __init__, startup_check, import_wp3) | MEDIUM | Yes (refactor opportunity) |
| `generate_recommendation_async` duplicates ~80% of sync variant logic | MEDIUM | Yes (pre-existing, not T2-specific) |

### Architecture concern: backend label is managed in 3 places

`_graph_backend` is set in:
1. `__init__` line 73: `"age"` or `"inmemory"`
2. `startup_check` line 179: `"networkx_fallback"`
3. `import_wp3` line 392: `"inmemory"` (clobber)

This is a state management smell. The backend label should be a **derived property**, not a manually tracked field:

```python
@property
def _graph_backend(self) -> str:
    if isinstance(self.graph, AgeRoadmapGraph):
        return "age"
    if self._age_unavailable:
        return "networkx_fallback"
    return "inmemory"
```

But this is refactoring, not a T2 blocker. File as technical debt.

## 6. Relationship to the Original R2 Mandate

The original R2 (Council Reforms, 2026-05-18) said:

> "Starting backend without PostgreSQL (in deployed mode) crashes with clear error, not silent fallback."

The T2 implementation does the **opposite**: it degrades gracefully instead of crashing. This is a deliberate evolution of the design (joint resolution 15/0), not a violation. The key insight is that R2 was about **startup gating** (fail fast before serving requests), while T2 is about **runtime resilience** (stay available with explicit degradation markers).

The test at line 152-164 of `test_pathfinder_core.py` confirms this: the test name is `test_deployed_mode_startup_check_raises_when_age_connect_fails` but the comment says "startup_check now degrades gracefully instead of raising." The test name is stale — it should be renamed to `test_deployed_mode_startup_check_degrades_gracefully`. Small thing, but stale names are how confusion propagates.

## 7. Required Actions

### Must-fix (before merge acceptance):

1. **Add degradation markers to `generate_recommendation_async`** — mirror the logic from the sync variant (lines 270-279). This is the actual code path used by the API server.

### Should-fix (low effort, high value):

2. **Guard `import_wp3` against clobbering `networkx_fallback`** — preserve the fallback label:
   ```python
   if not self._age_unavailable:
       self._graph_backend = "inmemory"
   ```

3. **Remove dead code** at line 172 (`if False` branch).

4. **Rename test** `test_deployed_mode_startup_check_raises_when_age_connect_fails` → `test_deployed_mode_startup_check_degrades_gracefully`.

### Defer to V2:

5. Recovery path from fallback (reconnect attempt, health retry).
6. Refactor `_graph_backend` into a derived property.

## 8. Summary

The T2 implementation correctly delivers graceful degradation with explicit markers: `degraded=True`, `confidence=0.0`, `path_backend="networkx_fallback"`, DEGRADED warning. The design matches the evolved specification (degradation markers, not crash, not silent fallback).

However, the degradation markers are only applied in the **sync** recommendation path, not the **async** path used by the actual API server. This is a functional gap that makes the fallback effectively invisible in production. Fixing this is a 5-line change.

Additionally, `import_wp3` during fallback clobbers the backend label. Low severity but sloppy.

The architecture is sound for V1. The technical debt is manageable and mostly deferrable. The core design decision — explicit degradation over silent failure — is correct and well-implemented.

**Verdict: ACCEPT WITH CONDITIONS** — fix the async path gap and the import_wp3 label clobber before closing T2.
