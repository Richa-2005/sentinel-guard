
# Sentinel Guard: Autonomous Real-Time Fraud Threat Mitigation Matrix Core

An enterprise-grade, high-throughput financial risk core designed to intercept, evaluate, and audit transactional telemetry in mid-flight. Sentinel Guard fuses sub-10ms machine learning ensemble inferences with an asynchronous, multi-agent legal reasoning engine orchestrated via LangGraph. 

Rather than treating fraud detection as an isolated classification problem, this platform provides a complete corporate risk command center: dynamically tracking sliding behavioral anomalies, storing system metrics inside a persistent transaction-safe engine, generating cross-referenced regulatory audit memos via localized LLMs, and securing logs within an immutable cryptographic hash chain.

---

## System Topology & Data Pipeline

The following architectural model isolates the low-latency transactional execution path from the data-heavy compliance auditing queues to prevent API gateway leakage or connection lag:


```

                                [ INBOUND TRANSACTION API REQUEST ]
                                              │
                                              ▼
                                ┌───────────────────────────────┐
                                │ Sub-10ms Sync Engine Pass     │ ──► [ Writes Features to SQLite WAL ]
                                │ - Calculates Velocity Metrics │
                                │ - Evaluates Model Ensemble    │
                                └───────────────────────────────┘
                                              │
                                    (Is Blocked == True)
                                              │
                                              ▼
                                ┌───────────────────────────────┐
                                │ Async Background Thread Shunt │
                                └───────────────────────────────┘
                                              │
                                              ▼
              ┌────────────────────────────────────────────────────────────────────────┐
              │            4-NODE LANGGRAPH STATE MACHINE AUDITING DIRECTORY           │
              │                                                                        │
              │  [Node 1: textForensics] ──► Extracts XGB/LGB SHAP Split Consensus     │
              │                                      │                                 │
              │  [Node 2: crossRefRAG]   ──► Queries synthetic compliance fixtures     │
              │                                      │                                 │
              │  [Node 3: legalVerdict]  ──► Compiles Structured Memo via Llama 3.1    │
              │                                      │                                 │
              │  [Node 4: cryptLedger]   ──► Chains Record using SHA-256 Checksums     │
              └────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                             [ IMMUTABLE FORENSIC AUDIT LOG ]

```

---

## The Tech Stack Core

| Layer | Component | Technical Selection & Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI | Async event-driven architecture, processing high-concurrency requests with sub-10ms execution gates. |
| **Storage Engine** | SQLite (WAL Mode) | Persistent transactional ledger with Write-Ahead Logging to maximize concurrent reads/writes under heavy simulation stress. |
| **ML Engine Matrix** | XGBoost & LightGBM | Blended model ensemble utilizing weighted probability trees to evaluate non-linear risk shapes. |
| **Explainability Core** | SHAP (SHapley Additive exPlanations) | Translates raw tree decisions into mathematical feature contributions for transparent model audits. |
| **Agent State Machine**| LangGraph | Structured Directed Acyclic Graph (DAG) managing immutable state transitions across legal audit nodes. |
| **Knowledge Base (RAG)**| In-Memory Regex Chunking | Targeted paragraph retrieval across clearly labelled synthetic compliance fixtures and an MCC registry. |
| **LLM Execution Node** | Ollama (Llama 3.1) | Localized inference execution node ensuring strict data privacy and enterprise zero-data leakage compliance. |
| **Frontend Dashboard** | React & Tailwind CSS | Modern, dark cyber-command dashboard featuring glowing telemetry gauges and live stream simulators. |

---

## Core System Specifications

### Low-Latency Analytical Feature Hydration
The system references real-time and historical transactions to calculate stateful parameters on the fly:
* `card_vel_10m`: Tracks rapid consecutive swipes within a short 10-minute sliding ledger window to catch programmatic script leaks.
* `device_card_ratio_30m`: Correlates how many unique payment cards are mapping to a single hardware device fingerprint, exposing distributed fraud rings.
* `is_off_hours_window`: Flags transactions hitting the gateway inside the high-risk 01:00 AM - 05:00 AM temporal boundary.

### Model Consensus & Multi-Agent Legal Reasoning
When a high-risk event is tripped, the background worker launches a 4-node LangGraph network:
1. **`textForensics`**: Combes individual model SHAP maps to verify tree consensus. Flags an `ARCHITECTURAL DIVERGENCE ALERT` if XGBoost and LightGBM output contradictory node directions.
2. **`crossRefRAG`**: Cross-references active metrics against synthetic RBI/Visa-style demonstration fixtures and a 334-row indexed **Merchant Category Code (MCC)** directory. The fixtures are not official legal sources.
3. **`legalVerdict`**: Prompts the localized Llama core to compile a structured demonstration compliance memo.
4. **`cryptLedger`**: Automates a linked-list chain. It hashes the report text bound with the preceding row’s checksum signature, generating a tamper-evident audit ledger on disk.

### Human-in-the-Loop Review

Blocked model decisions automatically enter an authenticated review queue.
Analysts can claim cases and submit reasoned dispositions; administrators can
assign, reopen, and override cases. Original model output is never rewritten,
and every workflow transition is stored in a database-enforced append-only
action history. Clients submit the case `version` with every transition so a
stale browser cannot overwrite another reviewer's work.

### Audit-Chain Verification

Authenticated users can call `GET /api/v1/audits/verify` to recompute the
complete audit vault from its genesis hash. The verifier checks every stored
digest, every previous-hash link, the chain head, and hash formatting, then
returns a structured integrity report with the first invalid record and bounded
issue details.

### Operational Model Monitoring

