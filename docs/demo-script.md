# PayPilot AI — Hackathon Demonstration Guide

## 1. Prerequisites & Sandbox Account Requirements

To run a full live demonstration (PostgreSQL persistence, multi-agent LLM orchestration, product discovery, and PayPal Sandbox checkout), configure real credentials in `backend/.env` and `frontend/.env`:

- **PostgreSQL 15+**: Running database instance accessible via `DATABASE_URL` in `backend/.env` with schema migrated (`alembic upgrade head`).
- **NVIDIA Nemotron API (`NVIDIA_API_KEY`, `NVIDIA_MODEL`)**: Required for the primary orchestrating agent (`PRIMARY_ORCHESTRATION`).
- **Mistral API (`MISTRAL_API_KEY`, `MISTRAL_MODEL`) & Groq API (`GROQ_API_KEY`, `GROQ_MODEL`)**: Used for structured option comparison (`STRUCTURED_ANALYSIS`) and fast classification/guardrail checks (`FAST_CLASSIFICATION`).
- **Channel3 API (`CHANNEL3_API_KEY`)**: Provides live product discovery metadata for `discovery_agent`.
- **PayPal Developer Sandbox**:
  - One Sandbox Business (merchant) app providing `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` in `backend/.env`, plus matching `VITE_PAYPAL_CLIENT_ID` in `frontend/.env` from the **same** Sandbox application.
  - `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com` (production `api-m.paypal.com` is blocked whenever `APP_ENV != "production"`).
  - `PAYPAL_WEBHOOK_ID` configured on the Sandbox webhook endpoint pointing to `/api/v1/webhooks/paypal` (via an HTTPS tunnel in local demos) for live webhook verification.
  - One PayPal Sandbox Personal (buyer) account email/password to sign in and authorize orders at PayPal checkout.

---

## 2. Startup Commands

1. **Start PostgreSQL and apply migrations** (inside `backend/`):
   ```powershell
   alembic upgrade head
   ```
2. **Start FastAPI Backend** (inside `backend/`):
   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. **Start React/Vite Frontend** (inside `frontend/`):
   ```powershell
   npm run dev
   ```
4. **Verify Integration Health Before Presenting**:
   - Open `http://localhost:8000/docs` or query `http://localhost:8000/api/v1/health`.
   - Open `/settings` inside the frontend UI and verify **Database**, **AI Providers (`nvidia_nemotron`, `mistral`, `groq`)**, **Channel3**, and **PayPal Sandbox** report healthy/configured status.

---

## 3. Live Demo Workflow & Presenter Script

### Step 1: Landing & Opening Experience (`/`)
- Load `http://localhost:5173`. Briefly highlight the PayPilot AI value proposition: an autonomous multi-agent commerce assistant with strict human-in-the-loop payment governance.

### Step 2: Account Creation & Spending Guardrails (`/register` or `/login`, `/settings`)
- Register a user on `/register` (password requires at least 8 characters with uppercase, lowercase, and a digit).
- Mention authentication security: Argon2id password hashing, JWT access tokens, and in-memory refresh token handling (never stored in `localStorage` or `sessionStorage`).
- Navigate to `/settings` to show per-transaction and daily spending limit configuration (`spending_limits`) plus live provider readiness.

### Step 3: Autonomous Multi-Agent Commerce Request (`/command-center`)
- Enter a natural-language shopping goal (e.g., `"Find wireless noise-cancelling headphones under $300"` with optional budget).
- Show the AI Orb state transitions (`Thinking` -> `Searching` -> `Analyzing` -> `Awaiting Approval`) alongside the real-time agent activity log (`orchestrator` coordinating intent parsing, product discovery, comparison, recommendation, and security/spending policy checks).
- Point out that **no payment order is created autonomously**: the workflow stops at `AWAITING_USER_APPROVAL`.

### Step 4: Comparison & Explicit Human Authorization (`/compare` -> `/checkout`)
- Open product comparison (`/compare`) or proceed directly from the recommendation card to `/checkout`.
- Review quantity, unit price, total amount, and spending-limit check inside `PaymentApproval`.
- Click **Authorize & Create PayPal Order** (`confirm_purchase=true`). Show the backend transitioning the workflow to `ORDER_CREATED` and creating a `PENDING_APPROVAL` PayPal Orders v2 checkout session.

### Step 5: PayPal Sandbox Authorization & Verified Capture (`/checkout/success`)
- Launch the PayPal Sandbox checkout URL, approve the purchase using the Sandbox Personal buyer account, and let PayPal redirect back to `/checkout/success?token=<PAYPAL_ORDER_ID>&PayerID=<PAYER_ID>`.
- Point out the cancellation safety path (`/checkout/cancel` leaves funds uncaptured if the user cancels on PayPal).
- Click **Capture Verified Payment** on `/checkout`. The backend calls PayPal Orders API v2 capture, records the decimal financial amount in `orders` and `transactions`, updates spend tracking, and advances status to `COMPLETED`.

### Step 6: Ledger & Audit Trail (`/transactions`, `/agents`, `/dashboard`)
- Show the completed payment and fee breakdown in `/transactions`, plus agent execution traces in `/agents` and cumulative spend metrics on `/dashboard`.

---

## 4. Known Limitations

- PayPal Orders v2 capture and webhook signature verification require internet connectivity to `https://api-m.sandbox.paypal.com` and valid Sandbox credentials (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_WEBHOOK_ID` for webhooks).
- Local development requires a running PostgreSQL instance (`DATABASE_URL`); without it, persistence endpoints fail explicitly with HTTP `503 DATABASE_NOT_CONFIGURED`.
- Webhook delivery from PayPal to `localhost:8000/api/v1/webhooks/paypal` during live local demos requires a public HTTPS forwarding tunnel (or direct signed payload replay for local verification).
- Live product search depends on Channel3 API availability; no fabricated product listings are substituted when unconfigured.

---

## 5. Backup Plan If External APIs Are Unavailable

If Wi-Fi drops or any external provider key/service fails during presentation:

1. **System Diagnostics Transparency**: Show `GET /api/v1/health` and the `/settings` diagnostics panel demonstrating explicit `NOT_CONFIGURED` / `FAILED` reporting with zero silent fallbacks or fake confirmations.
2. **Interactive API Contract & Architecture Walkthrough**: Demonstrate the auto-generated OpenAPI schema at `http://localhost:8000/docs` (29 documented paths) and DB migration schema in `backend/alembic/versions/0001_initial_schema.py` (10 PostgreSQL tables with `Numeric(12, 2)` financial fields).
3. **Automated Full-Flow Proof**: Run the backend and frontend test suites live in terminal to show full end-to-end validation with isolated mocked HTTP transports:
   ```powershell
   cd backend; python -m pytest -v
   cd frontend; npm test
   ```
   Show passing tests covering JWT rotation, spending-limit blocks, 7-agent workflow orchestration, idempotent PayPal order creation/capture, webhook replay protection, and `/checkout/success?token=...` return handling.
