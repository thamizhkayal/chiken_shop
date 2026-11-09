# Cluck Club

A single-shop loyalty platform: customers earn integer points through activities and redeem points for raw chicken in person. The application is a modular monolith with a Next.js web app, FastAPI API, and PostgreSQL database.

## Architecture

- **Frontend:** Next.js App Router, React, TypeScript, and Tailwind CSS. Current Phase 1 screens use CSS motion and native fetch; Framer Motion and TanStack Query are deferred until the package registry is reachable so the starter lockfile remains installable.
- **Backend:** FastAPI routers call service-layer business logic and SQLAlchemy 2.0 repositories/models. Pydantic validates request and response data.
- **Data:** PostgreSQL with Alembic-managed schema. Authentication uses Argon2id password hashes, short-lived JWT access cookies, and rotating, revocable refresh JWTs.
- **Local runtime:** Docker Compose starts the frontend, API, and PostgreSQL. There are no microservices or tenant boundaries.

## Planned project structure

```text
frontend/
  app/                 # Landing, login, registration, and customer app pages
  public/
  Dockerfile
backend/
  app/
    api/v1/             # Versioned HTTP routers
    core/               # Settings, DB sessions, password/JWT and rate limiting
    models/             # SQLAlchemy entities
    schemas/            # Pydantic API contracts
    repositories/       # Database queries
    services/           # Authentication and business logic
  alembic/              # Versioned database migrations
  tests/
docker-compose.yml
```

## Planned relational schema

All tables use primary keys, foreign keys, created/updated timestamps as appropriate, and indexes on common ownership/status/date lookups. Phase 1 creates identity/authentication tables; the remaining tables are introduced alongside their features.

| Table | Purpose / important constraints |
|---|---|
| `roles` | Unique `customer`, `staff`, and `admin` names |
| `users` | UUID id; unique nullable email and phone; at least one contact; role FK; Argon2 password hash |
| `staff_profiles` | One-to-one staff metadata keyed by user FK |
| `refresh_sessions` | Refresh JWT `jti`, user FK, expiry/revocation/replacement metadata |
| `wallets` | One per customer; integer cached balance with non-negative check |
| `wallet_transactions` | Append-only integer ledger, type, reference, description, customer FK; indexed by wallet/date |
| `spin_configurations` | Admin-authored integer rewards/probabilities, active window, audit actor |
| `spin_reward_options` | Integer reward values and probabilities in basis points; probabilities total 10,000 |
| `spin_sessions` | Server-selected spin results by user and business-local day; the normal limit is one, with a configurable development-only test allowance |
| `puzzle_questions` | Daily puzzle prompt, answer verifier, integer reward and active window |
| `puzzle_attempts` | One recorded answer per user/question, including incorrect answers |
| `daily_activity_limits` | Per-user/business-day total activity points earned |
| `redemption_requests` | User, reserved integer points/grams, lifecycle status and timestamps |
| `redemption_qr_tokens` | Hashed one-time token, redemption FK, expiry and consumed timestamp |
| `admin_audit_logs` | Actor, action, entity reference, safe before/after details and timestamp |

`1 point = 1 gram` is a fixed integer conversion. Redemption amounts must be at least 100 points and cannot exceed available points.

## Wallet and redemption transaction flow

1. Spin and puzzle services validate eligibility, one-per-day/submission constraints, and the shared activity cap inside a database transaction.
2. Wallet operations lock the wallet row (`SELECT ... FOR UPDATE` on PostgreSQL), verify the cached balance against the ledger sum, append a signed integer ledger entry, update the cached balance, and commit together. Transaction references are unique per transaction type to reject duplicate operations.
3. A redemption locks the wallet, checks `amount >= 100` and sufficient funds, writes a negative reservation entry and a `RESERVED` request, and creates a cryptographically random opaque QR token whose hash is stored. The QR contains only the opaque token.
4. An authenticated staff/admin scan locks the redemption/token, checks status and expiry, consumes the token once, validates fulfilled grams do not exceed the reservation, and records the fulfillment and audit event atomically.
5. Expiry/cancellation locks the same records, transitions once, and writes a compensating refund ledger entry. Repeated and concurrent requests are rejected or return the original result through idempotency.

Phase 2 provides the wallet summary (`GET /api/v1/wallet`), paginated customer transaction history (`GET /api/v1/wallet/transactions`), and the backend ledger service. A successful password login awards one point per business-local calendar day; refresh-token rotation does not award points.

Phase 3 adds server-selected daily spin rewards (`GET /api/v1/spin/status`, `POST /api/v1/spin`) and one-attempt daily puzzles (`GET /api/v1/puzzles/today`, `POST /api/v1/puzzles/{id}/attempt`). The initial spin outcomes are 1 point at 50%, 2 at 30%, 5 at 15%, and 10 at 5%; an admin can change the outcomes and odds. The shared daily cap defaults to 20 points across spin and puzzle rewards and does not include daily login points. If an outcome exceeds the remaining cap, the award is limited to the remaining points; a zero-point capped result is still recorded, but no zero-delta wallet transaction is created. The normal allowance is one spin per business day; in `ENVIRONMENT=development` only, `DEVELOPMENT_SPIN_LIMIT` can raise the daily count (local `.env` defaults to 10 for manual testing). Development spin requests are limited to 30 per minute instead of 3; the shared points cap still applies. Admins can manage reward settings at `/admin/activities` or through `/api/v1/admin/activities/configuration`; creating a dated puzzle is available at `/api/v1/admin/puzzles`. Changes are written to the admin audit log.

