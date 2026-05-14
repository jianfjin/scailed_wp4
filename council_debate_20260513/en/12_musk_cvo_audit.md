# SCAILED WP4 Pathfinder — Musk (CVO) First Principles Audit

**Audit Date**: 2026-05-14

---

## 1. "Pathfinder = Constrained Graph Search Engine" — What's Missing?

From first principles, Pathfinder is not a search engine. Search engines return information. Pathfinder needs to return executable sequences — do A, then B, then C, with branching logic.

You're building a compliance state machine wearing graph clothing. Core physics:
- States = regulatory configurations
- Edges = permitted transitions
- Constraints = EHDS/WP8 rules pruning illegal paths
- Output = ordered action list, not just "results"

Missing from definition:
- **Temporal logic**: Compliance isn't static. "Do step 1" has deadlines. Graph edges need time parameters.
- **Failure modes**: What happens when a step can't be completed? Need backtracking or alternative path generation.
- **Human-in-the-loop verification**: Users aren't machines. Need overrides, annotations, bookmarks. Your definition sounds like batch Dijkstra.

Verdict: You're underreporting interaction complexity and overreporting "search" abstraction. More honest definition: interactive verification regulatory path planner.

---

## 2. "Not Black-Box AI" — Is This the Right Positioning?

EU AI Act is in effect as of 2026. Any system influencing healthcare data or compliance decisions is under scrutiny. The EU doesn't hate AI — they hate unaccountable AI.

Your position: "We're not AI, we're transparent."

Risk: You're solving the wrong problem. AI Act classifies by risk level, not by whether something uses neural networks. A rule system determining compliance paths — whether it uses an LLM or hand-written JSON — is still high-risk under AI Act Article 6.

Shouting "not AI" creates two problems:
1. Comes off as overly defensive, like you're hiding something
2. Misses the right framing: **"Pathfinder is a deterministic, auditable decision support system, 100% traceable from input to output. Every recommendation is explainable through explicit rule chains. This exceeds AI Act transparency requirements."**

This isn't "not AI." This is better than AI. Own it.

Email wording fix:
> "Pathfinder is not a black-box AI system. It is a deterministic, rule-driven path planner where every recommendation traces back to explicit regulatory rules. This design exceeds EU AI Act transparency requirements by eliminating probabilistic reasoning entirely."

---

## 3. Does 36 Months Make Sense for "Dijkstra + Questionnaire"?

Disturbing. Do the math:

What's actually being built:
- PostgreSQL Schema: 5 tables
- Graph engine: Dijkstra/A* on DAG via Apache AGE
- API: FastAPI, 10-15 endpoints
- Frontend: Vue 3 questionnaire flow + path visualization
- Docker: single-container compose

This isn't a rocket. It's a CRUD app with graph algorithms.

**2-3 engineers can build the MVP in 6-8 weeks. Not months. Weeks.**

Your 36-month timeline:
- M1-M3: Schema freeze (designing 5 tables needs 3 months??)
- M4-M9: Core engine (Dijkstra needs 6 months?)
- M10-M15: API + frontend MVP (FastAPI + Vue needs 6 months?)

This is Parkinson's Law — work expands to fill available time.

Musk's approach:
1. Build MVP in 3 months, not 15. 3 engineers locked in a room. Schema week 1. Core engine weeks 2-4. API weeks 5-6. Frontend weeks 7-10. Polish weeks 11-12.
2. Remaining time is for **hardening** and **scaling**, not basic development. Real user testing. Break it. Fix it.
3. Ruthless parallelization. Schema design and frontend mockups can happen simultaneously.
4. Kill "M1-M3 Schema freeze." You don't need 3 months to freeze 5 tables. Freeze = don't change without negotiation — not = "spend 3 months thinking."

Real risk: Give a team 15 months to build an MVP, they'll take 15 months. Code won't be better — just older.

Recommendation: Compress build phases by 60%. Freed time goes to: real user testing, EHDS compliance verification, performance testing at actual graph scale.

---

## 4. DAG Constraint Forces Upstream Structured Data — Where's Plan B?

This is your biggest existential risk.

You wrote: "WP3 delivers PDF unstructured (very high risk)"
Then wrote: "Schema must be M1-M3 locked"

First principles: What happens to Pathfinder if WP3 delivers garbage?
Answer: It dies. Or you do 3 years of manual data entry. Both unacceptable.

What's missing:
1. **Data ingestion pipeline** with format detection — PDF? XML? Excel? CSV? Cell phone photo of handwritten note?
2. **Extraction layer** — even if just manual curation tooling. Who converts WP3 output to structured format? Epidata? DataWego? Subcontractor?
3. **Graceful degradation** — if WP3 data is incomplete, can Pathfinder run on partial graph? Can it flag "this path is provisional, pending WP3 delivery confirmation"?
4. **Mock→Real transition plan** — what's the cutover strategy? "Swap real data at M4" is fantasy. Real data breaks assumptions.

Specific audit finding: The risk register says "WP3 unstructured = very high risk" but your mitigation is… "Schema must be M1-M3 locked"? **That's not mitigation. That's prayer.**

Real mitigation:
- Contract: Epidata must guarantee structured WP3 delivery or fund extraction
- Technical: Include extraction tooling (even simple) in scope
- Operational: Budget data curation role M4-M9 to bridge WP3→Pathfinder
- Fallback: Pathfinder runs on "best available" data with confidence markers

**Without this, you're building a Ferrari and hoping someone paves the road.**

---

## 5. "Explainable Decision Navigation Tool" — Overpromising?

First principles: Can Pathfinder actually navigate? Or just suggest?

Navigation means:
- Real-time route correction
- Current position awareness
- Dynamic rerouting based on obstacles

Pathfinder does:
- Runs a questionnaire
- Runs one static graph search
- Returns a list of steps

That's not navigation. That's itinerary planning. The distinction matters.

GPS navigation knows where you are, sees congestion ahead, says "turn left now." Pathfinder is more like a Google Maps printout: "Here's the route. Good luck."

"Decision" navigation — who makes the decision? Pathfinder or the human?
- If Pathfinder decides → AI Act high-risk territory + liability hell
- If human decides → you're a decision support tool, not a navigator

Email fix:
> "Pathfinder is an interactive compliance path planner. It maps regulatory requirements to executable step sequences based on user input. Final decisions and execution remain with human operators. Pathfinder does not automate compliance — it structures complexity so humans can act with confidence."

This:
- Eliminates "navigation" overpromise
- Clarifies human-in-the-loop
- Sets expectations
- Guards against liability claims

---

## Summary: Five Key Audit Findings

| # | Issue | Severity | Recommendation |
|---|-------|----------|---------------|
| 1 | Definition missing temporal logic, failure fallback, human interaction | High | Redefine as "interactive verification compliance state machine" |
| 2 | "Not AI" positioning too defensive, misses compliance advantage | Medium | Reframe as "deterministic exceeds AI Act transparency requirements" |
| 3 | 36-month timeline has bureaucratic Parkinson's | Very High | Compress MVP to 3-4 months, remaining time for field iteration |
| 4 | WP3 structured dependency has no Plan B | Very High | Add data extraction layer, contract guarantee, degradation strategy |
| 5 | "Navigation" wording overpromises | High | Change to "interactive compliance path planner" |

Bottom line: You're building a rule-driven graph query system with a Vue frontend. The engineering is straightforward. What's hard is: data ingestion (WP3 reality vs your Schema dreams), regulatory volatility (EHDS will change), stakeholder alignment (Epidata, CHARITE, EU auditors all want different things).

Your documents spend too much time on elegant architecture and too little on "what happens when reality breaks the architecture."
