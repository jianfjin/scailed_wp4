# SCAILED WP4 Pathfinder — 6-Seat Joint Audit Final Report

**Lead Auditor**: Feng Ge / CTO
**Audit Date**: 2026-05-14
**Audit Scope**: 00_council_resolution.md + 09_expanded_analysis.md + email_to_lu_zhao_v1.md
**Participating Seats**: Xuefeng(CSA) / Musk(CVO) / Jobs(CPO) / Linus(Arch) / Guido(CLA) / Dijkstra(CSO)

---

## Comprehensive Risk Matrix (6-Seat Cross-Validation)

| Risk ID | Description | Source | Severity | Consensus |
|---------|-------------|--------|----------|-----------|
| R1 | EU4Health IP rules: "DataWego retains core engine copyright" violates Foreground IP rules | Xuefeng, Guido | 🔴 Critical | ✅ Dual-confirmed |
| R2 | EUR-X/day left blank + rework clause missing approval process and cap | Xuefeng | 🔴 Critical | ✅ Confirmed |
| R3 | NetworkX+JSONB graph computation collapses at 200+ nodes | Linus | 🔴 Critical | ✅ Confirmed |
| R4 | M9 payment tied to CHARITE receipt creates cash flow break risk | Xuefeng | 🔴 Critical | ✅ Confirmed |
| R5 | WP3 structured data dependency has no Plan B | Musk, Jobs | 🔴 Critical | ✅ Dual-confirmed |
| R6 | Schema freeze lacks auto-extension mechanism | Xuefeng | 🔴 Very High | ✅ Confirmed |
| R7 | audit_log using PostgreSQL RULE is unreliable | Linus, Guido | 🟠 High | ✅ Dual-confirmed |
| R8 | recommendation_rules missing tree structure (parent_rule_id) | Linus | 🟠 High | ✅ Confirmed |
| R9 | Pydantic models/exception classes/rule DSL completely missing | Guido | 🟠 High | ✅ Confirmed |
| R10 | Email wording: Apple analogy + navigation overpromise + SHAIPED political risk | Jobs, Musk, Guido, Xuefeng | 🟠 High | ✅ Quad-confirmed |
| R11 | 36-month timeline has Parkinson's disease, MVP compressible to 3-4 months | Musk | 🟡 Notable | ⚠️ Single seat |
| R12 | "Not AI" positioning too defensive | Musk | 🟡 Notable | ⚠️ Single seat |
| R13 | Low-fidelity prototype insufficient to lock QA-culture requirements | Xuefeng, Jobs | 🟡 Notable | ✅ Dual-confirmed |
| R14 | Missing user stories/demo/soul | Jobs | 🟡 Notable | ⚠️ Single seat |
| R15 | Acceptance criteria missing test condition specifications | Xuefeng | 🟡 Notable | ✅ Confirmed |
| R16 | FastAPI event loop blocking risk | Linus | 🟡 Notable | ⚠️ Single seat |
| R17 | Module structure missing migrations/config/exceptions (6 directories) | Guido | 🟡 Notable | ⚠️ Single seat |

---

## Feng Ge's Strategic Rulings

### Priority 1: Must Fix Before Sending Email (otherwise self-destruct)

**1. Rewrite IP Terms (R1)**
Xuefeng and Guido unanimously rule: EU4Health Foreground IP defaults to joint consortium ownership. "DataWego retains core engine copyright" is legally invalid.
→ Switch to Background/Foreground boundary model, attach IP_BOUNDARY.md listing per-file ownership.

**2. Complete Rework Clause (R2)**
EUR-X/day blank is a legal audit bomb.
→ Three-tier rates (Architect/Senior/Junior), add approval process: written request → estimate person-days → mutual confirmation → start, set caps (single ≤15%, annual ≤30%).

**3. Fix Graph Computation Architecture (R3)**
Linus identified: NetworkX pure Python implementation collapses at 200+ nodes, violating 3s SLA.
→ Introduce Apache AGE (PostgreSQL native graph extension) at M4-M9. No extra container needed in Docker Compose.

**4. Reinforce Payment Structure (R4)**
Xuefeng's math: 30% advance barely covers 9 months of salary for 4 people. M9 payment tied to CHARITE = starvation risk.
→ Split M9 payment into two (M9 15% + M15 15%), or add clause: CHARITE delay >30 days → Epidata advances.

**5. WP3 Data Plan B (R5)**
Both Musk and Jobs identify: your plan has no Plan B when WP3 delivers PDF — this is not architecture risk, this is survival risk.
→ Add data extraction layer (even if manual curation), contractually require Epidata to guarantee structured delivery or fund extraction.

### Priority 2: Must Complete Before Contract Negotiation

**6. Schema Extension Mechanism (R6)**
If M3 sign-off fails, auto-extend to M5 with payment shift. Add clause: "Upstream changes post-M3 Schema → rework at tiered rate."

**7. Audit Log Hardening (R7)**
PostgreSQL RULE → TRIGGER. Linus and Guido dual-confirmed RULE is unreliable. Add: prev_hash cryptographic chain hashing.

**8. Rule Engine Refactor (R8)**
recommendation_rules add parent_rule_id + priority + rule_type enum. WP8 rules are trees, not flat lists.

**9. Code Skeleton First (R9)**
Guido is right: three documents contain zero Pydantic models, exception classes, or rule DSL. Before sending the email, produce a pytest-able skeleton project.

### Priority 3: Email Wording Political Fixes

**10. Wording Quad-Kill (R10)**
Four-seat cross-confirmed as political risk:
- "Apple Setup Assistant" → "concise three-step guided experience" (Jobs: QA culture doesn't buy Apple analogies)
- "strategic positioning and navigation system" → "compliance path mapping tool" (Musk: navigation = overpromise)
- SHAIPED "what to reuse vs rewrite" → "architectural alignment with SHAIPED, extending for SCAILED context" (Jobs: don't criticize the client's ex)
- "Schema must be signed by M3" → "both parties jointly confirm Schema baseline by M3" (Xuefeng: adversarial → collaborative)

---

## Final Ruling

The plan's skeleton is correct and the direction is right. But the six-seat audit exposed 12 critical/very-high risks across three categories. **The email in its current form must not be sent.**

Action Checklist:
1. 🔴 Rewrite IP terms (Background/Foreground boundary + IP_BOUNDARY.md)
2. 🔴 Complete rework clause (three-tier rates + approval process + caps)
3. 🔴 Fix graph computation plan (introduce Apache AGE replacing pure NetworkX)
4. 🔴 Restructure payments (split M9 or add advance clause)
5. 🔴 Add WP3 data Plan B (extraction layer + contract guarantee)
6. 🔴 Schema auto-extension + upstream change billing clause
7. 🟠 Audit log RULE→TRIGGER + cryptographic chain hash
8. 🟠 recommendation_rules add tree structure
9. 🟠 Build pytest-able code skeleton (Pydantic + exceptions + DSL)
10. 🟠 Rewrite email wording (4 fixes)

Final cut: Add soul line to email — *"Pathfinder isn't here to help you fill compliance forms. It makes compliance intuitive."*