Phase 4 adds customer redemption reservations and staff fulfillment. Customers reserve at least 100 points with `POST /api/v1/redemptions` (requires an `Idempotency-Key` header), view their history at `GET /api/v1/redemptions`, refresh an active code at `POST /api/v1/redemptions/{id}/qr`, and cancel a reservation at `POST /api/v1/redemptions/{id}/cancel`. Reservations debit the wallet and append the ledger entry atomically. QR contents are opaque HMAC-derived tokens; only token hashes are persisted. Set `REDEMPTION_QR_SECRET_KEY` to a separate random secret of at least 32 characters (it falls back to `JWT_SECRET_KEY` for existing local setups). `REDEMPTION_QR_TTL_MINUTES` defaults to 15 and accepts 5–60 minutes. Customers can redeem a smaller chicken weight than reserved; unused points are refunded atomically at fulfillment. Staff/admin accounts verify tokens at `POST /api/v1/staff/redemptions/verify` and fulfill them at `POST /api/v1/staff/redemptions/fulfill`; fulfillment is single-use, cannot exceed the reserved grams, and writes an audit log. Expired reservations are refunded when customer history, a new reservation, or staff verification is accessed, and cancelled/expired tokens are invalidated. PostgreSQL row locks protect reservation, cancellation, and fulfillment; SQLite tests do not model production lock concurrency.

Phase 5 provides role-based landing pages: customers see their wallet, activity availability, recent redemptions, and transaction history at `/dashboard` and `/transactions`; administrators see shop and redemption totals at `/admin` and manage activities at `/admin/activities`; staff see today's fulfillment summary at `/staff` and scan or verify QR codes at `/staff/redemptions`. The dashboard summaries are available at `GET /api/v1/admin/dashboard` (admin only) and `GET /api/v1/staff/dashboard` (staff/admin only). Daily metrics use `BUSINESS_TIMEZONE`; outstanding points come from current wallet balances, and fulfilled grams are counted from completed redemptions.

Configure the shop's IANA timezone with `BUSINESS_TIMEZONE` (defaults to `Asia/Kolkata`).

## Security notes

- Public registration can only create customer accounts. Privileged users are not self-registered.
- Passwords use Argon2id. Access and refresh cookies are HttpOnly; refresh sessions are persisted and rotated/revoked on use.
- Login/register/refresh have IP-keyed rate limits. The default local `memory://` store is per process; use a shared Redis-compatible rate-limit store before running multiple API workers/replicas.
- CORS allows only configured origins. Production must set a strong random `JWT_SECRET_KEY`, strong database credentials, HTTPS, and `COOKIE_SECURE=true`.
- Activity rewards are selected and validated on the server; spin/puzzle requests are rate limited and capped. Production spin limits are enforced inside locked database transactions; only development environments can opt into additional daily spins. Puzzle answers are HMAC-verified and never included in customer responses.
- Redemption work must keep QR tokens opaque, short-lived and one-time, and use row locks plus database transactions. Browser-calculated rewards or balances are never authoritative.
- The Compose setup is for local development; it does not include TLS termination, backups, monitoring, or production secret management.

## Start locally

```bash
cp .env.example .env
# Run twice to generate separate hexadecimal secrets for those values.
openssl rand -hex 32
docker compose up --build
```

- Web app: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The backend container applies Alembic migrations before starting. The sample `.env` values are for local development only and must not be used in a deployed environment.

## Production deployment

See [docs/deployment.md](docs/deployment.md) for the single-host production setup with Caddy HTTPS termination, internal-only PostgreSQL/Redis/API services, secure cookies, Redis-backed rate limits, secret requirements, backup/rollback guidance, and the production Compose command. Copy `.env.production.example` to `.env.production`, replace every placeholder, and never commit the resulting file. Production startup rejects insecure cookies, shared JWT/QR secrets, memory-only rate limiting, example secrets, wildcard CORS, or extra development spins.

To create the first administrator or staff account after the API database is up, open a shell in the backend container and run:

```bash
docker compose exec backend python -m app.cli --role admin --email owner@example.com --name "Shop Owner"
```

The command prompts for the password twice and stores only an Argon2id hash. Customer self-registration never accepts a privileged role.

## Run tests

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
JWT_SECRET_KEY=local-test-key-that-is-at-least-32-characters-long pytest
```

```bash
cd frontend
npm ci
npm run lint
npm run build
npm run test:e2e
```

The Playwright browser tests need Chromium installed and a running local Compose stack. CI installs Chromium and runs them against the built app.

## Current increment

Phase 1 foundation includes the customer landing/auth experience, customer registration/login/logout, access and rotating refresh tokens, role checks, PostgreSQL/Alembic setup, Compose, and auth tests. Phase 2 adds per-customer wallets, the append-only integer transaction ledger, balance reconciliation and locking, a once-per-business-day login reward, the wallet read APIs, and wallet/auth tests. Phase 3 adds configurable daily spins and puzzles, a shared configurable activity cap, customer activity pages, admin activity settings, audit records, and backend tests. Phase 4 adds atomic point reservations, expiring QR credentials, customer cancellation/refunds and redemption history, plus authenticated staff QR scanning, verification, audited fulfillment, and an unused-points refund. Phase 5 adds customer/admin/staff dashboard views and full customer wallet history; customer/staff administration, report browsing, and suspicious-activity reporting remain future work. Phase 6 adds production security configuration and Compose overlay, HTTPS routing, CI, backend security/configuration tests, and Playwright browser flows for registration, wallet history, and daily spin. Production deployment still requires host-level monitoring, backup execution, secret management, and operational review.
