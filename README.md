# Payment Requests API

A REST API for managing payment requests. Staff submit a request to pay for something (for example, a supplier invoice), and a manager approves or rejects it.

## Features

- Create a payment request with the requester's name, an amount and a description
- List all requests, optionally filtered by status
- Get a single request
- Approve or reject a request, with a required reason for rejections
- Clear JSON error messages and sensible status codes (400, 404, 409)

## Business rules

- The amount must be more than 0
- Only Pending requests can be approved or rejected, so a request cannot be approved twice
- Rejecting a request requires a reason

## Built with

- Python 3.12 and FastAPI
- SQLAlchemy with SQLite (PostgreSQL can be used by setting `DATABASE_URL`)
- Pydantic for input validation
- pytest for automated tests (20 tests)

## Setup

Requires Python 3.12 or newer (tested on 3.12).

```powershell
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activate script, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn app.main:app --reload
```

The API runs at http://127.0.0.1:8000. The SQLite file `payment_requests.db` and its table are created on first start. Interactive docs are at http://127.0.0.1:8000/docs.

To use another database such as PostgreSQL, set the `DATABASE_URL` environment variable (for example `postgresql+psycopg://user:password@host/dbname`) and install its driver (`pip install "psycopg[binary]"`). I have only run the tests and the API against SQLite. No passwords or secrets are stored in this repository.

## Run the tests

```bash
pytest
```

Each test uses its own empty in-memory database, so your real data file is never touched.

## Endpoints

| Method | URL | What it does | Success |
|---|---|---|---|
| POST | `/payment-requests` | Create a request (starts as Pending) | 201 |
| GET | `/payment-requests` | List all requests. Optional `?status=Pending`, `Approved` or `Rejected` | 200 |
| GET | `/payment-requests/{id}` | Get one request | 200 |
| POST | `/payment-requests/{id}/approve` | Approve a Pending request | 200 |
| POST | `/payment-requests/{id}/reject` | Reject a Pending request. Body: `{"reason": "..."}` | 200 |

### Fields

| Field | Notes |
|---|---|
| `id` | Set by the database |
| `requesterName` | Required, 1 to 100 characters |
| `amount` | Required, more than 0, at most 2 decimal places |
| `description` | Required, 1 to 500 characters |
| `status` | `Pending`, `Approved` or `Rejected` |
| `createdAt` | UTC time, for example `2026-10-01T09:15:00Z` |
| `rejectionReason` | Text when rejected, otherwise `null` |

### Status codes and errors

| Code | When |
|---|---|
| 201 | Request created |
| 200 | Read, approved or rejected |
| 400 | Bad input: amount of 0 or less, missing or blank fields, rejecting without a reason, invalid JSON, unknown `?status=` value |
| 404 | Request id does not exist |
| 409 | Request is not Pending (already approved or rejected) |

Errors are JSON with a `detail` field:

```json
{ "detail": "Only Pending requests can be approved or rejected. Request 1 is already Approved." }
```

For bad input, `detail` is a list of messages, so every problem is reported in one response (404 and 409 use FastAPI's default single string):

```json
{ "detail": ["amount: Input should be greater than 0"] }
```

## Example requests

Use `curl` on macOS/Linux or Git Bash. In Windows PowerShell, type `curl.exe` instead of `curl`, or use the `/docs` page.

```bash
# Create
curl -X POST http://127.0.0.1:8000/payment-requests \
  -H "Content-Type: application/json" \
  -d '{"requesterName": "Lerato Dlamini", "amount": 4500.00, "description": "Printing of A1 posters - supplier invoice INV-2231"}'

# List everything, or only Pending
curl http://127.0.0.1:8000/payment-requests
curl "http://127.0.0.1:8000/payment-requests?status=Pending"

# Get one
curl http://127.0.0.1:8000/payment-requests/1

# Approve
curl -X POST http://127.0.0.1:8000/payment-requests/1/approve

# Reject (a reason is required)
curl -X POST http://127.0.0.1:8000/payment-requests/2/reject \
  -H "Content-Type: application/json" \
  -d '{"reason": "Invoice does not match the purchase order"}'

# Approving the same request again returns 409
curl -X POST http://127.0.0.1:8000/payment-requests/1/approve
```

## Project layout

```
app/
  main.py       Starts the app, creates the table, turns bad input into a 400
  routes.py     The five endpoints and the Pending rule
  models.py     The database table
  schemas.py    Rules for the data that comes in (amount above 0, no blanks)
  database.py   Database connection and session
tests/
  test_payment_requests.py
```

## Database design

One table, `payment_requests`:

| Column | Type | Why |
|---|---|---|
| `id` | integer, primary key | Added by the database |
| `requester_name` | text | Required |
| `amount_cents` | integer | Money is stored in cents (4500.00 is 450000), so there are no floating point rounding errors. The API converts to and from a normal amount |
| `description` | text | Required |
| `status` | text | Starts as Pending |
| `created_at` | datetime | Set by the server, stored in UTC |
| `rejection_reason` | text, nullable | Only filled when rejected |

The one business rule lives in a single function, `change_status` in `app/routes.py`. Both approve and reject use it, so there is one place to read or change it.

## Assumptions

- There is no login. The brief does not mention users, so anyone can call any endpoint.
- Amounts use one currency, with at most 2 decimal places and 12 digits in total.
- Text is trimmed of leading and trailing spaces. A name or reason made only of spaces counts as empty.
- Unknown fields in a request body are rejected with a 400, so a client cannot choose its own status.
- Approve takes no body. Reject takes `{"reason": "..."}`.
- The `?status=` filter is not case sensitive. An unknown value returns 400 instead of an empty list, so typos are noticed.
- The list is oldest first and is not paginated, because the system is small.
- Validation errors return 400 (FastAPI's default is 422), to match the brief's suggested codes.

## How I would change this for real production use

- **Authentication and roles.** Staff create and view their own requests, only managers approve or reject, and nobody can approve their own request. Store who decided and when.
- **Audit trail.** Record every status change in a separate table and never hard-delete requests, because this is about money.
- **Two managers at once.** The current check reads the status, then saves. Two simultaneous approvals could both pass the check. In production I would make the update atomic (`UPDATE ... WHERE status = 'Pending'`) or lock the row.
- **PostgreSQL and migrations.** Use PostgreSQL with Alembic migrations instead of creating tables on startup, with the connection string kept in a secret store.
- **Pagination and filters.** Add paging and filters by requester and date range to the list endpoint.
- **Money details.** Add a currency field and approval limits, for example large amounts need a senior manager.
- **Operations.** Logging for unexpected errors, a health check, rate limiting, a CI pipeline that runs the tests, and a Docker image.
