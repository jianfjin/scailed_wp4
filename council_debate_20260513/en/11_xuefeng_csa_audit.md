# SCAILED WP4 Pathfinder — Xuefeng (CSA) Realist Audit

**Audit Date**: 2026-05-14
**Scope**: 00_council_resolution.md + 09_expanded_analysis.md + email_to_lu_zhao_v1.md

---

## Cut 1: Cash Flow — 30% Advance Is Paper in EU4Health Projects

30% advance sounds solid, but you're the subcontractor. M1 to M9 is nine months. How long does 30% last?

- 30% advance = assuming €1M total, that's €300K
- M1-M9 = 9 months to complete Schema freeze + core engine
- Minimum team: 2 full-stack + 1 PM + 1 QA = 4 people
- Netherlands/Germany market: conservatively €8K/person/month
- 4 people × €8K × 9 months = €288K
- €300K barely covers salaries. Servers, licenses, travel, overhead?

Core problem: M9's 30% payment is tied to Epidata receiving funds from CHARITE.
- If CHARITE delays? EU project payment delays of 3-6 months are routine, not exceptional.
- If CHARITE and Epidata have disputes, audit failures, report revisions — M9 payment doesn't arrive. DataWego starves.
- M9 to M20: 11 months on just 30% to carry V1 development + delivery + D4.1 report.

**Risk Score: Very High.**

Recommendation: Split M9's 30% into two payments — M9 15% (Epidata payment received) + M15 15% (not tied to CHARITE). Or add: "If CHARITE payment delayed >30 days, Epidata advances the milestone amount."

---

## Cut 2: Requirements Lock — Low-Fidelity Prototype with QA/QC Culture?

Epidata's background? They do QA/QC. You're giving a low-fi prototype to QA-culture people to sign off?

What Epidata's QA Director sees in a low-fi prototype:
- "Interface isn't detailed enough" → "You haven't thought through interactions"
- "No error states shown" → "You haven't considered edge cases"
- "No loading states" → "Your performance is problematic"
- "Why is this button blue not green" → "Doesn't match our brand guidelines"

Two problems:
1. "Schema must be signed at M3" — who signs? PM signing ≠ QA signing ≠ legal signing
2. After sign-off, if someone raises new requirements — is that "scope change" or "you didn't understand the requirements"?

**Recommendation**: Low-fi prototype is insufficient. By M2-M3, deliver an interactive high-fidelity prototype covering at least 3 complete user flows, including error handling and empty states.

---

## Cut 3: Upstream Dependencies — "Skeleton First" Strategy's Blind Spot

Problem A: What if M3 Schema isn't signed?
In EU projects, Schema not getting signed is extremely probable. Because the defining characteristic of EU projects is — nobody is accountable for their own delivery timeline.

Problem B: Mock data fidelity — who validates it?
If mock data doesn't cover real data complexity, the skeleton works with mocks but collapses with real data.

Problem C: "Written confirmation" mechanism with upstream
What exactly is being locked? Schema names and types? Or specific field definitions, enum values, constraints, version numbers?

**Recommendations**:
- M1 Kick-off: require each upstream WP to provide sample data package (minimum 5 real records) as contract attachment
- M3 not signed → Phase 1 auto-extends to M5, payment milestones shift accordingly
- Contract clause: "Upstream changes to Schema post-M3 → rework billed at tiered rates"

---

## Cut 4: Acceptance Criteria — Quantified ≠ Objective

"WP8 known rules 100% match" — who defines "known rules"?
- Rules written in WP8 deliverable? Or rules WP8 lead mentioned verbally?
- If docs say 50 but actual need is 90 — which standard applies?

"Deployment docs: one hour to complete" — whose one hour?
- Developer's one hour? Or QA person who's never touched Docker's one hour?
- Fresh server or server with pre-existing Python environment?
- Smooth-sailing hour or port-conflict hour?

"Code coverage ≥80%" — what kind of coverage?
- Line? Branch? Condition?
- Overall or per-module?

"Frontend ≤3 seconds" — under what conditions?
- How many data records? 100? 10,000?
- 3 users or 30 concurrent?

**Recommendation**: Contract attachment: "Acceptance Test Scenario Specification" documenting test environment, data volume, concurrency, measurement tools.

---

## Cut 5: Rework Clause EUR-X/Day — Audit Bomb

1. Day rate opaque: architect and junior dev same rate?
2. Trigger conditions incomplete: rework caused by DataWego's own misunderstanding — excluded?
3. Approval process missing: who determines "this change counts as rework"?
4. No cap clause: theoretically Epidata can request 500 person-days and then say "budget's gone"

**Recommendations**:
- Three-tier rates: Architect €800-1200/day, Senior €600-800/day, Junior €400-600/day
- Process: Written change request → DataWego estimates person-days → mutual written confirmation → start
- Caps: Single change ≤15% of contract total, annual ≤30%
- Exclusion: "DataWego failed to implement per confirmed Schema" not covered here

---

## Cut 6: Intellectual Property — "Core Engine Copyright" Violates EU4Health

EU4Health IP framework has two principles:
1. Project results belong to the consortium jointly (Joint Ownership)
2. Only Background IP can be designated as developer's sole property

You say "DataWego retains core engine copyright" — but the core engine is developed during SCAILED with EU4Health funds. This is Foreground IP, defaulting to joint consortium ownership.

Unless you can prove:
- Core engine had a pre-existing version before project start (Pre-existing Background IP)
- Project development was only "minor improvements" not "substantial development"

**Recommendation**: Change to "DataWego's independently developed pre-existing graph search algorithm framework (defined in Attachment A) as Background IP belongs to DataWego; customizations developed during SCAILED for EU4Health requirements are jointly owned by the consortium, with DataWego receiving right of first negotiation for commercialization outside the project."

---

## Cut 7: Email Wording Political Risk

This email, after Lu Zhao reads it, may be forwarded to: Epidata legal, QA Director, project coordinator, CFO, even CHARITE people.

"Use mock data to build system skeleton... Schema must be signed at M3" — Epidata's PM reads: "DataWego is saying if we can't deliver Schema by M3, it's our fault."

Tone is too hard. In EU projects, everyone's family.

**Suggested rewording**: "To reduce the risk of WP2/WP3/WP8 delivery timeline uncertainty on project progress, we recommend parallel progress during M1-M3 — DataWego builds system skeleton with sample data while each WP advances Schema discussions. Both parties jointly confirm a Schema baseline before M3. Subsequent changes go through the change management process."

---

## Audit Findings Summary

| # | Risk | Severity | Action |
|---|------|----------|--------|
| 1 | M9 payment tied to CHARITE receipt | Very High | Split M9 payment or add CHARITE delay advance clause |
| 2 | Low-fi prototype insufficient for QA culture | High | Upgrade to interactive high-fi prototype, 3+ complete flows |
| 3 | M3 Schema unsigned, no auto-extension | High | Add auto-extension clause, payment shift linked |
| 4 | EUR-X/day blank, no role-based rate classification | Very High | Minimum three rates, add approval process and caps |
| 5 | "Core engine copyright to DataWego" violates EU4Health | Very High | Switch to Background/Foreground boundary model |
| 6 | Acceptance criteria missing test condition specs | High | Supplement "Acceptance Test Scenario Specification" attachment |
| 7 | Email wording too adversarial | Medium | Rewrite in collaborative "joint baseline" tone |
