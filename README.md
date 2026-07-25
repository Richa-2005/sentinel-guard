# Sentinel Guard

Sentinel Guard is a portfolio-grade fraud operations platform that combines
real-time transaction scoring, explainable ensemble decisions, human review,
model monitoring, and tamper-evident compliance records.

The project is designed around two authenticated roles:

- **Analyst** — investigates assigned blocked transactions and submits an
  evidence-backed recommendation.
- **Administrator** — assigns cases, records the final verdict, monitors the
  model and review operation, verifies the audit chain, and manages access.

> Sentinel Guard uses synthetic data and demonstration policy fixtures. It is
> not approved for real payment authorization, regulatory filing, or legal
> decision-making.

## Architecture

```text
Browser
  │
  ▼
Nginx / React SPA
  ├── /api/* ───────────────► FastAPI
  └── /ws/* ────────────────► authenticated WebSocket
                                  │
                                  ├── XGBoost + LightGBM ensemble
                                  ├── SHAP model explanations
                                  ├── SQLite transaction/review ledger
                                  └── durable single-report worker
                                           │
                                           ▼
                                      Ollama / Llama 3.1
                                           │
                                           ▼
                                  SHA-256 linked audit vault
```

The transaction response path performs feature hydration, model inference,
SHAP explanation, persistence, review-case creation, and WebSocket delivery.
Blocked transactions create durable report jobs. A single background worker
processes those jobs so local model generation cannot overload the API or the
model server.

## Main capabilities

- JWT authentication with analyst and administrator authorization
- Public analyst registration and separately provisioned administrator access
- XGBoost and LightGBM probability ensemble with calibrated decision threshold
- Stateful velocity, device/card, merchant, and off-hours features
- Separate per-model SHAP evidence
- Authenticated live transaction delivery over WebSocket
- Durable audit jobs with retry and interrupted-job recovery
- Structured compliance memoranda generated through a local model service
- Downloadable Markdown reports
- Analyst recommendation and administrator final-decision workflow
- Optimistic case versioning to prevent stale updates
- Database-enforced append-only review history
- SHA-256 linked audit records with chain verification
- Prediction, review, latency, block-rate, and PSI monitoring
- UTC timestamps as the canonical audit timeline
- Seeded, role-specific portfolio demonstration mode
- Alembic database migrations
- Dockerized frontend, backend, model service, and persistent volumes

## Runtime stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, Nginx |
| API and WebSocket | FastAPI, Uvicorn |
| Persistence | SQLite WAL, SQLAlchemy, Alembic |
| Classification | XGBoost, LightGBM |
| Explainability | SHAP |
| Report workflow | LangGraph |
| Local generation | Ollama with Llama 3.1 |
| Container orchestration | Docker Compose |

## Model assets

The small inference artifacts and synthetic knowledge fixtures required for a
reproducible clone are versioned under `backend/data/`. Generated datasets and
runtime databases are excluded from Git.

Image builds verify `backend/data/artifacts.sha256`; a checksum mismatch stops
the backend image build. `requirements-runtime.txt` contains the production
dependency set, while `requirements.txt` retains the broader local
development and training environment. Detailed model scope, evaluation results, and
limitations are documented in
[`backend/data/MODEL_CARD.md`](backend/data/MODEL_CARD.md).

## Complete Docker deployment

### Requirements

- Docker Engine with Docker Compose v2
- Approximately 8 GB of free memory
- Approximately 8 GB of free disk space for images and the local model

### Configuration

```bash
cp .env.example .env
openssl rand -hex 32
```

Store the generated value as `JWT_SECRET_KEY` in the untracked root `.env`.
Set `DEMO_MODE=true` only for the public portfolio demonstration.

### Start

```bash
docker compose up --build
```

On the first start, Compose downloads the configured Ollama image and model.
The model is stored in the `sentinel-guard-models` volume and is reused on
subsequent starts.

Open:

- Application: `http://localhost:8080`
- API documentation through the frontend gateway: `http://localhost:8080/docs`

Compose runs four coordinated services:

1. `ollama` — persistent local inference server
2. `model-loader` — one-time model availability gate
3. `backend` — migrations, API, WebSocket, models, worker, and SQLite
4. `frontend` — production React bundle and same-origin reverse proxy

The `sentinel-guard-runtime` volume retains users, transactions, review
history, audit jobs, and audit records across container replacement.

### Create an administrator

When demonstration mode is disabled, create the initial administrator from the
running backend container:

```bash
docker compose exec backend \
  python -m app.cli.create_admin \
  --email admin@example.com \
  --name "Sentinel Administrator"
```

### Stop

```bash
docker compose down
```

Named volumes remain intact. Removing the volumes also removes the local model
and application database:

```bash
docker compose down --volumes
```

## Local development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp .env.example .env
alembic -c alembic.ini upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend environment requires a non-empty `JWT_SECRET_KEY`. Local report
generation also requires Ollama with the configured model.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server proxies API and WebSocket traffic to
`127.0.0.1:8000`.

## Tests

```bash
cd backend
JWT_SECRET_KEY=test-only-secret-key-with-at-least-32-characters \
DEMO_MODE=true \
venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

```bash
cd frontend
npm test -- --run
npm run build
```

## Deployment notes

The complete Compose stack is best suited to a Linux virtual machine because it
requires persistent volumes, long-running WebSockets, SQLite single-writer
coordination, and several gigabytes of memory for local inference.

For a split cloud deployment:

- Serve the frontend from a static host or CDN.
- Run the backend as exactly one worker while SQLite and the in-process audit
  dispatcher are used.
- Attach persistent storage for the database.
- Point `OLLAMA_BASE_URL` at a private, persistent Ollama service.
- Use HTTPS and WSS at the public edge.
- Keep `DEMO_MODE=false` outside the portfolio sandbox.

Horizontal backend scaling requires moving the database to a shared server
database and coordinating report jobs and WebSocket fan-out through shared
infrastructure such as Redis.
