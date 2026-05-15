The relationship between the European Health Data Space (EHDS) and Health Data Access Bodies (HDABs) is foundational:

> EHDS is the EU-wide legal and operational framework.
> HDABs are the national operational authorities that implement and enforce part of that framework.

You can think of it like this:

| Layer | Role                              |
| ----- | --------------------------------- |
| EHDS  | EU-wide regulation + architecture |
| HDAB  | National implementation authority |

The SCAILED proposal explicitly treats HDABs as core actors inside the EHDS ecosystem. 

---

# 1. What is EHDS?

EHDS is:

* an EU regulation,
* a cross-border health data framework,
* enabling:

  * health data sharing,
  * secondary use of health data,
  * interoperability,
  * AI/research access,
  * secure processing.

It defines:

* governance rules,
* legal obligations,
* interoperability requirements,
* stakeholder roles,
* technical frameworks.

The proposal describes EHDS as:

* the secure framework enabling AI and biotech innovation across Europe. 

---

# 2. What is an HDAB?

HDAB = Health Data Access Body.

An HDAB is:

* a national authority (or delegated authority),
* designated by an EU Member State,
* responsible for controlling secondary access to health data under EHDS.

Examples in the proposal:

* FINDATA (Finland),
* HDH (France),
* LNDS (Luxembourg),
* HDA Belgium,
* etc. 

---

# 3. HDAB’s Main Responsibilities

Under EHDS, HDABs are responsible for:

| Responsibility                   | Meaning                 |
| -------------------------------- | ----------------------- |
| Reviewing access requests        | Approve/reject data use |
| Issuing permits                  | Legal authorization     |
| Ensuring GDPR compliance         | Privacy enforcement     |
| Managing secure environments     | SPE governance          |
| Auditing usage                   | Monitoring/revocation   |
| Coordinating cross-border access | EU interoperability     |
| Publishing metadata              | Dataset discoverability |

---

# 4. Simplified Relationship

```text
EHDS
 ├── Defines EU-wide rules
 ├── Defines architecture
 ├── Defines interoperability
 ├── Defines stakeholder roles
 │
 └── HDABs implement these rules nationally
        ├── Approve data access
        ├── Operate secure environments
        ├── Enforce compliance
        ├── Coordinate datasets
        └── Support secondary use
```

---

# 5. Operational Relationship

# EHDS = Framework

EHDS defines:

* WHAT is allowed,
* WHO can access,
* HOW access should work,
* technical/legal standards.

---

# HDAB = Operator / Gatekeeper

HDAB executes:

* actual approval workflows,
* data access decisions,
* secure processing,
* governance enforcement.

---

# 6. Example Workflow

Suppose:

* a biotech company wants cancer imaging data,
* to train an AI model.

---

## Step 1 — EHDS Defines Rules

EHDS defines:

* legal basis,
* allowed purposes,
* security requirements,
* interoperability standards.

---

## Step 2 — HDAB Executes Process

The HDAB:

* receives the request,
* evaluates compliance,
* approves/rejects,
* provisions secure access,
* monitors usage.

---

## Step 3 — AI Factory / SPE Used

If approved:

* processing occurs in:

  * Secure Processing Environment (SPE),
  * AI Factory,
  * federated infrastructure.

---

# 7. Why HDABs Matter So Much in SCAILED

The proposal repeatedly references HDABs because:

AI innovation under EHDS requires:

* lawful secondary use access,
* operational governance,
* secure processing,
* interoperability.

HDABs are the organizations enabling this.

---

# 8. Relationship to AI Factories

This is a key SCAILED concept.

The proposal tries to connect:

| Component  | Role                         |
| ---------- | ---------------------------- |
| EHDS       | legal/data framework         |
| HDAB       | access/governance authority  |
| AI Factory | compute infrastructure       |
| SPE        | secure execution environment |

So:

```text
EHDS
   ↓
HDAB approves access
   ↓
SPE / AI Factory processes data
   ↓
Biotech AI application developed
```

---

# 9. Relationship to Your Pathfinder Platform

Your platform essentially sits ABOVE these layers.

Pathfinder evaluates:

* whether an organization is EHDS-ready,
* whether an HDAB integration exists,
* whether AI Factory deployment is compliant,
* whether governance maturity is sufficient.

---

# 10. In Your Software Architecture

You should model:

| Entity       | Role                          |
| ------------ | ----------------------------- |
| EHDS         | Regulatory framework          |
| HDAB         | Operational authority         |
| SPE          | Secure processing environment |
| AI Factory   | Compute provider              |
| Dataset      | Governed asset                |
| Organization | Stakeholder                   |

---

# 11. Important Concept: EHDS Does NOT Centralize Data

Very important.

EHDS is NOT:

* one giant EU database.

Instead:

* data remains distributed,
* HDABs coordinate access,
* infrastructures federate metadata and workflows.

This is why:

* federation,
* interoperability,
* metadata catalogs,
* SPEs,
* federated learning

are so important in the proposal.

---

# 12. HDAB vs Data Holder

Another important distinction.

| Role        | Meaning               |
| ----------- | --------------------- |
| Data Holder | owns/provides dataset |
| HDAB        | governs access        |

Example:

* hospital owns data,
* HDAB approves access.

---

# 13. Technical Implication for Your Platform

Your Pathfinder system will probably need:

# A. HDAB Readiness Model

Evaluate:

* governance maturity,
* interoperability,
* SPE support,
* metadata readiness.

---

# B. EHDS Compliance Engine

Map:

* organizational state,
* legal obligations,
* access workflows.

---

# C. AI Factory + HDAB Integration Layer

Evaluate:

* whether AI deployment satisfies HDAB governance constraints.

---

# 14. Best Mental Model

The cleanest abstraction is:

| Layer      | Comparable To                       |
| ---------- | ----------------------------------- |
| EHDS       | Internet protocol / legal framework |
| HDAB       | National gateway/router             |
| AI Factory | Cloud compute provider              |
| SPE        | Secure execution sandbox            |
| Pathfinder | Operational intelligence platform   |

---

# 15. Extremely Important Insight for Your Project

Your platform is NOT just:

* an AI governance dashboard.

It is actually becoming:

> a coordination/orchestration layer between:

* EHDS governance,
* HDAB operational workflows,
* AI Factory compute systems,
* biotech AI innovation pipelines.
