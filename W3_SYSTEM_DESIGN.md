# Week 3 System Design Diagram

This is a simplified C4-inspired container view for the outside-in AgentForge adversarial AI security platform. It intentionally hides low-level internal edges so the first read answers three questions:

- Who uses the system?
- What is inside the adversarial platform?
- What external Co-Pilot target does it test?

```mermaid
flowchart TB
  Operator["Hospital director / CISO / security engineer"]

  subgraph Inputs["Design inputs"]
    direction TB
    Threat["Threat model<br/>risk categories"]
    Cases["Eval cases<br/>approved seeds"]
    Config["Environment config<br/>allowlist, budgets, synthetic auth"]
  end

  subgraph Platform["Deployed adversarial platform"]
    direction TB
    UI["Operator UI<br/>FastAPI risk dashboard"]
    Controller["Run controller<br/>target mode, auth, budgets"]
    Agents["LangGraph agent loop<br/>Orchestrator, Red Team, Target Runner, Judge, Docs"]
    Store[("SQLite run store<br/>persistent volume")]
    Exports["Evidence exports<br/>JSON, Markdown, reports"]

    UI --> Controller
    Controller --> Agents
    Agents --> Store
    Store --> UI
    Store --> Exports
  end

  subgraph Target["Allowlisted Co-Pilot target"]
    direction TB
    Web["Co-Pilot web<br/>clinician workflow"]
    API["Co-Pilot API<br/>chat, documents, writes"]
    OpenEMR["OpenEMR FHIR<br/>synthetic patients and notes"]
    Web --> API --> OpenEMR
  end

  Operator -->|"reviews risk"| UI
  Inputs -->|"defines scope"| Controller

  Agents -->|"black-box HTTP attacks<br/>and observed evidence"| Web

  classDef actor fill:#fff7ed,stroke:#c2410c,color:#111827;
  classDef input fill:#eef2ff,stroke:#4f46e5,color:#111827;
  classDef platform fill:#ecfdf5,stroke:#059669,color:#111827;
  classDef target fill:#eff6ff,stroke:#2563eb,color:#111827;
  classDef data fill:#fef9c3,stroke:#a16207,color:#111827;

  class Operator actor;
  class Threat,Cases,Config input;
  class UI,Controller,Agents,Exports platform;
  class Store data;
  class Web,API,OpenEMR target;
```

## Design Readout

The system is an outside-in adversarial platform, deployed separately from Co-Pilot. It supports local and deployed target modes, but the operator app itself must be deployed for checkpoint and final review.

The simple container view is:

1. Design inputs define what is allowed and what matters: threat model, approved eval cases, target allowlist, budgets, and synthetic auth.
2. The deployed adversarial platform runs the operator UI, run controller, LangGraph agent loop, SQLite run store, and exports.
3. The platform attacks only the allowlisted Co-Pilot target through black-box HTTP workflows.
4. Co-Pilot returns observable evidence: responses, citations, timings, status codes, and tool outcomes.
5. The platform stores verdicts, traces, draft reports, confirmed reports, and regression artifacts in SQLite.
6. The operator UI presents a hospital-director risk view; exports provide submission evidence.

The detailed internal graph still exists conceptually:

```text
Orchestrator -> Red Team -> Target Runner -> Judge -> Documentation Draft -> Regression Store -> Orchestrator
```

That internal loop belongs in the deeper `W3_ARCHITECTURE.md`, not the first system-design diagram.
