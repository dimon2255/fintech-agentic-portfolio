# Golden-Set Evaluation Harness: Data Flow

How a scenario flows through the harness ([ADR-001](../adr/001-golden-set-evaluation.md)). Green nodes are the
projects' own code, run unmodified. Blue nodes are harness code. The orange node is the only behavior the harness
changes inside a project: simulated latency is set to zero. Grey nodes are observation-only wrappers that call
through unchanged.

```mermaid
flowchart LR
    subgraph harness["Harness process (python -m evals)"]
        golden["Golden scenarios<br/>evals/golden/*/*.json<br/>narrative, inputs,<br/>evidence constraints,<br/>labels, rationale"]
        runner["runner.py<br/>one subprocess per project"]
        score["score.py<br/>grade against labels;<br/>errors, drift and fallbacks<br/>excluded from accuracy"]
        gate["baseline.json ratchet<br/>(rules tier, CI)"]
        cards["docs/evals/<br/>scorecard, claude-run-N,<br/>scorecard-claude"]
    end

    subgraph worker["Worker subprocess, cwd = project-N/ (python -m evals.worker)"]
        env["Environment set before import<br/>rules: both API keys empty<br/>LLM: ANTHROPIC_API_KEY from env,<br/>OPENAI_API_KEY empty, DEFAULT_MODEL set<br/>(verified after load_dotenv)"]
        evid["Evidence check<br/>calls the project's own tool<br/>functions on the inputs"]
        entry["Project entrypoint<br/>P1 classify_transaction<br/>P2 analyze_transaction<br/>P3 run_kyc_application"]
        graph["LangGraph graph, agents,<br/>prompts, thresholds, routing,<br/>final-decision logic"]
        tools["Simulated tools (tools.py)<br/>hash-seeded observations<br/>and risk scoring"]
        latency["SIMULATED_LATENCY_SECONDS = 0"]
        rules["Rules mode: mock_llm.py"]
        llm["LLM mode: ChatAnthropic via src/llm.py<br/>default claude-haiku-5-5 since 2026-10-13<br/>(runs 1 to 4: claude-haiku-4-5-20251001)"]
        rec["LLM call recorder<br/>(tokens, model, errors)<br/>rules tier: any call raises"]
        fb["Fallback counters<br/>wrap mock_* fallbacks;<br/>P1 fallback summary marker"]
    end

    golden --> runner --> env --> evid --> entry --> graph
    graph --> tools
    latency -.-> tools
    graph -->|"no key"| rules
    graph -->|"key"| rec --> llm
    graph -.->|"unparseable LLM reply"| fb --> rules
    graph -->|"decision JSON"| runner
    evid -->|"drift: harness error"| runner
    runner --> score --> gate
    score --> cards

    classDef real fill:#d9f2d9,stroke:#2e7d32,color:#000
    classDef harness fill:#dde8f7,stroke:#1f5fa8,color:#000
    classDef changed fill:#fde3c8,stroke:#c25e00,color:#000
    classDef observe fill:#eeeeee,stroke:#666,color:#000
    class entry,graph,tools,rules,llm real
    class golden,runner,score,gate,cards,env,evid harness
    class latency changed
    class rec,fb observe
```

## What is real and what is replaced

| Component | In the evaluation |
|---|---|
| Entrypoints, LangGraph graphs, agent nodes, supervisor routing, adjudicator, final-decision logic | Real, unmodified |
| Prompts and LLM calls (LLM tier) | Real, through the projects' own `ChatAnthropic` construction |
| Deterministic rules (`mock_llm.py`, rules tier) | Real, unmodified |
| Simulated data sources and their risk scoring (`tools.py`) | Real, unmodified; inputs chosen so they return the scenario's evidence |
| Simulated latency | Set to zero |
| Network access in the rules tier | Blocked: any LLM call raises |
| LLM call accounting and fallback detection | Observation-only wrappers that call through |
| Labels | Hand-written by one author from each scenario narrative |
