# SCAILED / EPIDATA Pathfinder Platform — Architecture Diagrams

## 1. Overall SCAILED System Architecture

```mermaid
flowchart TB

    subgraph Stakeholders
        BIO[Biotech Companies]
        HDAB[Health Data Access Bodies]
        AIF[AI Factories]
        RI[Research Infrastructures]
        HOSP[Hospitals / Healthcare]
        REG[Regulators]
        PAT[Patient Organisations]
    end

    subgraph WP2[WP2 Stakeholder Forum]
        FORUM[Stakeholder Engagement Platform]
    end

    subgraph WP3[WP3 Strategic Roadmap]
        ROADMAP[Strategic Roadmap]
        LANDSCAPE[Landscape Analysis]
    end

    subgraph WP4[WP4 Pathfinder System - EPIDATA]
        PATHFINDER[Pathfinder Platform]
        SCORE[Readiness Scoring Engine]
        NAV[Navigation / Recommendation Engine]
        MONITOR[Monitoring & Evaluation]
        DASH[Operational Dashboards]
    end

    subgraph WP5[WP5 EHDS Infrastructure Integration]
        EHDS[EHDS Integration]
        SPE[Secure Processing Environments]
        GDI[Genomics Infrastructure]
        EUCAIM[Cancer Imaging Infrastructure]
        EBRAINS[Brain Infrastructure]
    end

    subgraph WP6[WP6 AI Use Cases]
        UC1[Synthetic Data]
        UC2[Federated Learning]
        UC3[Polygenic Risk Scores]
        UC4[Clinical Trial AI]
    end

    subgraph WP7[WP7 AI Factories]
        HPC[HPC Infrastructure]
        GPU[GPU Clusters]
        MODEL[AI Model Deployment]
        SECURE[Secure AI Processing]
    end

    subgraph WP8[WP8 Regulatory & Ethics]
        GDPR[GDPR]
        EHDSREG[EHDS Regulation]
        AIACT[AI Act]
        MDR[MDR/IVDR]
    end

    Stakeholders --> FORUM
    FORUM --> ROADMAP
    LANDSCAPE --> PATHFINDER
    ROADMAP --> PATHFINDER

    PATHFINDER --> SCORE
    PATHFINDER --> NAV
    PATHFINDER --> MONITOR
    PATHFINDER --> DASH

    EHDS --> PATHFINDER
    SPE --> PATHFINDER
    GDI --> PATHFINDER
    EUCAIM --> PATHFINDER
    EBRAINS --> PATHFINDER

    UC1 --> PATHFINDER
    UC2 --> PATHFINDER
    UC3 --> PATHFINDER
    UC4 --> PATHFINDER

    HPC --> PATHFINDER
    GPU --> PATHFINDER
    MODEL --> PATHFINDER
    SECURE --> PATHFINDER

    GDPR --> PATHFINDER
    EHDSREG --> PATHFINDER
    AIACT --> PATHFINDER
    MDR --> PATHFINDER
```

---

# 2. EPIDATA Pathfinder Platform Architecture

```mermaid
flowchart LR

    subgraph Frontend
        WEB[React Web Portal]
        ADMIN[Admin Dashboard]
        REPORTS[Report UI]
    end

    subgraph API[FastAPI Backend]
        AUTH[Authentication]
        ORG[Organisation Management]
        QUESTION[Questionnaire Engine]
        SCORE[Scoring Engine]
        RECOMMEND[Recommendation Engine]
        KPI[KPI Monitoring]
        EXPORT[PDF / DOCX Export]
    end

    subgraph AI
        RAG[RAG Engine]
        LLM[LLM Copilot]
        RULES[Regulatory Rules Engine]
        GRAPH[Graph Reasoning]
    end

    subgraph Data
        POSTGRES[(PostgreSQL)]
        NEO4J[(Neo4j)]
        VECTOR[(pgvector)]
        REDIS[(Redis)]
    end

    subgraph External
        EHDSAPI[EHDS APIs]
        AIFACTORY[AI Factories]
        HDAB[HDAB Services]
        REGDB[Regulatory Documents]
    end

    WEB --> API
    ADMIN --> API
    REPORTS --> API

    API --> AI
    API --> Data

    RAG --> VECTOR
    GRAPH --> NEO4J
    RULES --> POSTGRES

    API --> EHDSAPI
    API --> AIFACTORY
    API --> HDAB
    API --> REGDB
```