Administrators can call `GET /api/v1/monitoring/model?window_hours=24` for a
time-windowed report covering prediction volume, block rate, risk-score
distribution, human-review coverage and outcomes, resolution latency, and
recent-versus-previous score-distribution PSI. Drift is reported as
`insufficient_data` until both windows contain at least 30 predictions; this is
operational monitoring rather than a claim of real-world model accuracy.

---

## 📂 Repository Directory Layout

```text
sentinel-guard/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── agent.py          # LangGraph Workflow DAG definitions & Ollama calls
│   │   │   ├── database.py       # SQLite connection layer and WAL initialization
│   │   │   ├── explainer.py      # SHAP translation matrix bridge
│   │   │   ├── knowledge.py      # KnowledgeBaseManager corpus segmenter & RAG matcher
│   │   │   └── trainer.py        # XGB/LGB model training pipeline & feature calibration
│   │   └── main.py               # FastAPI router paths, worker pool, & endpoints
│   └── data/
│       ├── corporate_policy.txt  # Internal corporate threshold ceilings
│       ├── rbi_circular.txt      # Synthetic RBI-style demonstration fixture
│       ├── network_tos.txt       # Synthetic card-network demonstration fixture
│       └── mcc_codes.csv         # Structured 334-row industry sector risk lookup directory
└── frontend/
    └── src/
        ├── components/
        │   ├── LandingWelcome.jsx # Onboarding Quick-Start tour page
        │   ├── RealTimeStream.jsx # Live sandbox transaction forge & traffic simulator
        │   ├── IncidentCenter.jsx # Blocked logs list with tree model feature dials
        │   └── ComplianceVault.jsx# Cryptographically chained Markdown audit reviews
        └── hooks/
            └── useTrafficSimulator.js # Drives the auto-traffic requests sequence loop

```

---

## Quick-Start Installation & Setup

### 1. Prerequisites

Ensure you have Python 3.10+, Node.js 18+, and [Ollama](https://ollama.com) installed locally.

### 2. Configure the LLM Node

Boot your terminal and download the required model weight layer to your local Ollama registry instance:

```bash
ollama pull llama3.1

```

### 3. Backend Setup

Navigate into the backend workspace, set up your virtual environment, and activate the server:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r ../requirements.txt
cp .env.example .env

# Put the output of this command into JWT_SECRET_KEY in backend/.env
openssl rand -hex 32

alembic -c alembic.ini upgrade head

# Create the first administrator interactively
python -m app.cli.create_admin --email admin@example.com --name "Demo Admin"

# Boot the FastAPI server instance on its local port
uvicorn app.main:app --host 127.0.0.1 --port 8000

```

### 4. Frontend Setup

Open a secondary console window, install the design packages, and spin up the React client:

```bash
cd frontend
npm install
npm run dev

```

### Backend Docker Runtime

Start the persistent backend service while Ollama is running on the host
machine:

```bash
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
docker compose up --build
```

Compose stores SQLite state in the named `sentinel-guard-runtime` volume, so
transactions, audit jobs, and hash-linked records survive container
replacement. The image uses `http://host.docker.internal:11434/api/generate`
to reach host Ollama, with a host-gateway mapping for Linux. Override
`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, or `OLLAMA_TIMEOUT_SECONDS` when using a
different Ollama deployment.

The container applies pending Alembic migrations before starting the API.
Public registration creates analysts only. Create the first administrator with
the CLI command shown above; authenticated administrators can then manage roles
and account status through `/api/v1/auth/users`.

The small inference and synthetic knowledge-base assets required to run a fresh clone are
versioned under `backend/data/`. Generated training data and mutable runtime
state remain excluded. See the [model card](backend/data/MODEL_CARD.md) for
evaluation results, limitations, and checksum verification.

---

## Real-Time Verification Testing

To verify the system end-to-end without waiting for manual entries, navigate to the **Sandbox Activity Stream** tab inside the dashboard.

### Interactive Manual Testing

You can input manual transactions using the custom sandbox panel. To trigger a forced system block and check the resulting LangGraph blockchain logs, pass an explicit high-risk anomaly signature:

```bash
curl -X 'POST' \
  '[http://127.0.0.1:8000/api/v1/evaluate](http://127.0.0.1:8000/api/v1/evaluate)' \
  -H 'Authorization: Bearer <access_token>' \
  -H 'Content-Type: application/json' \
  -d '{
  "amount_paise": 950000,
  "device_id": "malicious_hardware_ring_01",
  "card_id": "stolen_card_token_01",
  "merchant_id": "7995"
}'

```

### Expected Output Results

Check your console logs and look inside `backend/data/compliance_audit.log` to read the generated signed audit output:

```text

NEXUS FINTECH COMPLIANCE INCIDENT REPORT [ALERT-GATEWAY-REJECTION]

A. EXECUTIVE RISK VERDICT: Transaction blocked due to critical velocity breach...
B. TECHNICAL SPECIFICATION PROFILE: Amount: 950000 Paise | MCC: 7995 (Gambling)
C. REGULATORY COMPLIANCE CROSS-REFERENCE: Violates Sec 2.1 of Corporate spending...
D. MITIGATION & ACTIONABLE DEFENSE ROADMAP: Compile FMR-1 matrix filing within 3 weeks...

[CRYPTOGRAPHIC LEDGER CHAIN CHECK]
 |- PREVIOUS_ENTRY_HASH : 0000000000000000000000000000000000000000000000000000...
 |- CURRENT_RECORD_HASH : fe3f89bf87973661d652aa7d21194d46217a5a7573357bbac789...

```

---
