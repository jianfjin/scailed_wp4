# SCAILED WP4 Pathfinder — Dijkstra (CSO) Formal Methods Audit

**Audit Date**: 2026-05-14

---

## 1. S ⊆ ℝⁿ State Space — Over-Formalization

Stakeholder self-assessment data comes from questionnaires (discrete Likert scales, multiple choice, booleans). Attempting to embed this in ℝⁿ continuous space is pseudomathematics of the worst kind.

Questionnaire answers produce categorical data (nominal/ordinal), not metric data. S should be defined as a finite discrete set: S = ∏ᵢ Aᵢ, where Aᵢ is the answer option set for question i. This is not a subset of ℝⁿ — there is no meaningful way to define addition or scalar multiplication.

The term "state vector" applied to self-assessment data is incorrect terminology, borrowed from an AI/ML culture with no respect for data semantics.

**Correction**: S should be defined as a Set of Profiles, where each profile is a partial function of (attribute, value) pairs. The matching function f: S×V→ℝ should be replaced with a rule-based multi-criteria scoring function — which has better mathematical properties than "argmin" for discrete profiles.

---

## 2. Dijkstra Shortest Path — Naming Abuse

The shortest path algorithm (Dijkstra 1959, not 1956) solves a deterministic problem: given a fixed graph and fixed edge weights, find the minimum-cost path. But the situation here is fundamentally different.

Under regulatory constraints, edge feasibility depends on stakeholder state. Whether a path is feasible is not an inherent property of the graph — it is a function of (state, path) pairs.

This is a **Constraint Satisfaction Problem (CSP)**, not a shortest path problem.

Recommendation: "Constrained graph search" rather than "Dijkstra shortest path." Do not say "A*" — the document mentions A* but the heuristic function h(n) is never defined. A* requires h to be admissible (h(n) ≤ h*(n)). Without an admissibility proof, A* is not credible.

Solver code issue: locate() iterates all compliant nodes. plan_path() runs shortest_path only on the compliant node subgraph. But if the subgraph does not contain the endpoints (current node and target node happen to be excluded by rules) — how does the code behave? Under current design, subgraph.subgraph() does not check whether the subgraph is connected or whether it contains the requested nodes. **This is a source of runtime exceptions**, which should be handled by a dedicated DisconnectedGraphError rather than a KeyError.

---

## 3. Invariant I1 (Monotonicity) — Definition is Vague

The document claims "state transitions are continuous." Self-assessment data consists of discrete questionnaire answers. "Continuity" has no meaning on a discrete set.

If the intention is monotonicity (states monotonically improve along the path) — this mathematically requires a partial order relation and a monotonic function proof. The current document defines no such partial order.

**Correction**: Define precisely what is changing monotonically. Is the maturity level increasing? Is the compliance score accumulating? Is the presence of certain attributes after each step? The definition must be precise — this is not philosophy, this is mathematics.

---

## 4. argmin Not Unique — "Positioning" Wording Risk

The email says "strategic positioning and navigation system with compliance constraints." Positioning requires argmin — the node v minimizing f(s,v). But argmin in a discrete non-convex space may not be unique.

What happens if there are ≥2 nodes with identical minimum distance for a given profile? Neither the email nor the documents address this.

**Correction**: Documents should define a deterministic tie-breaking rule — such as "among all argmin nodes, the one with the smallest node_id in lexicographic order."

---

## 5. Complexity Analysis — Horn Clause Assumption Has No Basis

Complexity claim: "Constraint checking O(k) if Horn clauses."

Are WP8 regulatory constraints genuinely Horn clauses? Regulatory text is rarely expressed in pure Horn form. They contain contradictions, exceptions, priority rules, "where reasonably practicable" vagueness — none of which is capturable by propositional logic, let alone Horn clauses.

Horn clause satisfiability is polynomial-time, but general propositional satisfiability is NP-complete. If WP8 rules contain non-Horn structures (such as A∨B as premises), constraint checking complexity jumps to NP.

_is_compliant() time complexity depends on how condition JSONB is parsed into runtime expressions. Worst case, if cross-table queries are required, this is O(n) or worse.

locate() is O(|V|·C). |V|=100 is fine. |V|=10,000 is a performance disaster — linear scan is insufficient, spatial indexing is needed.

---

## 6. Supplementary Audit: Math/Logic Holes Across Three Documents

**[00_council_resolution.md]**
1. Risk matrix has no mathematical definition: "Very High/High/Medium/Low" without probability thresholds. Risk = P×I, but neither P nor I is quantified.
2. "A*" mentioned but h(n) never defined. No admissibility proof.
3. Timeline origin undefined: Is M1 the contract signing date or project start date? If contract signed after M1, entire timeline shifts.

**[09_expanded_analysis.md — Technical Implementation]**
4. SQL schema defects: roadmap_nodes missing foreign key constraints to guarantee DAG structural integrity; recommendation_rules condition JSONB missing Schema definition.
5. audit_log "immutable" claim is dishonest — PostgreSQL RULE provides no cryptographic guarantee.
6. Formal definition references NetworkX graphs — but NetworkX does not enforce DAG structure, relying on runtime is_directed_acyclic_graph() calls.
7. Solver code analysis: subgraph.subgraph() does not check endpoint containment; exception NoFeasiblePositionError promises a formal guarantee of position existence (but does not implement that guarantee).

---

## Audit Conclusions and Action Checklist

| Priority | Action | Category |
|----------|--------|----------|
| P0 | Change S from ℝⁿ to finite discrete profile set | Fix Formalization |
| P0 | Rename "Dijkstra shortest path" to "constrained graph search" | Fix Naming |
| P0 | Define deterministic tie-breaking rule | Complete Algorithm |
| P1 | Handle subgraph not containing endpoints exception | Fix Code |
| P1 | Provide upper bound proof for locate() and plan_path() complexity | Complete Analysis |
| P1 | Fix table structure reference errors in solver.py | Fix Code |
| P2 | Replace audit_log "immutable" with "append-restricted" or implement cryptographic audit chain | Security Hardening |
| P2 | Clarify ip_hash pseudo-anonymization nature | Complete Docs |
| P3 | "Topological sort proof" → "topological sort verification script and output" | Contract Wording |
| P3 | "Auditable traceability" → "complete input-output snapshot recorded per query" | Contract Wording |
| P3 | Delete "A*" mentions unless admissible heuristic with proof provided | Fix Docs |

---

This proposal is roughly one hundred thousand miles from "provably correct."
