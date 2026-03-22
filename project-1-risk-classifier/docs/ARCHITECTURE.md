# Architecture: Transaction Risk Classifier

## System Overview

```mermaid
graph TD
    TXN[Incoming Transaction] --> GS[Gather Signals Node]

    GS --> |async| VC[Velocity Check]
    GS --> |async| GL[Geo Lookup]
    GS --> |async| DF[Device Fingerprint]

    VC --> AR[Assess Risk Node]
    GL --> AR
    DF --> AR

    AR --> |structured output| RA[Risk Assessment]

    RA --> |low risk| APPROVE[Auto-Approve]
    RA --> |medium risk| REVIEW[Human Review Queue]
    RA --> |high/critical| DECLINE[Auto-Decline]

    style GS fill:#4a9eff,color:#fff
    style AR fill:#ff6b6b,color:#fff
    style RA fill:#51cf66,color:#fff
```

## LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> GatherSignals
    GatherSignals --> AssessRisk: tool_results populated
    AssessRisk --> [*]: risk_assessment produced
```

The graph has two nodes with a simple linear flow. This intentional simplicity is the foundation — Project 2 expands this into a multi-agent graph with branching, debate, and escalation paths.

## Sequence Diagram: Agent Communication

```mermaid
sequenceDiagram
    participant C as Client
    participant G as GatherSignals Node
    participant V as Velocity Tool
    participant L as Geo Lookup Tool
    participant D as Device FP Tool
    participant A as AssessRisk Node
    participant LLM as LLM Provider

    C->>G: Transaction

    par Parallel Tool Execution
        G->>V: check_velocity(txn)
        G->>L: lookup_geo(txn)
        G->>D: fingerprint_device(txn)
        V-->>G: VelocityResult
        L-->>G: GeoResult
        D-->>G: DeviceFingerprintResult
    end

    G->>A: State + ToolResults
    A->>LLM: System prompt + Transaction + Tool results
    LLM-->>A: Structured reasoning + assessment
    A->>A: Parse & validate via Pydantic
    A-->>C: RiskAssessment (explainable)
```

## Data Flow

```
Transaction (Pydantic)
    │
    ├── customer_id, amount, merchant ──▶ VelocityCheck ──▶ VelocityResult
    ├── ip_address, billing_country ────▶ GeoLookup ─────▶ GeoResult
    └── device_id ─────────────────────▶ DeviceFP ──────▶ DeviceFPResult
                                                              │
                                         All 3 results ◀─────┘
                                              │
                                              ▼
                                     LLM Reasoning Engine
                                              │
                                              ▼
                                     RiskAssessment
                                     ├── risk_level (enum)
                                     ├── confidence (float)
                                     ├── reasoning_chain[] (explainable)
                                     ├── recommended_action
                                     ├── summary (human-readable)
                                     └── tool_results (raw data)
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration | LangGraph | Explicit state, checkpointing, production-ready |
| Parallelism | asyncio.gather | 3x faster tool execution, critical for real-time |
| Data validation | Pydantic v2 | Type safety, schema enforcement, serialization |
| LLM abstraction | LangChain providers | Swap OpenAI/Anthropic without code changes |
| Output format | Structured JSON | Machine-parseable + human-readable |
