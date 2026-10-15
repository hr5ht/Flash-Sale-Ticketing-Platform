# Flash-Sale Ticketing Backend

A ticketing backend built for flash sales: hundreds of buyers going after the same few seats at the same moment. The one guarantee that matters is that **a seat is never sold twice**, however many requests arrive at once, and the database enforces that guarantee rather than application code.

FastAPI, async SQLAlchemy 2.0, PostgreSQL, Alembic, Pydantic v2.

**Live:** https://flashsaleticketing.vercel.app (opens the interactive API docs)

## How a seat stays unique

Seat ownership lives in a single table:

```sql
seat_claims (seat_id BIGINT PRIMARY KEY, hold_id BIGINT)
```

That primary key is the guarantee. A claim belongs to a hold, and the hold's state decides what the claim means:

| hold status | expiry | the seat is |
|---|---|---|
| `active` | in the future | held |
| `active` | in the past | available again |
| `confirmed` | ignored | booked, permanently |
| `released` | ignored | available (the claim row is deleted on release) |

This gives three properties without any application-level locking:

- **All-or-nothing holds.** Every seat in a request goes in as one multi-row insert inside a savepoint. If one seat conflicts, the whole statement fails and nothing is held.
- **Expiry with no background job.** Expiry is evaluated against `now()` in Postgres every time availability is read or a seat is acquired. An expired hold counts as available everywhere the moment it expires. The application clock is never consulted.
- **Booked seats stay booked.** Confirming a hold keeps its claim rows and marks the hold `confirmed`, and expiry only ever reclaims `active` holds.

Bypassing the API doesn't get around this either:

```
INSERT INTO seat_claims (seat_id, hold_id) VALUES (1, 2);
ERROR:  duplicate key value violates unique constraint "seat_claims_pkey"
```

Seats also carry a denormalized `event_id`, which keeps the hot seat queries on a single table. Composite foreign keys, `seats(section_id, event_id) → sections(id, event_id)` and the same for price tiers, make it impossible for a seat to point at a section or tier from a different event. The denormalized column cannot drift.

## Seat acquisition strategies

Four interchangeable strategies are selected by `SEAT_ACQUISITION_STRATEGY` (see `src/bookings/acquisition.py`):

| strategy | mechanism |
|---|---|
| `unique_insert` | delete expired claims for the requested seats, insert, rely on the primary key violation |
| `for_update` | lock the seat rows with `SELECT ... ORDER BY id FOR UPDATE`, check live claims, insert |
| `skip_locked` | the same with `SKIP LOCKED`: give up at once instead of waiting behind another buyer |
| `upsert` (default) | one `INSERT ... ON CONFLICT (seat_id) DO UPDATE ... WHERE <existing claim is dead> RETURNING` |

`upsert` takes free seats, takes over expired claims and skips live claims in one statement, with no read-then-write window. The lock-based strategies sort seat ids before locking, so two buyers with overlapping baskets cannot deadlock.

The same correctness tests run against all four strategies, and a separate suite runs the default strategy at READ COMMITTED, REPEATABLE READ and SERIALIZABLE. The benchmark below covers every combination.

## Benchmark

`scripts/flash_sale.py` seeds an event, fires every buyer at it concurrently and checks the result for oversells. It runs 500 buyers over 100 seats, 2 seats per buyer, with overlapping baskets so the contention is real. It was measured on an Apple M1 against local Postgres 17 with a pool of 40 connections.

```
strategy       isolation          ok  conflict  retry  oversell   req/s   p50 ms   p95 ms
unique_insert  READ COMMITTED     45       455      0         0   448.2    704.0   1082.6
for_update     READ COMMITTED     44       456      0         0   551.7    572.3    890.7
skip_locked    READ COMMITTED     39       461      0         0   664.8    458.0    727.6
upsert         READ COMMITTED     41       459      0         0   495.9    602.3    990.1
upsert         REPEATABLE READ    45       403     52         0   469.1    566.5   1026.7
upsert         SERIALIZABLE       43        15    442         0   357.3    853.5   1350.5
skip_locked    SERIALIZABLE       23       438     39         0   504.5    520.1    942.0
```

**Zero oversells in all 12 strategy and isolation combinations.** What the numbers show:

- `skip_locked` has the best throughput and latency because losing buyers fail immediately instead of queueing for a lock. It also sells the fewest seats, because a buyer who would have won if they had waited gives up. That trade between latency and sell-through is the real choice between these strategies.
- Raising the isolation level adds no safety here, because the primary key already provides it. What it does change is how many requests fail with retryable serialization errors. SERIALIZABLE turns most conflicts into retries.
- The simulator calls the service layer directly with independent sessions, so the numbers measure database contention, not HTTP overhead. The relative order of the strategies is the meaningful result; the absolute throughput isn't.

Reproduce it with:

```bash
python scripts/flash_sale.py --buyers 500 --seats 100 --strategy all --isolation all
python scripts/flash_sale.py --explain     # EXPLAIN (ANALYZE, BUFFERS) on the hot queries
```

The script defaults to `TEST_DATABASE_URL` and truncates that database before every run.

## Things worth knowing

**Serialization failures are not "seat taken".** Under SERIALIZABLE, buyers holding *disjoint* seats were rejected through predicate-lock conflicts. Reporting those as `409 seat unavailable` would tell buyers their seats were gone when they weren't. Those errors (SQLSTATE `40001` and `40P01`) return `503` and can be retried.

**Commits happen inside the service, not in dependency teardown.** SERIALIZABLE can defer a conflict to `COMMIT`. When the commit ran in the FastAPI dependency's teardown, the response had already started, so the client got a dropped connection and the server logged a `RuntimeError`. Write paths now commit inside the request, where a failure can still become a proper status code.

**Services never roll back the caller's transaction.** Recoverable conflicts are handled with `session.begin_nested()` savepoints, so a failed hold attempt unwinds its own work and nothing else.

**Idempotency is enforced by the database.** `UNIQUE (user_id, idempotency_key)` on holds and on bookings. If two requests with the same key race, the loser re-reads by key and returns the original result. Repeating a hold with the same key doesn't count against the per-event seat limit a second time.

**Indexes were chosen from EXPLAIN output, not guessed.** The event listing originally aggregated every price tier to show a minimum price on 20 rows (1.65 ms, 116 buffers). A correlated subquery that runs only for the returned page brought that to 0.06 ms and 64 buffers. A functional index on `lower(city)` was never chosen by the planner, so it was replaced with `(status, lower(city), starts_at)`, which serves both the filter and the sort order.

## API

| method | path | who |
|---|---|---|
| POST | `/auth/register` | anyone (role `attendee` or `organizer`) |
| POST | `/auth/login` | anyone |
| POST | `/auth/refresh` | holder of a refresh token |
| GET | `/auth/me` | authenticated |
| POST | `/events` | organizer |
| GET | `/events` | anyone; published only, paginated, filter by `city`, `category`, `starts_after`, `starts_before` |
| GET | `/events/mine` | organizer, including drafts |
| GET | `/events/{id}` | anyone if published, otherwise the owner or an admin |
| PATCH | `/events/{id}` | owner or admin, drafts only |
| POST | `/events/{id}/publish` | owner or admin |
| GET | `/events/{id}/seatmap` | each seat as `available`, `held` or `booked` |
| GET | `/events/{id}/sales` | owner or admin |
| POST | `/events/{id}/holds` | authenticated; accepts an `Idempotency-Key` header |
| DELETE | `/holds/{id}` | the holder |
| POST | `/holds/{id}/confirm` | the holder, before expiry; accepts an `Idempotency-Key` header |
| GET | `/bookings` | authenticated, paginated |
| GET | `/bookings/{id}` | the booking's owner |
| GET | `/health` | runs a real query against the database |

Interactive docs are served at `/docs` while the app is running.

## Running locally

Requires Python 3.11 or newer (the deployment runs 3.12) and PostgreSQL.

```bash
createdb flash_sale
createdb flash_sale_test

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```
DATABASE_URL=postgresql+asyncpg://<user>@localhost:5432/flash_sale
TEST_DATABASE_URL=postgresql+asyncpg://<user>@localhost:5432/flash_sale_test
JWT_SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(48))">
```

`TEST_DATABASE_URL` is only needed for the tests and the benchmark. Database URLs can be given in asyncpg form, as above, or as the plain `postgresql://...?sslmode=require` string that hosted providers hand out. The app converts the second form on startup.

Optional settings and their defaults:

| variable | default |
|---|---|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 15 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 |
| `HOLD_DURATION_SECONDS` | 300 |
| `MAX_SEATS_PER_USER_PER_EVENT` | 6 |
| `SEAT_ACQUISITION_STRATEGY` | `upsert` |

Then:

```bash
alembic upgrade head
uvicorn src.main:app --reload
pytest
```

The tests run against `TEST_DATABASE_URL`. Most of them run inside a transaction that is rolled back afterwards. The concurrency and isolation tests commit for real and truncate the tables afterwards, because two connections cannot see each other's uncommitted rows.

## Deploying to Vercel with Neon

Live at **https://flashsaleticketing.vercel.app**. The API runs on Vercel as a single Python function in Singapore, and the database is Neon serverless Postgres in the same region.

Two files configure the deployment:

- `vercel.json` sets `"framework": "fastapi"` and `"regions": ["sin1"]`. Without the framework setting, a project created from the CLI gets the "Other" preset. That build finishes in 54 ms, installs no Python, and every URL returns Vercel's own 404. Without the region, the function runs in Washington, D.C. and every query crosses to Singapore and back.
- `.vercelignore` keeps `.env`, `.env.*`, `.venv`, tests and scripts out of CLI uploads. `vercel deploy` uploads the working directory, not the git commit, so without this file local secrets would be sent along.

`pyproject.toml` points Vercel at the app (`[tool.vercel] entrypoint = "src.main:app"`), pins the tested dependency versions, and declares the project an application rather than a package (`[tool.uv] package = false`), so the build installs dependencies without trying to build the repository as a wheel. `.python-version` selects 3.12, the oldest version Vercel runs.

**1. Create the database.** Create a project in the [Neon console](https://console.neon.tech). Under **Connect**, copy two connection strings:

- the **pooled** string (its host contains `-pooler`), for the running app
- the **direct** string (the same host without `-pooler`), for migrations

Use them exactly as Neon gives them. Neon's format, `postgresql://...?sslmode=require&channel_binding=require`, is libpq syntax that asyncpg rejects (`unexpected keyword argument 'sslmode'`), so `src/config.py` rewrites it to `postgresql+asyncpg://...?ssl=require`.

**2. Create the schema.** From your machine, with the direct string:

```bash
DATABASE_URL="<direct connection string>" alembic upgrade head
```

The build does not run migrations. Schema changes are applied before the code that needs them is deployed, so a failed migration never leaves a broken deployment live.

**3. Deploy.** With the [Vercel CLI](https://vercel.com/docs/cli):

```bash
vercel link
vercel env add DATABASE_URL production      # paste the pooled Neon string
vercel env add JWT_SECRET_KEY production    # a new secret, never the local one
vercel deploy --prod
```

`vercel link` also connects the GitHub repository, so every push to `main` deploys to production after that. The root URL redirects to the interactive docs at `/docs`.

**Measured on the live deployment:**

| request | time |
|---|---|
| first request after idle (function cold start, Neon waking from zero) | about 5 s |
| `/health` while warm, function in Washington, D.C. | 1.9 s |
| `/health` while warm, function in Singapore next to the database | 0.41 s median |

The engine uses `pool_pre_ping`, so a connection that died while Neon was suspended is replaced instead of failing the request. The benchmark numbers earlier in this README come from local Postgres, not from this deployment.

## Layout

The code is organised by domain, not by layer. Each domain owns its router, schemas, models, service and exceptions.

```
src/
  auth/        users, roles, argon2 hashing, access and refresh tokens
  events/      events, price tiers, sections, seats, listing, seat map
  bookings/    holds, seat claims, bookings, acquisition strategies, sales
  config.py    settings from environment variables
  database.py  engine, session, transaction boundary
  exceptions.py  domain errors mapped to HTTP status codes in one place
  pagination.py
alembic/       migrations
scripts/       flash_sale.py benchmark
tests/
```

Routers only handle HTTP. Business rules, authorization checks and transactions live in the services.

## Known limitations

- **Refresh tokens are stateless.** Logging out cannot revoke a token, and a stolen refresh token is valid until it expires. Rotation and revocation are planned.
- **Login timing reveals whether an email exists.** The error response is identical for an unknown email and a wrong password, but the unknown-email path skips Argon2 and returns faster.
- **Expired claim rows stay until a seat is wanted again.** Correctness is unaffected, since every read checks expiry, but the table grows. A periodic sweeper is planned.
- **A seat layout cannot change after the event is created.** Draft metadata can be edited; the sections, rows and seats cannot.

## Not built yet

- A live seat map over WebSockets that broadcasts holds, releases, expiries and bookings
- Redis caching and rate limiting, payments, a background worker and refresh token rotation