---

# 3. Pathfinder Readiness Evaluation Workflow

```mermaid
sequenceDiagram

    participant User
    participant Portal
    participant Scoring
    participant KnowledgeGraph
    participant RegulatoryEngine
    participant AI
    participant Report

    User->>Portal: Submit organisation profile
    User->>Portal: Complete assessment questionnaire

    Portal->>Scoring: Calculate maturity scores

    Scoring->>KnowledgeGraph: Query dependencies & requirements
    KnowledgeGraph-->>Scoring: Infrastructure relationships

    Scoring->>RegulatoryEngine: Check EHDS/GDPR/AI Act compliance
    RegulatoryEngine-->>Scoring: Compliance gaps

    Scoring->>AI: Generate recommendations
    AI-->>Scoring: Suggested roadmap actions

    Scoring->>Report: Build readiness report
    Report-->>User: Dashboard + PDF report
```

---

# 4. EHDS Knowledge Graph Architecture

```mermaid
flowchart TB

    subgraph Entities
        COMPANY[Biotech Company]
        AIFACTORY[AI Factory]
        HDAB[HDAB]
        SPE[Secure Processing Environment]
        DATASET[Health Dataset]
        REGULATION[Regulation]
        USECASE[Use Case]
        INFRA[Research Infrastructure]
    end

    COMPANY -->|uses| AIFACTORY
    COMPANY -->|requests access from| HDAB

    HDAB -->|provides| SPE
    SPE -->|hosts| DATASET

    USECASE -->|requires| DATASET
    USECASE -->|runs on| AIFACTORY

    REGULATION -->|governs| HDAB
    REGULATION -->|governs| AIFACTORY
    REGULATION -->|governs| USECASE

    INFRA -->|integrates with| EHDS[EHDS]
    INFRA -->|publishes metadata to| HDAB
```

---

# 5. AI Factory Integration Architecture

```mermaid
flowchart LR

    subgraph Users
        SME[Biotech SMEs]
        STARTUP[AI Startups]
        RESEARCH[Researchers]
    end

    subgraph Pathfinder
        READY[Readiness Evaluation]
        GUIDE[Deployment Guidance]
        GOVERN[Governance Validation]
    end

    subgraph AI_Factory
        GPU[GPU Cluster]
        TRAIN[Model Training]
        INFER[Inference Services]
        FED[Federated Learning]
        SYNTH[Synthetic Data]
    end

    subgraph EHDS
        HDAB[HDAB]
        SPE[SPE]
        META[Metadata Catalogue]
    end

    SME --> READY
    STARTUP --> READY
    RESEARCH --> READY

    READY --> GUIDE
    GUIDE --> GOVERN

    GOVERN --> GPU
    GOVERN --> TRAIN
    GOVERN --> INFER
    GOVERN --> FED
    GOVERN --> SYNTH

    AI_Factory --> SPE
    SPE --> HDAB
    HDAB --> META
```

---

# 6. Suggested Cloud-Native Deployment Architecture

```mermaid
flowchart TB

    subgraph Internet
        USERS[Users]
    end

    subgraph Azure_or_EU_Cloud

        subgraph Gateway
            CDN[Cloudflare / CDN]
            LB[Load Balancer]
            API[API Gateway]
        end

        subgraph Kubernetes
            FRONTEND[React Frontend]
            BACKEND[FastAPI Services]
            WORKER[Async Workers]
            AI[AI Services]
        end

        subgraph Databases
            PG[(PostgreSQL)]
            NEO[(Neo4j)]
            VECTOR[(pgvector)]
            CACHE[(Redis)]
        end

        subgraph Storage
            DOCS[Document Storage]
            AUDIT[Audit Logs]
            MODELS[AI Models]
        end

        subgraph Security
            IAM[Keycloak / Azure AD]
            SIEM[Security Monitoring]
            VAULT[Secrets Vault]
        end

    end

    USERS --> CDN
    CDN --> LB
    LB --> API

    API --> FRONTEND
    API --> BACKEND

    BACKEND --> WORKER
    BACKEND --> AI

    BACKEND --> PG
    BACKEND --> NEO
    BACKEND --> VECTOR
    BACKEND --> CACHE

    BACKEND --> DOCS
    BACKEND --> AUDIT
    AI --> MODELS

    IAM --> BACKEND
    SIEM --> Kubernetes
    VAULT --> Kubernetes
```

