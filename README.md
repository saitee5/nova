# NOVA

### The voice that notices what no single sensor can.

![NOVA](assets/banner.png)

NOVA is an agentic industrial safety intelligence system. It watches a plant's live operational signals — gas sensors, permit-to-work logs, maintenance records, shift data, and CCTV events — continuously and autonomously, correlates them against each other and against organizational memory, and speaks up the moment an otherwise invisible combination of facts becomes dangerous. It asks for authorization before it acts, executes only what a human approves, and writes what it learns back into memory so the next incident is caught faster.

Built for **StarForge 2026 — Track 1 (VoxForge).**

---

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [MVP User Flow](#mvp-user-flow)
- [Features](#features)
- [What Makes This Different](#what-makes-this-different)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Sponsor Technology Integration](#sponsor-technology-integration)
- [Getting Started](#getting-started)
- [Repository Structure](#repository-structure)
- [Evaluation](#evaluation)
- [Limitations](#limitations)
- [Team](#team)
- [License](#license)

---

## The Problem

India's heavy industrial sector continues to pay a devastating human cost. DGFASLI recorded over 6,500 fatal workplace accidents in FY2023 — a figure that excludes most mining and construction fatalities. In one of the most disturbing recent incidents, eight workers died at the Visakhapatnam Steel Plant in January 2025 when entrapped gases triggered a sudden explosion in a coke oven battery — a facility with functioning gas detectors, permit-to-work controls, and SCADA. The subsequent investigation found that warning signals from gas pressure sensors existed. They were never connected to an operational decision in time.

This is not a story about missing technology. A 2024 FICCI survey found that over 60 percent of large industrial facilities rely on manual handoffs between their own digital safety tools. The sensors exist. The permit systems exist. The maintenance logs exist. What does not exist, in nearly all of these facilities, is the layer that fuses them into one real-time risk picture and acts on it before a fatality, not after one is already being investigated.

Every one of those systems, on their own, is doing its job correctly. A gas reading eight percent above baseline is not an alarm. A hot-work permit is routine paperwork. A maintenance flag on a compressor is a footnote in a logbook. A shift changeover is a scheduling event. None of these, individually, is worth a phone call. Together, in the same bay, in the same twenty-minute window, they are the exact pattern that has preceded fatal incidents before — and no single sensor, no single threshold rule, and no dashboard a human has to remember to check is built to see that.

## The Solution

NOVA is not a dashboard, and it is not a chatbot with a microphone attached. It runs a standing, autonomous reasoning loop over live plant data:

**Detect → Contextualize → Retrieve organizational memory → Reason about compound risk → Explain → Recommend → Authorize and act → Verify → Learn**

NOVA correlates signals across sources and across time, checks whether a similar combination has mattered before anywhere in the plant's history, and — because the people who need this information are wearing PPE, standing near hazardous equipment, and cannot safely stop to read a screen — it tells them, out loud, before they have to ask. It does not wait for a person to open an app. It does not wait for a person to notice a red cell in a spreadsheet. It watches, and when the pattern is real, it speaks.

Every action beyond a spoken warning requires an explicit human decision. NOVA proposes; it never unilaterally executes. That boundary is enforced structurally, in code, not by instruction to a language model.

## MVP User Flow

1. **The plant opens already under watch.** There is no "start monitoring" step. NOVA is live from the moment the interface loads, continuously ingesting sensor, permit, maintenance, and shift data.
2. **Weak signals accumulate.** Individually sub-threshold facts across multiple sources build up inside a rolling time window for a given zone.
3. **NOVA correlates and retrieves.** The Risk Reasoner assembles the current situational context, queries organizational memory for a matching historical incident or near-miss, and computes a compound-risk score from deterministic, auditable arithmetic — not an opaque model confidence value.
4. **NOVA speaks first.** When the compound score crosses a calibrated threshold, NOVA proactively voices the situation: what is happening, why it matters, and what precedent it found — structured as state, then evidence, then a single closed-form question if action is warranted.
5. **The user can interrupt at any point.** Barge-in is handled natively. An interruption cancels NOVA mid-sentence, is answered directly, and the original thread resumes without being lost.
6. **Authorization is explicit.** For any action beyond a notification, NOVA asks a single yes-or-no question. Nothing executes without a recorded human decision, captured either by voice or through a visible fallback control.
7. **Approved actions execute and are logged.** A real, typed action runs — for example, suspending a permit — and the complete evidence-to-decision-to-action chain is written to an immutable audit trail.
8. **Resolution becomes memory.** On close, NOVA asks a short spoken debrief. The answer, together with the full evidence trail, is embedded and written into long-term organizational memory.
9. **The next incident is caught faster.** A later case with a similar pattern retrieves the lesson just written and cites it directly — demonstrable, in the same demo, not asserted as a future capability.

The demo mode on the landing page runs this exact sequence end to end against a scripted, replayable telemetry feed, so the entire loop — from a quiet plant to a spoken warning to an authorized action to a written lesson — is visible in one continuous walkthrough.

## Features

**Core, always on**

- Multi-source event correlation across sensors, permits, maintenance, and shift data
- Deterministic, explainable compound-risk scoring — never a black-box confidence number
- Historical incident and near-miss retrieval that directly changes the computed risk score
- Proactive, evidence-first voice notification with full barge-in and interruption handling
- Confirmation-gated action execution with a complete, immutable audit trail
- Organizational memory that writes back on every resolved case and is retrievable on the very next one

**Safety architecture**

- Deterministic threshold alarms that fire independently of any AI reasoning
- A single, structurally enforced authorization gate — the reasoning layer proposes, it never executes
- A fixed escalation ladder, officer to shift manager to deterministic fallback, with enforced timeouts
- Hallucination prevention: every spoken claim must be traceable to a specific input fact or it is dropped before being said

## What Makes This Different

| Capability | Why a generic RAG chatbot or dashboard cannot replicate it |
|---|---|
| Compound-risk reasoning | A standing correlation loop that initiates contact, not a system that answers only when asked |
| Temporal correlation | Risk is defined by the combination and sequence of signals, which requires a stateful reasoning loop, not a single retrieval call |
| Retrieval that changes the decision | The historical-match similarity score is a direct input to the compound-risk arithmetic, not a citation fetched after the fact |
| Compounding organizational memory | Every resolved case writes back into the exact memory the next detection queries — the system measurably improves across its own operating history, demonstrated live, not claimed |
| Voice-first, interruption-safe interaction | Losing conversation state on barge-in is the most common voice-agent failure; NOVA is architected specifically around a persistent interruption-state stack |

## Architecture

The complete system design — every layer from the browser to the vector database, with a full diagram — lives in **[`ARCHITECTURE.md`](./ARCHITECTURE.md)** and **[`docs/BACKEND_ARCHITECTURE.md`](./docs/BACKEND_ARCHITECTURE.md)**.

```text
                  INDUSTRIAL SYSTEMS
                         │
                         ▼
                INGESTION / NORMALIZATION
                         │
                         ▼
                    CANONICAL EVENTS
                         │
                         ▼
                     PLANT STATE
                         │
                ┌────────┴────────┐
                ▼                 ▼
          FEATURE ENGINE     CONTEXT ENGINE
                │                 │
                └────────┬────────┘
                         ▼
                    ML PIPELINE
                         │
                         ▼
               INDUSTRIAL RISK ENGINE
                         │
                         ▼
               OPERATIONAL EPISODE
                    │          │
                    ▼          ▼
               PostgreSQL    Qdrant
                    │          │
                    └────┬─────┘
                         ▼
                  EVIDENCE PACKAGE
                         │
                         ▼
                        LLM
                         │
                         ▼
                  OPERATOR / VOICE
                         │
                         ▼
                      FEEDBACK
```

NOVA is a single logical pipeline implemented as one backend process with cleanly separated modules — no microservice mesh, no unnecessary infrastructure. Five async agents (Sensor and Event Intelligence, Operational Context, Risk Reasoner, Response Orchestrator, Voice Interaction) sit behind a deterministic policy and safety gate with zero LLM involvement, backed by a vector memory layer in Qdrant and a relational state and audit store in SQLite/PostgreSQL, fronted by a real-time, WebSocket-driven interface.

See `ARCHITECTURE.md` and `docs/` for the full layered diagram, the request lifecycle, deployment topology, and every failure and degradation path the system is designed to handle gracefully.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React and TypeScript, single client-side store, native WebSocket |
| API gateway | FastAPI, REST and WebSocket |
| Agent orchestration | Async Python tasks within one process, in-process event bus |
| Policy engine | Pure deterministic Python — no LLM dependency |
| Vector memory | Qdrant — hybrid dense and lexical search, cross-encoder reranking |
| Relational store | SQLite |
| Embeddings | BAAI/bge-small-en-v1.5, local |
| Reranker | BAAI/bge-reranker-base, local |
| LLM | Hosted API with a local fallback model |
| Speech recognition | faster-whisper, local |
| Voice synthesis | Rime, streaming |
| Deployment | Single-process backend, static frontend hosting — no Docker, no Kubernetes |

Every component was chosen to build and demo at zero cost. Full rationale for each choice, and the exact free-tier path for each, is in `ARCHITECTURE.md`.

## Sponsor Technology Integration

**Rime** is the only channel through which NOVA initiates contact. It is not a text-to-speech layer added to a chat interface. Streaming synthesis, sub-second time-to-first-audio, mid-utterance barge-in cancellation, and pronunciation handling for equipment identifiers and measurements are first-class requirements of the system, not afterthoughts.

**Qdrant** is one of the system's intellectual cores, not a decorative vector store. Its retrieval score is a direct, causal input to the compound-risk tier — removing it removes NOVA's only source of knowing whether a given combination of signals has mattered before. Eight purpose-built collections separate live case memory from long-term organizational memory, with hybrid dense and lexical search and payload filtering so retrieval is precise, not merely topical.


## Getting Started

```bash
git clone https://github.com/sachdeva-aarushi/nova.git
cd nova

# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in RIME_API_KEY at minimum; LLM defaults to a local fallback
python -m uvicorn main:app --reload

# Vector memory, separate terminal
qdrant   # or: docker run -p 6333:6333 qdrant/qdrant
python ../qdrant/ingestion/ingest_seed_data.py

# Frontend, separate terminal
cd ../frontend
npm install
npm run dev
```

Open the app and select **View Demo** on the landing page to run the full detection-to-resolution sequence end to end against scripted telemetry.

Run the committed evaluation benchmark:

```bash
python evaluation/benchmark_runner.py
```

Full setup notes, the complete environment variable reference, and troubleshooting live in `.env.example` and `ARCHITECTURE.md`.

## Repository Structure

```
nova/
├── ARCHITECTURE.md      complete system design and diagrams
├── LIMITATIONS.md
├── backend/             FastAPI app: agents, policy engine, memory, services
├── frontend/             React app: live plant view and case experience
├── data_simulator/       scripted, replayable telemetry — no physical IoT required
├── qdrant/                collection schemas, seed data, ingestion
├── evaluation/            benchmark runner and committed results
└── demo/                  demo script and fallback recording
```

## Evaluation

Every metric shown in this repository is generated from a fixed, versioned scenario script and committed to `evaluation/results/` — reproducible by re-running `evaluation/benchmark_runner.py`, not hand-selected from a live demo run. Measured: compound-risk detection precision and recall, false-alarm rate, retrieval recall at k, task completion rate, human-escalation accuracy, voice latency, interruption-recovery correctness, and response correctness against the underlying source data.

## Limitations

This is a hackathon prototype, built and demoed with no physical IoT hardware — all sensor, SCADA, permit, maintenance, and shift data is simulated or synthetic and de-identified. Benchmark scenarios are scripted, not field-validated against a live facility. CCTV-derived events are pre-scripted labels rather than live computer vision unless stated otherwise. NOVA carries no formal safety certification and is not a substitute for certified industrial safety systems — it is designed to add an intelligence layer on top of a facility's existing deterministic safety controls, not to replace them.

## Team

Built by team .bin under VoxForge track @starforge 2026

## License

MIT — see `LICENSE`.
