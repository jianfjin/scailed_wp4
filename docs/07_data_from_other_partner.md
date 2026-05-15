For the Pathfinder platform to become a real operational system instead of a conceptual EU-project dashboard, you need **structured, machine-readable data** from partners.

The most important thing is:

> Do NOT accept only PDFs, PowerPoints, meeting notes, and Word documents.

If partners only give narrative documents, you will spend enormous effort manually converting policy text into usable software logic.

You should request:

* JSON,
* CSV,
* YAML,
* API schemas,
* ontology tables,
* BPMN workflows,
* OpenAPI specs,
* graph relationships,
* KPI matrices.

Below is the realistic data contract you should establish with each partner group.

---

# 1. From SCIENSANO (WP3 Strategic Roadmap)

SCIENSANO provides:

* roadmap,
* landscape analysis,
* maturity dimensions,
* barriers/enablers. 

---

# Data You Need

## A. Stakeholder Taxonomy

### Format

CSV / JSON

### Example

```json
{
  "stakeholder_type": "AI_FACTORY",
  "description": "Provides secure AI compute infrastructure",
  "capabilities": [
    "GPU_CLUSTER",
    "FEDERATED_LEARNING",
    "SPE_SUPPORT"
  ]
}
```

---

# B. Maturity Model Definitions

### Format

JSON / YAML

### Example

```json
{
  "dimension": "EHDS_COMPLIANCE",
  "levels": [
    {
      "level": 1,
      "name": "Initial"
    },
    {
      "level": 2,
      "name": "Managed"
    }
  ]
}
```

---

# C. Roadmap Milestones

### Format

CSV / JSON

### Example

| stakeholder | current_state | target_state    | dependency     |
| ----------- | ------------- | --------------- | -------------- |
| AI Factory  | local GPU     | EHDS integrated | SPE deployment |

---

# D. KPI Definitions

### Format

CSV / JSON

### Example

```json
{
  "kpi_id": "KPI_001",
  "name": "Federated Learning Capability",
  "measurement": "boolean",
  "threshold": true
}
```

---

# 2. From IACS (WP2 Stakeholder Forum)

You need operational user modeling.

---

# Data Needed

## A. Stakeholder Personas

### Format

JSON

### Example

```json
{
  "persona": "Biotech SME",
  "pain_points": [
    "Regulatory uncertainty",
    "No AI infrastructure"
  ],
  "objectives": [
    "Train AI model",
    "Access EHDS data"
  ]
}
```

---

# B. User Journeys

### Format

BPMN / Mermaid / JSON workflow

### Example

```yaml
steps:
  - request_data_access
  - obtain_HDAB_approval
  - deploy_model
  - validate_AI
```

---

# C. Feedback Dataset

### Format

CSV

| stakeholder | issue          | severity | recommendation |
| ----------- | -------------- | -------- | -------------- |
| SME         | unclear AI Act | high     | guidance tool  |

---

# 3. From ELIXIR / WP5 Infrastructure Partners

This is one of the most important data sources.

---

# Data Needed

## A. EHDS Metadata Schemas

### Format

JSON Schema / OpenAPI / RDF

Examples:

* HealthDCAT-AP,
* dataset metadata,
* access workflows.

---

# B. Infrastructure Capability Matrix

### Format

CSV / JSON

| infrastructure | supports_federation | supports_synthetic_data | supports_SPE |
| -------------- | ------------------- | ----------------------- | ------------ |
| EUCAIM         | yes                 | partial                 | yes          |

---

# C. Data Access Workflow

### Format

BPMN / Mermaid / YAML

Needed for:

* navigation engine,
* recommendation system.

---

# D. API Specifications

### Format

OpenAPI / Swagger

You should ask for:

* endpoints,
* authentication methods,
* metadata APIs,
* dataset query APIs.

---

# E. Interoperability Standards

### Format

Machine-readable tables

Examples:

* FHIR profiles,
* OMOP mappings,
* SNOMED mappings.

---

# 4. From AI Factories (WP7)

You need operational compute information.

---

# Data Needed

## A. Service Catalog

