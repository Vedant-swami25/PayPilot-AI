# PayPilot AI

**Autonomous AI Commerce Agent**

PayPilot AI is a multi-agent autonomous commerce platform powered by FastAPI, React, PostgreSQL, NVIDIA Nemotron, Mistral, Groq, and PayPal Orders API v2. Users describe what they want to buy in natural language, specialized AI agents discover and compare real catalog options against user spending policies, and checkout executes **only after explicit human approval** via PayPal.

![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-Frontend-646CFF?logo=vite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-SQLAlchemy_2.x-4169E1?logo=postgresql&logoColor=white)
![NVIDIA Nemotron](https://img.shields.io/badge/Primary_AI-NVIDIA_Nemotron-76B900?logo=nvidia&logoColor=white)
![PayPal Orders v2](https://img.shields.io/badge/Payments-PayPal_Orders_v2-00457C?logo=paypal&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?logo=tailwindcss&logoColor=white)

> **Project Status:** Production-hardened FastAPI backend, seven-agent orchestrator, PayPal Orders v2 payment workflow (including capture reconciliation and refunds), Alembic-managed Neon PostgreSQL schema (`0002_production_indexes`), and React/Vite frontend. Live external APIs (NVIDIA Nemotron, Mistral, Groq, Channel3 v1, Neon PostgreSQL, and PayPal Sandbox) require valid credentials in `backend/.env` and `frontend/.env`; switching to PayPal Live additionally requires setting `APP_ENV=production`, HTTPS origins, non-sandbox `PAYPAL_BASE_URL`, and live PayPal REST/Webhook credentials.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [Payment Workflow](#payment-workflow)
- [Security](#security)
- [Running Tests](#running-tests)
- [External Integrations and Limitations](#external-integrations-and-limitations)
- [Screenshots / Demo](#screenshots--demo)
- [Future Improvements](#future-improvements)
- [License and Contribution](#license-and-contribution)

---

## Overview

PayPilot AI turns natural-language shopping intents into auditable, policy-checked purchase workflows:

1. **Natural-Language Request:** The authenticated user submits a shopping goal, budget, and currency through the AI Command Center.
2. **Intent & Planning:** AI agents interpret the request, extract search constraints, and plan execution.
3. **Product Discovery:** The Discovery Agent queries the configured external product provider (`Channel3`) to retrieve matching products without fabricating listings.
4. **Comparison & Decision:** Products are compared deterministically on `Decimal` pricing and specifications, enriched with AI qualitative notes, and ranked against user preferences.
5. **Security Validation:** The Security Agent evaluates spending limits (per-transaction, daily, and monthly caps) and merchant risk posture.
6. **Explicit User Approval:** The workflow pauses at `AWAITING_USER_APPROVAL`. No PayPal order or charge can occur unless the user explicitly confirms the purchase.
7. **PayPal Checkout & Capture:** Upon user approval, the backend creates a PayPal Orders API v2 order, redirects or opens PayPal approval, and captures payment only after PayPal reports `APPROVED` status.
8. **Ledger & Audit Persistence:** Orders, transactions, fee breakdowns, webhook events, and agent execution traces are recorded in PostgreSQL.

---

## Key Features

### Implemented & Locally Verified (Mocked Transports / Unit & Integration Suites)
- **Natural-Language Shopping Interface:** Interactive orchestrator console (`/command-center`) with workflow session history and AI Orb status animations.
- **Multi-Agent Orchestration:** Seven specialized backend agents coordinated by `CommerceOrchestrator`, with resumable state and mid-flight cancellation.
- **Product Discovery & Comparison:** Catalog search (`/discovery`, `/products/:productId`) and side-by-side `Decimal` comparison matrix (`/compare`).
- **Purchase Security Validation:** Deterministic enforcement of `max_single_transaction`, `daily_limit`, and `monthly_limit` rules before payment creation.
- **Explicit Payment Approval:** Server-enforced human consent gate (`confirm_purchase=true`) and UI consent guardrails (`PaymentApproval` / `PayPalCheckout`).
- **PayPal Checkout Integration:** PayPal Orders v2 order creation, return-route handling (`/checkout/success` and `/checkout/cancel`), backend-verified capture, and uncaptured order cancellation.
- **Transaction History & Agent Monitoring:** Filterable transaction ledger (`/transactions`, `/transactions/:transactionId`), summary analytics (`/dashboard`), and agent activity audit logs (`/agents`).
- **Authentication & Route Protection:** Argon2id password hashing, JWT access tokens, refresh token rotation with reuse revocation, and protected client routes.
- **Dark / Light Theme Support:** Persisted UI theme preference (`paypilot_theme`, defaulting to `dark`) toggled from Settings (`/settings`).

### Features Requiring External Credentials & Live Setup
- Live LLM inference via NVIDIA Nemotron, Mistral, and Groq APIs.
- Live product search via Channel3 (`CHANNEL3_API_KEY`).
- Live PostgreSQL persistence via `DATABASE_URL` and Alembic migrations.
- Live PayPal Sandbox checkout approval, payment capture, and signed webhook delivery (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, `VITE_PAYPAL_CLIENT_ID`).

---

## System Architecture

### Seven-Agent Architecture

PayPilot AI coordinates seven backend agents inside [`backend/app/agents/`](backend/app/agents/):

1. **Lead Agent (`lead_agent.py` — NVIDIA Nemotron):** Primary reasoning and orchestration agent responsible for parsing natural-language shopping intents, extracting budgets/currencies, requesting clarifications when needed, and synthesizing final user-facing recommendations.
2. **Discovery Agent (`discovery_agent.py` — Groq + Channel3):** Refines search queries using fast inference (`FAST_CLASSIFICATION`) and queries verified external product feeds. Never invents product records when providers are unconfigured or return empty results.
3. **Comparison Agent (`comparison_agent.py` — Deterministic + Mistral):** Computes exact `Decimal` price spreads, percentage deltas, and budget compliance, optionally enriched with structured qualitative pros/cons (`STRUCTURED_ANALYSIS`).
4. **Decision Agent (`decision_agent.py` — NVIDIA Nemotron):** Ranks retrieved options strictly from verified product IDs and generates structured trade-off reasoning.
5. **Security Agent (`security_agent.py` — Deterministic + Mistral):** Validates merchant posture, transaction risk, and user spending limits (`BLOCKED_BY_SECURITY` prevents checkout execution). Remains advisory/preventive and never authorizes funds itself.
6. **Payment Agent (`payment_agent.py`):** Prepares backend-validated PayPal Orders v2 checkout requests only after explicit human approval.
7. **Monitoring Agent (`monitoring_agent.py`):** Records agent execution telemetry, workflow step durations, errors, and audit trails.

### LLM Routing Policy

Implemented in [`backend/app/llm/router.py`](backend/app/llm/router.py):

- **NVIDIA Nemotron (`PRIMARY_ORCHESTRATION`):** Required primary model for Lead Agent orchestration/synthesis and Decision Agent selection. **Never silently replaced** by Mistral or Groq if unconfigured or unavailable.
- **Mistral (`STRUCTURED_ANALYSIS`):** Supporting specialist for structured comparison notes and advisory security analysis.
- **Groq (`FAST_CLASSIFICATION`):** Fast supporting inference for lightweight tasks such as search query refinement.

### Architecture Flow

```mermaid
flowchart LR
    U["User Browser"] --> FE["React + Vite Frontend"]
    FE -->|REST API + JWT| API["FastAPI Backend"]
    API --> ORCH["Commerce Orchestrator"]

    subgraph Agents["Seven-Agent Pipeline"]
        LEAD["Lead Agent"]
        DISC["Discovery Agent"]
        COMP["Comparison Agent"]
        DEC["Decision Agent"]
        SEC["Security Agent"]
        PAYA["Payment Agent"]
        MON["Monitoring Agent"]
    end

    ORCH --> LEAD
    ORCH --> DISC
    ORCH --> COMP
    ORCH --> DEC
    ORCH --> SEC
    ORCH --> PAYA
    ORCH --> MON

    subgraph LLMs["LLM Router (No Silent Primary Fallback)"]
        NEM["NVIDIA Nemotron (Primary)"]
        MIS["Mistral (Structured Analysis)"]
        GRQ["Groq (Fast Classification)"]
    end

    LEAD --> NEM
    DEC --> NEM
    COMP --> MIS
    SEC --> MIS
    DISC --> GRQ

    DISC -->|Product Feed| CH3["Channel3 API"]
    PAYA -->|Orders v2 + Webhooks| PP["PayPal Sandbox API"]
    API --> DB[("PostgreSQL Database")]
    ORCH --> DB
```

---

## Technology Stack

Verified directly against [`backend/requirements.txt`](backend/requirements.txt), [`backend/Dockerfile`](backend/Dockerfile), and [`frontend/package.json`](frontend/package.json):

- **Frontend:** React (`^18.3.1`), Vite, React Router DOM (`^7.2.0`), Tailwind CSS (`^3.4.17`), PostCSS, Autoprefixer, TanStack React Query (`^5.66.0`), Axios (`^1.7.9`), Zustand (`^5.0.3`), Framer Motion (`^12.4.7`), GSAP (`^3.12.7`), Recharts (`^2.15.1`), Lucide React (`^0.475.0`).
- **Backend:** Python (`3.11-slim` target in Docker; compatible with 3.10+), FastAPI (`>=0.115.0`), Uvicorn (`>=0.32.0`), Pydantic v2 (`>=2.9.0`), `pydantic-settings` (`>=2.6.0`), `email-validator`, `python-multipart`, `httpx`, `tenacity`, `structlog`, `python-dotenv`.
- **Database and Migrations:** PostgreSQL, SQLAlchemy (`>=2.0.35`, async), Alembic (`>=1.14.0`), `psycopg[binary]` (`>=3.2.0`), `greenlet` (`>=3.1.0`), `aiosqlite` (used only for isolated unit test fixtures).
- **AI / LLM Integrations:** NVIDIA Nemotron (`integrate.api.nvidia.com/v1`), Mistral (`api.mistral.ai/v1`), Groq (`api.groq.com/openai/v1`), accessed via `httpx`.
- **Payment Integration:** PayPal Developer REST API (OAuth2, Orders API v2, Webhook Signature Verification) and `@paypal/react-paypal-js` (`^8.7.0`).
- **Authentication and Security:** `PyJWT` (`>=2.9.0`), `argon2-cffi` (`>=23.1.0`), `bcrypt` (`>=4.0.1`), `slowapi` (`>=0.1.9`).
- **Testing and Development Tools:** `pytest` (`>=8.3.0`), `pytest-asyncio` (`>=0.24.0`), Vitest (`^3.0.7`), `@testing-library/react` (`^16.2.0`), `@testing-library/jest-dom` (`^6.6.3`), `jsdom` (`^26.0.0`).

---

## Repository Structure

```text
PayPilot-AI/
├── .env.example
├── .gitignore
├── LICENSE                         # Empty placeholder (license not yet specified)
├── README.md
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── alembic/
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── app/
│   │   ├── main.py                 # FastAPI app, middleware, health checks, exception handlers
│   │   ├── agents/                 # Orchestrator + 7 specialized agents
│   │   ├── api/routes/             # auth, agents, commerce, products, payments, transactions, webhooks
│   │   ├── core/                   # config, database, logging (redaction), security
│   │   ├── integrations/
│   │   │   ├── paypal/             # client, orders, capture, webhooks, schemas
│   │   │   └── products/           # channel3, provider abstraction
│   │   ├── llm/                    # nemotron, mistral, groq, router, prompts/
│   │   ├── models/                 # SQLAlchemy models (10 database tables)
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/               # auth, audit, commerce, payment, product, transaction services
│   │   └── utils/                  # currency, helpers, validators
│   └── tests/                      # conftest, test_agents, test_commerce, test_payments, test_webhooks
├── database/
│   ├── migrations/
│   └── seed/
│       └── products.json           # Empty placeholder file (0 bytes)
├── docs/
│   ├── agent-workflow.md           # Empty placeholder file
│   ├── api-reference.md            # Empty placeholder file
│   ├── architecture.md             # Empty placeholder file
│   ├── demo-script.md              # Hackathon live demo guide & backup plan
│   └── paypal-integration.md       # Empty placeholder file
└── frontend/
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── vite.config.js
    ├── public/
    └── src/
        ├── App.jsx
        ├── main.jsx
        ├── app/                    # App.jsx, providers.jsx, routes.jsx
        ├── components/             # agents/, animations/, chat/, commerce/, layout/, payments/, ui/
        ├── context/                # AuthContext
        ├── hooks/                  # React Query & auth hooks
        ├── pages/                  # Landing, Login, Register, Dashboard, AICommandCenter, Checkout, etc.
        ├── services/               # Axios client + resource API wrappers
        ├── store/                  # Zustand app & theme store
        ├── styles/
        ├── test/                   # Vitest + Testing Library suite (app.test.jsx)
        └── utils/
```

---

## Prerequisites

- **Python:** `3.11+` recommended ([`backend/Dockerfile`](backend/Dockerfile) uses `python:3.11-slim`; local tests also pass on Python `3.10.11`).
- **Node.js and npm:** LTS Node.js (`v20+` / verified locally on `v24.19.0`) and `npm` (`10.x`).
- **PostgreSQL:** PostgreSQL database instance (local service or container) reachable via `DATABASE_URL`.
- **Git:** Standard Git client.
- **External API Accounts (Required for Live Execution):**
  - NVIDIA API (`NVIDIA_API_KEY`, `NVIDIA_MODEL`)
  - Mistral API (`MISTRAL_API_KEY`, `MISTRAL_MODEL`)
  - Groq API (`GROQ_API_KEY`, `GROQ_MODEL`)
  - Channel3 Product Discovery (`CHANNEL3_API_KEY`)
  - PayPal Developer Sandbox Business App (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`) and Sandbox Personal buyer account

---

## Installation and Setup

### 1. Backend Setup

```bash
# 1. Clone the repository and navigate to backend/
git clone https://github.com/Vedant-swami25/PayPilot-AI.git
cd PayPilot-AI/backend

# 2. Create and activate a Python virtual environment
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Create backend/.env from template and populate your credentials
cp .env.example .env

# 5. Ensure PostgreSQL is running and DATABASE_URL is set, then run migrations
python -m alembic upgrade head

# 6. Start the FastAPI server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup

Open a second terminal:

```bash
# 1. Navigate to frontend/
cd PayPilot-AI/frontend

# 2. Install npm dependencies
npm install

# 3. Create frontend/.env from template and set matching API / PayPal Sandbox Client ID
cp .env.example .env

# 4. Start the Vite development server (default port 5173)
npm run dev
```

Open `http://localhost:5173` in your browser and verify backend Swagger docs at `http://localhost:8000/docs`.

---

## Environment Variables

All environment variables below are taken verbatim from [`backend/.env.example`](backend/.env.example) and [`frontend/.env.example`](frontend/.env.example).

### Security Rules for Environment Configuration
- **Backend Secrets Stay on the Server:** `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, `NVIDIA_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `CHANNEL3_API_KEY`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_WEBHOOK_ID` must reside strictly in `backend/.env` and must never be committed or exposed to clients.
- **Never Expose `PAYPAL_CLIENT_SECRET` to the Frontend:** Only the public `VITE_PAYPAL_CLIENT_ID` belongs in `frontend/.env`.
- **`VITE_` Variables Are Public:** Vite bundles all `VITE_*` variables into client JavaScript shipped to the browser—never place private secrets in `frontend/.env`.
- **Use PayPal Sandbox for Development:** `APP_ENV != "production"` explicitly forbids `api-m.paypal.com`; keep `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com` during development and testing.
- **Test Product Fixtures vs. Real Data:** Keeping `ENABLE_TEST_PRODUCT_FIXTURES=false` ensures products come strictly from the configured Channel3 provider. Enabling `ENABLE_TEST_PRODUCT_FIXTURES=true` (development only) returns clearly tagged `TEST DATA` fixtures and must not be confused with real merchant inventory.

### Backend (`backend/.env.example`)

| Group | Variable | Example / Default | Requirement | Purpose |
|---|---|---|---|---|
| **Application** | `APP_NAME` | `PayPilot AI` | Optional | Service title shown in OpenAPI & health responses. |
| | `APP_ENV` | `development` | Optional (`development` / `production`) | Controls strict production checks & blocks live PayPal outside `production`. |
| | `DEBUG` | `true` | Optional | Enables development debug logging behavior. |
| | `CORS_ORIGINS` | `http://localhost:5173` | Required if custom frontend host | Comma-separated origins or JSON list allowed for CORS (`*` forbidden in production). |
| | `DEFAULT_CURRENCY` | `USD` | Optional | Default 3-letter ISO-4217 currency code. |
| | `RATE_LIMIT_AUTH_REQUESTS` | `10` | Optional | Maximum auth requests allowed per window. |
| | `RATE_LIMIT_AUTH_WINDOW_SECONDS` | `60` | Optional | Sliding window duration (seconds) for auth rate limits. |
| **Database** | `DATABASE_URL` | `postgresql+psycopg://user:password@localhost:5432/paypilot` | **Required** for persistence & Alembic | PostgreSQL SQLAlchemy connection URL (`503 DATABASE_NOT_CONFIGURED` if blank). |
| **JWT & Auth** | `SECRET_KEY` | `your_32plus_char_app_secret` | **Required** in production (>=32 chars); ephemeral in dev | Application cryptographic secret key. |
| | `JWT_SECRET_KEY` | `your_32plus_char_jwt_secret` | **Required** in production (>=32 chars); ephemeral in dev | Signing key for JWT access and refresh tokens. |
| | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Optional | Access token lifetime in minutes. |
| | `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Optional | Refresh token lifetime in days. |
| **NVIDIA Nemotron** | `NVIDIA_API_KEY` | `your_nvidia_api_key` | **Required** for Lead & Decision agents | API key for primary NVIDIA Nemotron orchestration. |
| | `NVIDIA_MODEL` | `nvidia/nemotron-model-id` | **Required** for Lead & Decision agents | Nemotron model identifier served by NVIDIA endpoint. |
| | `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | Optional override | OpenAI-compatible NVIDIA inference base URL. |
| **Mistral** | `MISTRAL_API_KEY` | `your_mistral_api_key` | Optional (required for Mistral enrichment) | API key for Mistral comparison/security analysis. |
| | `MISTRAL_MODEL` | `mistral-model-id` | Optional (required with `MISTRAL_API_KEY`) | Mistral model identifier. |
| | `MISTRAL_BASE_URL` | `https://api.mistral.ai/v1` | Optional override | Mistral API base URL. |
| **Groq** | `GROQ_API_KEY` | `your_groq_api_key` | Optional (required for Groq refinement) | API key for fast lightweight classification/refinement. |
| | `GROQ_MODEL` | `groq-model-id` | Optional (required with `GROQ_API_KEY`) | Groq model identifier. |
| | `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Optional override | Groq OpenAI-compatible API base URL. |
| | `LLM_TIMEOUT_SECONDS` | `30` | Optional | Per-request LLM HTTP timeout in seconds. |
| | `AGENT_TIMEOUT_SECONDS` | `45` | Optional | Per-agent execution timeout in seconds. |
| **Product Discovery** | `CHANNEL3_API_KEY` | `your_channel3_api_key` | **Required** for live product search | API key for Channel3 v1 product catalog queries. |
| | `CHANNEL3_BASE_URL` | `https://api.trychannel3.com/v1` | Optional override | Channel3 API base URL (defaults to `v1`). |
| | `PRODUCT_CACHE_TTL_SECONDS` | `120` | Optional | In-memory TTL cache duration for normalized Channel3 results. |
| | `ENABLE_TEST_PRODUCT_FIXTURES` | `false` | Optional (forbidden in `production`) | Explicitly toggles tagged `TEST DATA` fixtures for non-production local testing. |
| **Operational Hardening** | `FRONTEND_BASE_URL` | `http://localhost:5173` | **Required** (HTTPS in `production`) | Canonical frontend origin used for default PayPal return/cancel URLs. |
| | `MAX_REQUEST_BODY_BYTES` | `1048576` | Optional (`>= 1024`) | Maximum allowed JSON request payload size (`413` on overflow). |
| | `RATE_LIMIT_API_REQUESTS` | `120` | Optional | General per-IP API rate limit window request cap (`429` when exceeded). |
| | `RATE_LIMIT_API_WINDOW_SECONDS` | `60` | Optional | Sliding window duration for general API rate limiting. |
| | `REQUEST_TIMEOUT_SECONDS` | `60` | Optional | Global HTTP request deadline (`504` on timeout). |
| | `EXPOSE_API_DOCS_IN_PROD` | `false` | Optional | Exposes `/docs`, `/redoc`, and `/openapi.json` when `APP_ENV=production`. |
| **PayPal Sandbox** | `PAYPAL_CLIENT_ID` | `your_paypal_sandbox_client_id` | **Required** for PayPal Orders v2 | PayPal Sandbox REST app Client ID. |
| | `PAYPAL_CLIENT_SECRET` | `your_paypal_sandbox_client_secret` | **Required** for PayPal Orders v2 | PayPal Sandbox REST app Secret (server-only). |
| | `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` | **Required** | PayPal REST API base URL (use Sandbox for dev). |
| | `PAYPAL_WEBHOOK_ID` | `your_paypal_webhook_id` | **Required** for webhook signature verification | Webhook ID from PayPal Developer Dashboard. |

### Frontend (`frontend/.env.example`)

| Group | Variable | Example / Default | Requirement | Purpose |
|---|---|---|---|---|
| **Frontend API** | `VITE_API_BASE_URL` | `http://localhost:8000` | **Required** | Base URL for Axios requests to the FastAPI backend. |
| **Frontend PayPal** | `VITE_PAYPAL_CLIENT_ID` | `your_paypal_sandbox_client_id` | Optional (triggers JS SDK vs redirect mode) | Public Sandbox Client ID from the **same** PayPal app as `PAYPAL_CLIENT_ID`. |

---

## API Documentation

When the backend is running, interactive API documentation is served automatically at:
- **Swagger UI:** [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **ReDoc:** [`http://localhost:8000/redoc`](http://localhost:8000/redoc)

Verified FastAPI endpoint groups and routes:

| Group | Method(s) | Path | Description |
|---|---|---|---|
| **Health & Telemetry** | `GET` | `/health` | Basic service liveness status. |
| | `GET` | `/ready`, `/api/v1/ready` | Container/orchestrator readiness probe (`503` if PostgreSQL unreachable). |
| | `GET` | `/api/v1/metrics` | Authenticated HTTP, AI provider token/latency/circuit, and PayPal/Channel3 counters. |
| | `GET` | `/api/v1/health` | Aggregate integration status (`database`, `ai`, `paypal`, `product_discovery`). |
| | `GET` | `/api/v1/health/database` | PostgreSQL configuration & connectivity check. |
| | `GET` | `/api/v1/health/ai` | Per-provider AI readiness (`nvidia_nemotron`, `mistral`, `groq`; supports `?verify=true`). |
| | `GET` | `/api/v1/health/paypal` | PayPal environment & OAuth2 credential check (supports `?verify=true`). |
| **Authentication** | `POST` | `/api/v1/auth/register` | Register a new user and provision default `spending_limits`. |
| | `POST` | `/api/v1/auth/login` | Issue JWT access token + refresh token (rate-limited). |
| | `POST` | `/api/v1/auth/refresh` | Rotate refresh token and detect revoked-token reuse. |
| | `POST` | `/api/v1/auth/logout` | Revoke active refresh token session. |
| | `GET`, `PUT` | `/api/v1/auth/me` | Retrieve or update authenticated user profile & spending limits. |
| **Agents** | `POST` | `/api/v1/agents/run` | Trigger the multi-agent commerce workflow. |
| | `GET` | `/api/v1/agents/status/{workflow_id}` | Inspect workflow execution status and agent trace. |
| | `POST` | `/api/v1/agents/cancel/{workflow_id}` | Cancel an active workflow. |
| | `GET` | `/api/v1/agents/activity` | Retrieve user-scoped agent execution audit logs. |
| **Commerce** | `POST` | `/api/v1/commerce/request` | Submit natural-language shopping request through the 7-agent orchestrator. |
| | `GET` | `/api/v1/commerce/workflows/{workflow_id}` | Retrieve full workflow state, products, comparison, recommendation, and risk posture. |
| | `POST` | `/api/v1/commerce/workflows/{workflow_id}/approve` | Explicitly authorize purchase (`confirm_purchase=true`) and prepare PayPal order. |
| | `GET` | `/api/v1/commerce/history` | Paginated user workflow history. |
| **Products** | `GET` | `/api/v1/products/search` | Search products via the configured discovery provider. |
| | `GET` | `/api/v1/products/{product_id}` | Fetch single product metadata. |
| | `POST` | `/api/v1/products/compare` | Compare multiple products using deterministic `Decimal` calculations. |
| **Payments** | `POST` | `/api/v1/payments/create-order` | Create an authorized PayPal Orders v2 order using backend-computed totals. |
| | `GET` | `/api/v1/payments/{payment_id}` | Inspect (and optionally `?sync=true` sync) a user-owned payment order. |
| | `POST` | `/api/v1/payments/{payment_id}/capture` | Capture an `APPROVED` PayPal order via PayPal Orders API v2 (with uncertain-timeout reconciliation). |
| | `POST` | `/api/v1/payments/{payment_id}/refund` | Refund a `COMPLETED` PayPal capture via PayPal Payments v2. |
| | `POST` | `/api/v1/payments/{payment_id}/cancel` | Cancel an uncaptured order safely. |
| **Transactions** | `GET` | `/api/v1/transactions` | List user-owned transactions. |
| | `GET` | `/api/v1/transactions/summary` | Aggregate spend analytics and transaction counts. |
| | `GET` | `/api/v1/transactions/{transaction_id}` | View detailed transaction record & receipt fields. |
| **PayPal Webhooks** | `POST` | `/api/v1/webhooks/paypal` | Receive and cryptographically verify PayPal payment webhooks. |

---

## Payment Workflow

PayPilot AI enforces a strict server-side payment lifecycle:

1. **Product Selection:** User selects a discovered or recommended product (`product_id` and `quantity`).
2. **Purchase Validation:** Backend validates product availability, currency compatibility, and calculates unit/total `Decimal` amounts (`Numeric(12, 2)`) server-side—client-supplied prices are never trusted as authoritative.
3. **Security Checks:** Backend checks `spending_limits` (`max_single_transaction`, `daily_limit`, `monthly_limit`) and workflow security posture; any violation returns `403` / `BLOCKED_BY_SECURITY`.
4. **Explicit User Approval:** User must explicitly confirm purchase intent (`confirm_purchase=true` and UI confirmation checkbox).
5. **PayPal Order Creation:** Backend invokes PayPal Orders API v2 (`POST /v2/checkout/orders`) with idempotency keys and stores the order in `PENDING_APPROVAL` status.
6. **User Checkout & Approval:** User opens PayPal's approval link (or Sandbox JS SDK flow), signs in with a Sandbox Personal buyer account, and returns to `/checkout/success?token=<paypal_order_id>&PayerID=<payer_id>` (or `/checkout/cancel` to abort without capture).
7. **Payment Capture:** Clicking **Capture Verified Payment** sends `POST /api/v1/payments/{payment_id}/capture`. The backend verifies that PayPal reports `APPROVED` status and matching amount/currency integrity before capturing.
8. **Webhook Verification:** PayPal sends asynchronous lifecycle events (`PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, etc.) to `POST /api/v1/webhooks/paypal`, which verifies signatures via PayPal's `/v1/notifications/verify-webhook-signature` API and deduplicates event IDs.
9. **Transaction Persistence:** Orders, fee breakdowns, capture references, and audit logs are committed transactionally in PostgreSQL.

### Sandbox vs. Production & Merchant Checkout Scope
- **Sandbox vs. Production:** Set `APP_ENV=development` and `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com` for Sandbox demos. The backend configuration validator raises `ConfigurationError` if `api-m.paypal.com` is used whenever `APP_ENV != "production"`.
- **Merchant Scope Disclaimer:** Discovering a product from an external search catalog (such as Channel3) surfaces product metadata and merchant information for comparison and agent reasoning, **not universal direct checkout integration with every third-party storefront**. In PayPilot AI, payment creation and capture are executed against the configured PayPal Orders API v2 merchant/application account.

---

## Security

Implemented security controls verified in the backend and frontend codebase:

- **Argon2id Password Hashing:** Passwords hashed and verified via `argon2-cffi` (`PasswordHasher`) with minimum complexity validation.
- **JWT Authentication:** Short-lived signed JWT access tokens (`PyJWT`) validated on every protected API endpoint.
- **Refresh Token Rotation & Reuse Protection:** Refreshing rotates tokens atomically (`POST /api/v1/auth/refresh`); reusing an already-revoked refresh token triggers `REFRESH_TOKEN_REUSE_DETECTED` and revokes the entire token family.
- **Client Refresh Token Isolation:** Frontend stores refresh tokens in memory (`tokenVault`), never in `localStorage` or `sessionStorage`.
- **Spending-Limit Enforcement:** Server-side verification of per-transaction, daily, and monthly spend limits prior to order creation and capture.
- **Backend-Calculated Payment Amounts:** Totals are computed in `Decimal` from persisted product records on the server; client mismatch raises `409 Conflict`.
- **Strict Ownership Validation:** Workflows, orders, and transactions filter strictly by authenticated `user_id`.
- **Payment Idempotency:** Workflow approval and order creation use idempotency keys so retries/resumptions return the existing order instead of double-charging.
- **PayPal Webhook Signature Verification:** Rejects forged or unverifiable webhook calls when headers/signatures fail PayPal verification; deduplicates processed `webhook_events`.
- **Secret Redaction:** Structured logging (`backend/app/core/logging.py`) redacts sensitive dictionary keys (`secret`, passwords, tokens) as well as `Bearer` and `Basic` authorization headers.
- **Explicit Human Purchase Approval:** Agents cannot bypass `AWAITING_USER_APPROVAL` to trigger PayPal charges autonomously.

---

## Running Tests

### Backend Suite

```bash
cd backend
python -m pytest -v
```

**Latest Verified Local Result (`backend/`):**
- **`38 passed, 1 skipped`** (`39` tests collected):
  - Covers Nemotron primary-model enforcement (no silent fallback), structured JSON parse repair, provider circuit breakers, multi-agent workflow orchestration & cancellation, monthly/daily/single-transaction spending limits, SSRF & prompt sanitization guards, Channel3 v1 normalization/pagination/429-backoff/TTL caching, production `Settings` security rejection checks, security headers, body-size limits (`413`), `/ready` & authenticated `/api/v1/metrics`, PayPal order creation/capture reconciliation/refunds/cancellation, and webhook signature/idempotency tests.
  - **`1 skipped`:** `test_manual_paypal_sandbox_oauth_connectivity` skips in default isolated test mode unless `RUN_LIVE_PAYPAL_TESTS=true` is explicitly set.

### Frontend Suite & Build

```bash
cd frontend
npm test
npm run build
```

**Latest Verified Local Result (`frontend/`):**
- **Vitest (`npm test`):** **`12 passed`** across `2` test files (`src/test/app.test.jsx` and `src/test/production.test.jsx`), covering `tokenVault`, `AIOrb`, `OpeningIntro`, `ProtectedRoute`, `ProductComparison`, `PaymentApproval` & `PayPalCheckout` security/capture guards, `Login` & `Register` password validation, and `TransactionDetails` two-step refund confirmation.
- **Production Build (`npm run build`):** Cleanly split Vite chunks (`react`, `motion`, `query`, `charts`, `index`) under `frontend/dist/`.

---

## Production Deployment & Operations

### Database Migrations, Backup, and Rollback (Neon / PostgreSQL)

```bash
cd backend
python -m alembic upgrade head
python -m alembic check
```

- **Current Head Revision:** `0002_production_indexes` (adds composite query indexes on `orders`, `transactions`, `commerce_workflows`, and `audit_logs`, plus `CheckConstraint` invariants).
- **Backup Before Schema Changes:**
  ```bash
  pg_dump "$DATABASE_URL" --format=custom --no-owner --file=paypilot_backup_$(date +%F).dump
  ```
- **Rollback Last Revision:**
  ```bash
  cd backend && python -m alembic downgrade -1
  ```

### Container Builds (`backend/Dockerfile` & `frontend/Dockerfile`)

```bash
# Backend FastAPI container (runs behind HTTPS reverse proxy with graceful shutdown)
docker build -t paypilot-backend ./backend

# Frontend Vite + Nginx SPA container (SPA fallback, gzip, cache & security headers)
docker build \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com \
  --build-arg VITE_PAYPAL_CLIENT_ID=<YOUR_PAYPAL_CLIENT_ID> \
  -t paypilot-frontend ./frontend
```

### Switching from PayPal Sandbox to Live Production

1. Set `APP_ENV=production` and `DEBUG=false` in backend environment config.
2. Provide production `DATABASE_URL` (PostgreSQL with SSL), HTTPS `CORS_ORIGINS`, HTTPS `FRONTEND_BASE_URL`, `PAYPAL_BASE_URL=https://api-m.paypal.com`, and **Live** PayPal REST (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`) and matching frontend `VITE_PAYPAL_CLIENT_ID`.
3. Register `https://api.yourdomain.com/api/v1/webhooks/paypal` in the PayPal Live Developer Dashboard (`CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.CAPTURE.REVERSED`).
4. Verify `GET /ready` returns `200 {"status": "READY"}` and `GET /api/v1/health?verify=true` confirms live database, AI, and PayPal OAuth health.

---

## External Integrations and Limitations

- **PostgreSQL:** Requires a running PostgreSQL instance and valid `DATABASE_URL`; without it, `/ready` reports `503 NOT_READY` and persistence endpoints fail cleanly with `503`.
- **NVIDIA Nemotron API:** Requires `NVIDIA_API_KEY` and `NVIDIA_MODEL`. Because Nemotron is strictly enforced as primary orchestrator without silent fallback, workflow execution reports configuration errors until set.
- **Mistral & Groq APIs:** Supporting specialist models (`MISTRAL_API_KEY`/`MISTRAL_MODEL`, `GROQ_API_KEY`/`GROQ_MODEL`) used for comparison/security enrichment and query refinement.
- **Channel3 Product Provider:** Requires `CHANNEL3_API_KEY` for live product catalog search (`https://api.trychannel3.com/v1`).
- **PayPal Checkout Scope:** Current credentials run against **PayPal Sandbox** (`https://api-m.sandbox.paypal.com`); PayPal Live real-money settlement has not been exercised and requires Live PayPal Business approval and HTTPS domain registration.
- **Merchant Checkout Scope:** Channel3 surfaces external catalog items for discovery/comparison, while payment orders settle against PayPal Sandbox merchant credentials rather than universal direct third-party merchant APIs.
- **In-Memory Rate Limiter & Cache Scope:** The sliding-window rate limiter and product TTL cache are process-local (`memory`), suitable for single-instance deployment; multi-replica horizontal scaling should front rate limits and caching with Redis.
- **Browser Visual E2E Coverage:** Vitest/JSDOM covers component/page workflows, while automated cross-browser Playwright responsive checks were not executed in this environment.

---

## Screenshots / Demo

See [`docs/demo-script.md`](docs/demo-script.md) for the step-by-step live demonstration workflow, Sandbox prerequisites, and offline backup plan.

---

## Future Improvements

*(Planned enhancements — not currently implemented)*

- Populate standalone technical references in `docs/architecture.md`, `docs/agent-workflow.md`, `docs/api-reference.md`, and `docs/paypal-integration.md`.
- Add Redis-backed distributed rate limiting and product search caching for multi-replica backend clusters.
- Integrate Server-Sent Events (SSE) or WebSockets for token-by-token streaming updates in the AI Command Center.
- Add automated Playwright end-to-end visual regression tests across mobile, tablet, and desktop viewports.

---

## License and Contribution

- **License:** A `LICENSE` file exists at the repository root; review before commercial redistribution.
- **Contributing:** Issues and pull requests improving test coverage, multi-agent prompts, or documentation are welcome—never commit `.env` files, API keys, or PayPal credentials.
