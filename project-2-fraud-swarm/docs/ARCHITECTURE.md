# Architecture: Fraud Detection Swarm

## System Overview

```mermaid
graph TD
    TXN[Incoming Transaction] --> GAS[Gather All Signals]

    GAS --> |async| VC[Velocity Check]
    GAS --> |async| GL[Geo Lookup]
    GAS --> |async| DF[Device Fingerprint]
    GAS --> |async| IC[Identity Check]
    GAS --> |async| BA[Behavioral Analysis]

    VC --> VA[Velocity Agent]
    GL --> VA
    GL --> IA[Identity Agent]
    DF --> IA
    IC --> IA
    BA --> BHA[Behavioral Agent]

    VA --> |verdict| ADJ[Adjudicator]
    IA --> |verdict| ADJ
    BHA --> |verdict| ADJ

    ADJ --> |synthesized| SA[SwarmAssessment]

    SA --> |low risk| APPROVE[Auto-Approve]
    SA --> |medium risk| REVIEW[Human Review Queue]
    SA --> |high/critical| DECLINE[Auto-Decline]

    style GAS fill:#4a9eff,color:#fff
    style VA fill:#e67700,color:#fff
    style IA fill:#7950f2,color:#fff
    style BHA fill:#20c997,color:#fff
    style ADJ fill:#ff6b6b,color:#fff
    style SA fill:#51cf66,color:#fff
```

## LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> GatherAllSignals
    GatherAllSignals --> VelocityAgent
    GatherAllSignals --> IdentityAgent
    GatherAllSignals --> BehavioralAgent
    VelocityAgent --> Adjudicator
    IdentityAgent --> Adjudicator
    BehavioralAgent --> Adjudicator
    Adjudicator --> [*]
```

The graph uses LangGraph's native fan-out edges. When `gather_all_signals` completes, all three specialist nodes execute in parallel. The adjudicator fires only after all three complete (fan-in). This is the key architectural difference from Project 1's linear two-node graph.

## Sequence Diagram: Multi-Agent Communication

```mermaid
sequenceDiagram
    participant C as Client
    participant G as GatherAllSignals
    participant V as Velocity Tool
    participant L as Geo Tool
    participant D as Device Tool
    participant I as Identity Tool
    participant B as Behavioral Tool
    participant VA as Velocity Agent
    participant IA as Identity Agent
    participant BA as Behavioral Agent
    participant ADJ as Adjudicator
    participant LLM as LLM Provider

    C->>G: Transaction

    par 5 Tools in Parallel
        G->>V: check_velocity(txn)
        G->>L: lookup_geo(txn)
        G->>D: fingerprint_device(txn)
        G->>I: check_identity(txn)
        G->>B: analyze_behavior(txn)
        V-->>G: VelocityResult
        L-->>G: GeoResult
        D-->>G: DeviceFPResult
        I-->>G: IdentitySignals
        B-->>G: BehavioralSignals
    end

    par 3 Specialists in Parallel
        G->>VA: State + velocity/geo data
        VA->>LLM: Velocity analysis prompt
        LLM-->>VA: SpecialistVerdict

        G->>IA: State + identity/geo/device data
        IA->>LLM: Identity analysis prompt
        LLM-->>IA: SpecialistVerdict

        G->>BA: State + behavioral data
        BA->>LLM: Behavioral analysis prompt
        LLM-->>BA: SpecialistVerdict
    end

    VA-->>ADJ: velocity_verdict
    IA-->>ADJ: identity_verdict
    BA-->>ADJ: behavioral_verdict
    ADJ->>LLM: All 3 verdicts
    LLM-->>ADJ: DebateAnalysis
    ADJ->>ADJ: Synthesize final verdict
    ADJ-->>C: SwarmAssessment
```

## Data Flow

```
Transaction (input)
    │
    ├── amount, merchant, customer ─────▶ VelocityCheck ────▶ VelocityResult
    ├── ip_address, billing_country ────▶ GeoLookup ────────▶ GeoResult
    ├── device_id ─────────────────────▶ DeviceFP ──────────▶ DeviceFPResult
    ├── email, account, customer ──────▶ IdentityCheck ─────▶ IdentitySignals
    └── session, navigation ───────────▶ BehaviorAnalysis ──▶ BehavioralSignals
                                                                    │
                            All signals distributed to specialists ◀┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            Velocity Agent       Identity Agent      Behavioral Agent
                    │                   │                   │
                    ▼                   ▼                   ▼
            SpecialistVerdict   SpecialistVerdict   SpecialistVerdict
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                                   Adjudicator
                            ┌───────────┴───────────┐
                            ▼                       ▼
                    DebateAnalysis           SwarmAssessment
                    ├── agreement_score      ├── risk_level
                    ├── agreeing_agents      ├── confidence
                    ├── dissenting_agents    ├── recommended_action
                    ├── contention_points    ├── summary
                    └── resolution           ├── specialist_verdicts[]
                                             ├── debate_analysis
                                             ├── tool_results (raw)
                                             └── assessed_at
```

### State Isolation Pattern

Each specialist writes to its own key in `SwarmState` — no merge conflicts:

```
SwarmState (TypedDict)
├── transaction           ← input
├── tool_results          ← gather_all_signals writes
├── identity_signals      ← gather_all_signals writes
├── behavioral_signals    ← gather_all_signals writes
├── velocity_verdict      ← velocity_agent writes (exclusive)
├── identity_verdict      ← identity_agent writes (exclusive)
├── behavioral_verdict    ← behavioral_agent writes (exclusive)
├── debate_analysis       ← adjudicator writes
└── final_assessment      ← adjudicator writes
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Topology | Fan-out/fan-in | Parallel specialist execution, single adjudication point |
| State isolation | Separate verdict keys per agent | Avoids LangGraph merge conflicts in parallel nodes |
| Debate resolution | Adjudicator + weighted synthesis | Context-dependent weighting beats simple majority vote |
| Disagreement handling | Conservative — bump toward "review" | Matches fintech risk tolerance; false positives < false negatives |
| Mock fallback | Per-agent mock functions | Each specialist has independent fallback; real/mock can mix |
| Model architecture | Same LLM for all agents (configurable) | Simplicity; could tier models per specialist for cost optimization |
| Tool execution | asyncio.gather for all 5 tools | ~0.3s total vs ~1.5s sequential; critical for real-time use |
