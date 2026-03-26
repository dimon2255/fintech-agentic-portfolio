# Architecture — KYC/AML Compliance Platform

## System Overview

```mermaid
graph TD
    A[KYC Application] --> B[Supervisor]
    B -->|Route 1| C[Document Intake Agent]
    B -->|Route 2| D[Identity Verification Agent]
    B -->|Route 3| E[Sanctions Screening Agent]
    B -->|Route 4| F[Risk Assessment Agent]
    B -->|Escalate| G[Human Review]
    B -->|Complete| H[Final Decision]

    C --> B
    D --> B
    E --> B
    F --> B
    G --> H
    H --> I[Compliance Decision]

    style B fill:#4ecdc4,stroke:#333,color:#000
    style G fill:#ffd43b,stroke:#333,color:#000
    style H fill:#51cf66,stroke:#333,color:#000
    style I fill:#339af0,stroke:#333,color:#fff
```

## Supervisor State Machine

```mermaid
stateDiagram-v2
    [*] --> Supervisor
    Supervisor --> DocumentIntake : First step
    DocumentIntake --> Supervisor : Done
    Supervisor --> IdentityVerification : Docs OK
    Supervisor --> HumanReview : Doc quality < 0.3
    IdentityVerification --> Supervisor : Done
    Supervisor --> SanctionsScreening : Identity confirmed
    Supervisor --> HumanReview : Identity NOT confirmed
    Supervisor --> RiskAssessment : Skip sanctions (low-risk domestic)
    SanctionsScreening --> Supervisor : Done
    Supervisor --> HumanReview : Strong sanctions hit (> 0.8)
    Supervisor --> RiskAssessment : Sanctions clear
    RiskAssessment --> Supervisor : Done
    Supervisor --> FinalDecision : All steps complete
    Supervisor --> FinalDecision : Risk = PROHIBITED (auto-reject)
    HumanReview --> FinalDecision : Reviewed
    FinalDecision --> [*]
```

## Sequence Diagram

```mermaid
sequenceDiagram
    participant App as Application
    participant S as Supervisor
    participant D as Doc Intake
    participant I as Identity
    participant Sc as Sanctions
    participant R as Risk
    participant F as Final Decision

    App->>S: New KYC application
    S->>S: Check checklist → route to doc_intake
    S->>D: Process documents
    D-->>D: extract + classify + validate (parallel)
    D->>S: DocumentIntakeResult
    S->>S: Check quality → route to identity
    S->>I: Verify identity
    I-->>I: name + address + DOB + PEP (parallel)
    I->>S: IdentityVerificationResult

    alt Low-risk domestic individual
        S->>S: Skip sanctions (checklist: skipped)
        S->>R: Assess risk
    else Standard flow
        S->>Sc: Screen sanctions
        Sc-->>Sc: OFAC + EU + UN + media (parallel)
        Sc->>S: SanctionsScreeningResult
        S->>R: Assess risk
    end

    R-->>R: country + industry + pattern + overall
    R->>S: RiskAssessmentResult
    S->>F: All steps complete → final decision
    F->>App: ComplianceDecision
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Graph topology** | Supervisor hub-and-spoke | Compliance workflows have dependencies between stages; fan-out is wrong here |
| **Routing mechanism** | `add_conditional_edges` | LangGraph's native conditional routing — cleaner than manual state checks |
| **State management** | State isolation per agent | Each agent writes to its own key (pattern from P2, prevents merge conflicts) |
| **Skip logic** | Supervisor-driven | Low-risk domestic individuals skip sanctions — reduces cost by ~15-25% |
| **Escalation** | 3 triggers → human_review | Document failure, identity failure, strong sanctions match |
| **Checklist tracking** | Pydantic model in state | Immutable audit of which steps ran, which were skipped, and when |
| **LLM fallback** | `_has_api_key()` check | Zero-cost development with deterministic mocks; real LLM when key is present |

## Data Flow

```
KYCApplication (input)
    │
    ├── Document Intake: 3 tools × N documents (parallel per-doc, parallel per-tool)
    │   └── DocumentIntakeResult → state.document_intake_result
    │
    ├── Identity Verification: 4 tools (parallel)
    │   └── IdentityVerificationResult → state.identity_verification_result
    │
    ├── Sanctions Screening: 4 tools (parallel)  [may be SKIPPED]
    │   └── SanctionsScreeningResult → state.sanctions_screening_result
    │
    ├── Risk Assessment: 4 tools (3 parallel + 1 sequential aggregation)
    │   └── RiskAssessmentResult → state.risk_assessment_result
    │
    └── Final Decision: aggregates all results
        └── ComplianceDecision (output with full audit trail)
```

## Portfolio Progression

| Dimension | P1: Risk Classifier | P2: Fraud Swarm | P3: KYC/AML Platform |
|-----------|-------------------|-----------------|---------------------|
| Topology | Linear (2 nodes) | Fan-out/fan-in (5 nodes) | **Supervisor hub-and-spoke (7 nodes)** |
| Routing | Static | Static parallel | **Dynamic conditional** |
| LangGraph API | `add_edge` | `add_edge` fan-out | **`add_conditional_edges`** |
| Agents | 1 | 3 specialists + adjudicator | **4 specialists + supervisor** |
| Tools | 3 | 5 | **15** |
| Skip logic | None | None | **Supervisor-driven** |
| Escalation | None | Mentioned | **Implemented (3 triggers)** |
| Domain | Transaction scoring | Fraud detection | **KYC/AML compliance** |