### Format

JSON

```json
{
  "service": "Federated Learning",
  "gpu_required": true,
  "supports_ehds": true
}
```

---

# B. Compute Resource Metadata

### Format

CSV / JSON

| cluster | GPU  | region | secure_processing |
| ------- | ---- | ------ | ----------------- |
| LUMI    | H100 | FI     | yes               |

---

# C. Deployment Constraints

### Format

YAML / JSON

```yaml
constraints:
  - GDPR
  - encrypted_storage
  - EU_region_only
```

---

# D. AI Workflow Definitions

### Format

BPMN / YAML

Needed for:

* automated guidance generation.

---

# 5. From WP8 Regulatory / Legal Partners

This becomes your rules engine.

---

# Data Needed

## A. Regulatory Decision Trees

### Format

JSON / DMN

Example:

```json
{
  "if": {
    "uses_personal_health_data": true
  },
  "then": [
    "GDPR_APPLIES",
    "EHDS_SECONDARY_USE_REQUIRED"
  ]
}
```

---

# B. Compliance Checklists

### Format

CSV / JSON

| regulation | requirement | mandatory |
| ---------- | ----------- | --------- |
| GDPR       | DPIA        | yes       |

---

# C. Legal Templates

### Format

DOCX + structured metadata

Needed for:

* automated document generation.

---

# D. Regulatory Ontology

### Format

RDF / OWL / JSON-LD

This is extremely valuable for:

* knowledge graph integration.

---

# 6. From WP6 Use Case Teams

These are your validation datasets.

---

# Data Needed

## A. Use Case Descriptions

### Format

JSON

```json
{
  "use_case": "Federated Learning",
  "datasets": [
    "genomics",
    "imaging"
  ],
  "requirements": [
    "SPE",
    "GPU"
  ]
}
```

---

# B. Evaluation Results

### Format

CSV / JSON

| use_case | success | blocker     | recommendation     |
| -------- | ------- | ----------- | ------------------ |
| FL       | partial | legal delay | improve governance |

---

# C. Architecture Diagrams

### Format

Mermaid / DrawIO / BPMN

---

# D. KPIs / Metrics

### Format

CSV / Time-series JSON

Examples:

* training time,
* approval duration,
* interoperability success rate.

---

# 7. Data Formats You Should Standardize Across Consortium

You should define consortium-wide standards early.

---

# Recommended Formats

| Data Type       | Preferred Format |
| --------------- | ---------------- |
| APIs            | OpenAPI          |
| Rules           | JSON / DMN       |
| Metadata        | JSON Schema      |
| Ontologies      | RDF / OWL        |
| Graph relations | CSV / Cypher     |
| Workflows       | BPMN / Mermaid   |
| KPIs            | CSV / JSON       |
| Reports         | Markdown + JSON  |
| Taxonomies      | CSV              |
| Questionnaires  | JSON             |

---

# 8. What NOT to Accept

Avoid relying only on:

* PDFs,
* PowerPoints,
* Word docs,
* screenshots,
* narrative descriptions.

These are useful for humans,
but terrible for software systems.

---

# 9. Data Architecture You Should Create

You should probably create:

# Pathfinder Canonical Data Model

Core entities:

| Entity         | Examples           |
| -------------- | ------------------ |
| Stakeholder    | AI Factory         |
| Infrastructure | EUCAIM             |
| Capability     | Federated Learning |
| Regulation     | EHDS               |
| Workflow       | Data Access        |
| KPI            | Compliance Score   |
| Recommendation | Deploy SPE         |
| Use Case       | Synthetic Data     |

---

# 10. Most Valuable Thing You Can Build Early

One of the highest leverage things you can do is:

# Define a unified consortium schema

Example:

* `/schemas/stakeholder.schema.json`
* `/schemas/usecase.schema.json`
* `/schemas/regulation.schema.json`

This will:

* massively reduce chaos later,
* standardize integrations,
* simplify graph modeling,
* simplify AI/RAG pipelines,
* simplify frontend development.

Without this,
the project can easily become:

* 50 incompatible Excel files + PDFs.
