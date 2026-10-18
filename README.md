# AlphaSight · AI Invest Assistant

**An end-to-end AI investment research platform: data collection → cleaning & storage → intelligent analysis → visualization.**

English | [简体中文](./README.zh-CN.md)

---

AlphaSight turns raw market data into daily, reusable research: a self-hosted collector pipeline keeps market / capital-flow / news data fresh, an agent runtime (deepagents on LangGraph) generates reviews, attributions and chain analyses, and a React workspace presents everything in one responsive console.

## Highlights

**Workbench** — one-stop market overview: sentiment, hotspots, indices and your watchlist at a glance.

![Workbench](docs/screenshots/workbench.png)

### Feature Tour

**Daily Review** — index performance & turnover, limit-up ladder (连板天梯), sector heatmap, limit-up attribution and an AI-generated market summary for every trading day.

![Daily Review](docs/screenshots/daily-review.png)

**Agent Hub (智体中枢)** — the mission-control board for your trading agents: live pulse of selections, records, plans, execution and reviews.

![Agent Hub](docs/screenshots/agent-hub.png)

**Agent Experience & Lessons** — trading agents accumulate memory across runs: lessons learned, disciplines and methods, surfaced as reviewable cards.

![Agent Experiences](docs/screenshots/agent-experiences.png)

**Knowledge Base Search** — the global AI assistant answers investment questions by retrieving knowledge cards from your own course/book library, with original-text citations.

![Knowledge Base Search](docs/screenshots/kb-search.png)

**Industry Chain Graph** — versioned industry-chain analysis (nodes, edges, narratives) rendered as an interactive graph.

![Industry Chain](docs/screenshots/industry-chain.png)

### Full Capability Map

| Domain | Capabilities |
|--------|--------------|
| Market Research | Multi-timeframe K-line / call-auction trends / sector fund flow (river chart + ranking) / macro index monitoring |
| Daily Review | Index stats / limit-up review / AI market summary (module-level editing) / watchlist cards |
| AI Analysis | Versioned industry-chain analysis / limit-up attribution / daily watchlist analysis / research & earnings summaries / anomaly detection & attribution / AI trendlines / AI stock screening |
| News & Knowledge | Near-real-time cls.cn telegraph / news importance grading / hot-topic clustering / investment calendar / knowledge-base retrieval QA |
| AI Assistant | Global chat panel (deepagents streaming + tool calling + session persistence + page-context awareness) |
| Agent Hub | Trading agents with per-task prompts & skills, run streaming, HITL interrupts, experience memory (lessons / disciplines / methods) |
| Paper Trading | Juejin online simulation (account sync / order & cancel / NAV curve / trade markers on K-line) |
| Platform | Skill square (zip distribution / custom skills) / user settings (theme, MAs, AI quota) / admin console (21 modules) / user-group feature permissions |

## Architecture

```
Browser (desktop / mobile, responsive SPA)
   │  HTTPS  invest.example.com
   ▼
Caddy (TLS termination, auto Let's Encrypt)
   │  reverse proxy
   ▼
web :9000  ── all-in-one image ── FastAPI + React SPA (single uvicorn, SSE streaming,
   │                            in-process deepagents assistant)
   │  same-host docker network
   ├─ PostgreSQL (TimescaleDB, pg_trgm + pgvector)  ├─ Redis
   ├─ celery-beat + workers (realtime+batch / heavy)
   ├─ collector-stream (news telegraph)             ├─ paper-trade sidecar
   └─ douyin-signer sidecar                         ── COS (S3): PDFs, KB files, backups
```

- **Data layer**: PostgreSQL with TimescaleDB; hybrid retrieval via pg_trgm + pgvector (halfvec).
- **Task layer**: Celery beat + dual workers; a dedicated stream consumer ingests the news telegraph.
- **AI layer**: [deepagents](https://github.com/langchain-ai/deepagents) (LangChain/LangGraph) with YAML prompts, skills and MCP tools; per-user BYOD model config (bring your own key) with quota metering.
- **Deployment**: GitHub Actions builds images → Tencent Container Registry (TCR) → production server pulls by tag (`develop-<sha>`).

Full architecture design: [docs/arch/](./docs/arch/) (10 documents, 00–09).

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| Backend API | FastAPI, Python 3.10+, SQLAlchemy 2.0, Pydantic 2.7 |
| Web Frontend | React 18, TypeScript, Vite, TanStack Query, Zustand, Ant Design |
| AI Agent | deepagents (LangChain / LangGraph) + YAML prompts + Skills + MCP |
| Data Collection | In-house collector runtime, Celery, httpx / akshare / curl_cffi |
| Visualization | ECharts, AntV G6 v5, D3.js |
| Storage | PostgreSQL (TimescaleDB, pg_trgm + pgvector), Redis, COS (S3-compatible) |
| Package Mgmt | uv (Python), npm (frontend) |

## Quick Start

### Option A — full stack via Docker Compose

```bash
cp .env.example .env                # fill in what you need
docker compose up -d postgres redis # infrastructure first, wait for healthy
bash docker/database/migrate.sh     # create schema / run migrations (ledger-based)
docker compose up -d                # web on :9000, health check at /health
```

### Option B — local development (outside containers)

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 18+.

```bash
# 1. Infrastructure
docker compose up -d postgres redis

# 2. Backend on :9000 (Vite dev proxy targets 127.0.0.1:9000)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 9000

# 3. Frontend on :5173 (proxies /api to the backend)
cd web
npm install
npm run dev

# 4. Optional sidecars
docker compose up -d paper-trade douyin-signer
```

Open http://localhost:5173 and register the first user (promote to admin via `role` in DB or the admin console).

### Production deployment

Production runs from a single compose file on the server (images only, no build):

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d postgres --wait
bash docker/database/migrate.sh     # with COMPOSE_FILE=docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d --wait --remove-orphans --no-build
```

Images are built and pushed to TCR by GitHub Actions; the pinned tag lives in the server's `.env` as `APP_TAG=develop-<sha>`.

### Common Commands

```bash
# Backend type-check / lint / tests
cd backend
uv run mypy app/
uv run ruff check .
uv run pytest -m unit

# Frontend type-check / lint / tests
cd web
npm run typecheck
npm run lint
npm run test:unit
```

## Project Structure

```
ai-invest-assisstant/
├── backend/
│   ├── app/                    # FastAPI app (api / services / repositories / models / schemas / agent)
│   ├── collector/              # collector runtime (core / runtime / specs / spiders / stores)
│   └── tests/                  # pytest unit & integration tests
├── web/                        # React web app (src/ + Playwright e2e/)
├── shared/                     # FE/BE shared contract package (endpoints + types)
├── skills/                     # skill units (SKILL.md + prompt.yaml, self-contained)
├── docker/                     # images (web / collector / signer / paper-trade) + database migrations
├── docs/                       # arch (design) / plan / requirement / prototypes
├── qa/                         # black-box integration QA (standalone uv project)
└── docker-compose.yml          # full-stack orchestration (dev & prod base)
```

## Documentation

- [docs/arch/](./docs/arch/) — architecture design (10-part series)
- [docs/plan/development-plan.md](./docs/plan/development-plan.md) — development plan (source of truth for batch & status)

## License

MIT — see [LICENSE](./LICENSE).
