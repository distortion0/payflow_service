# PayFlow card operations service

A FastAPI service that receives PayFlow webhooks about corporate cards and keeps
a ledger per account: how much is available, how much is on hold, and what happened to
each authorization.

Endpoints:

- `POST /webhooks` accepts signed PayFlow events.
- `GET /accounts/{account_id}/balance` returns `available` and `pending`.
- `GET /accounts/{account_id}/transactions` lists the account's authorizations.
- `GET /health` checks the database connection.

## 1. How to run

Requirements: Docker with Compose. Everything else runs inside containers.

```bash
docker compose up --build
```

The service listens on <http://localhost:8000>. The schema is created at startup. To
start again from an empty database:

```bash
docker compose down -v
```

Configuration is read from the environment. Compose sets both variables; the defaults
in `app/config.py` are for local development only.

| Variable                 | Default in compose                                   |
|--------------------------|------------------------------------------------------|
| `DATABASE_URL`           | `postgresql+asyncpg://payflow:payflow@db:5432/payflow` |
| `PAYFLOW_WEBHOOK_SECRET` | `whsec_test_123` (PayFlow's test secret)             |

To check the service with PayFlow's own tool:

```bash
git clone https://github.com/mekasp/PayFlow.git
cd PayFlow
python3 PayFlowEventsSender.py happy_path.json
curl -s http://localhost:8000/accounts/acc_1/balance
curl -s http://localhost:8000/accounts/acc_1/transactions
```

### Tests

The tests run against a real PostgreSQL database (`payflow_test`, created by the
compose init script), because what they verify is exactly the database behaviour:
`ON CONFLICT`, `NUMERIC` and concurrent transactions.

```bash
docker compose run --rm app pytest
```

For local development (Python 3.12 and Poetry):

```bash
poetry install
docker compose up -d db
poetry run pytest
poetry run ruff check .
poetry run uvicorn app.main:create_app --factory --reload
```

## 2. Assumptions

- An account has one currency, the one from its first `account.funded` event. I store
  the currency of every event as delivered and do not cross-check it.
- There is one capture per authorization. A capture may be smaller or larger than the
  authorized amount and releases the whole hold.
- A reversal releases the whole hold. If both `captured` and `reversed` arrive for the
  same authorization, which the documented lifecycle does not allow, `captured` wins:
  money actually moved, and `available` is never overstated.
- `available` may go negative, for example when a capture exceeds the funding.
- An authorization whose `authorization.created` event has not arrived yet is still
  listed: `merchant`, `authorized_amount` and `created_at` are `null`, its status is
  derived from the facts that did arrive.
- An account exists only after `account.funded`. Events that arrive before it are
  stored and counted as soon as the funding arrives; until then both `GET` endpoints
  answer `404`.


## 3. Not done on purpose

- **Authentication on the GET endpoints.** The task does not ask for it.
- **Pagination.** The task says it is not needed.
- **Currency mismatch checks.** The documentation says an account has one currency;
  task gives no rule for what to do on a mismatch.

## 4. Before production

- Alembic migrations instead of `create_all`.
- The webhook secret from a secret manager, with rotation (accepting two secrets for a
  while).
- Structured logs, metrics and alerts on `failed` and `ignored` events; today they
  are only visible in the `events` table.
- A stored balance instead of aggregates over all facts once accounts have many
  events, updated in the same transaction as the facts.
- Reconciliation with PayFlow to detect events that never arrived.
- Authentication on the GET endpoints.
- A tool to reprocess `failed` events after a fix; the payload is kept for that.
