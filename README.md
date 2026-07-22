# URL Shortener API

A JSON REST API + small web UI for shortening URLs, built with FastAPI.

## Stack & why

- **FastAPI**, fully async end to end.
- **PostgreSQL** via SQLAlchemy's async engine + `asyncpg`. 
- **Redis
- Click analytics are recorded via a FastAPI `BackgroundTask` after the
  redirect response is already sent, so logging a click never adds
  latency to the redirect itself.
- A small static UI (`app/static/`) is served from the same FastAPI app —
  no separate frontend service, so `docker compose up` gives you both the
  API and a page to browse/create/delete links and view per-link traffic.

Visit deployed - [https://url-shortner-208441550973.us-central1.run.app](https://url-shortner-208441550973.us-central1.run.app/)

## Setup

### Option A — Docker Compose (recommended)

```bash
docker compose up --build
```

This starts Postgres, Redis, and the API + UI on `http://localhost:8080`.
Tables are created automatically on startup. Postgres data persists across
restarts via a named volume (`pgdata`).

Visit the swagger api docs on `https://localhost:8080/docs`

### Option B — Run locally with uv

Dependencies are managed with [uv](https://docs.astral.sh/uv/) — no
`requirements.txt`, no manual venv.

```bash
cp .env.example .env
# edit .env with your DATABASE_URL / REDIS_URL

uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

`uv sync` creates `.venv/` and installs exactly what's pinned in
`uv.lock`. To add a dependency: `uv add <package>`.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string (any standard scheme) |
| `REDIS_URL` | yes | Redis connection string |
| `BASE_REDIRECT_URL` | no | Public base URL used to build `short_url` in responses (default `http://localhost:8080`) |
| `SLUG_LENGTH` | no | Auto-generated slug length (default `7`) |
| `PORT` | no | Informational only — the Dockerfile always binds `8080` |

## Web UI

`GET /` serves a small static UI (plain HTML/CSS/JS, no build step, no
separate frontend service) for browsing, creating, and deleting links,
and viewing per-link traffic. Runs from the same container as the API —
`docker compose up` gives you both at `http://localhost:8080`, one port.

- **Expiry presets** — Never / 1 hour / 1 day / 1 week / 30 days, or a
  custom amount+unit picker.
- **Client-side validation** before the request is even sent (URL shape,
  slug charset/length, positive custom expiry), with errors shown inline
  under the relevant field.
- **Server-side errors mapped to fields** — `400` responses include a
  `field`/`message` per issue (see below), and the UI attaches each one
  to its input instead of dumping raw JSON. Network/unexpected errors
  fall back to a dismissible banner.
- **Per-link traffic panel** — click a route to expand total clicks,
  24h/7d counts, unique visitors, last-click time, and a 14-day
  sparkline, without leaving the list.
- **Responsive** — the routing table collapses into stacked cards below
  ~620px.

## API

### `POST /api/links` — create a short link

```bash
curl -X POST http://localhost:8080/api/links \
  -H "Content-Type: application/json" \
  -d '{"slug": "github", "target_url": "https://github.com"}'
```

```json
{
  "slug": "github",
  "target_url": "https://github.com/",
  "short_url": "http://localhost:8080/github",
  "click_count": 0,
  "created_at": "2026-07-21T12:00:00Z",
  "expires_at": null
}
```

Omit `slug` to get an auto-generated one:

```bash
curl -X POST http://localhost:8080/api/links \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com"}'
```

Expiry — accepts an absolute `expires_at` (ISO 8601), a relative
`expire_after` (seconds), or both (whichever resolves earliest wins):

```bash
curl -X POST http://localhost:8080/api/links \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "expire_after": 3600}'
```

Errors:
- Duplicate slug → `409 Conflict`
- Invalid URL / slug charset / non-future `expires_at` → `400 Bad Request`
  with a `field` + `message` per error

### `GET /:slug` — redirect

```bash
curl -i http://localhost:8080/gh
# HTTP/1.1 302 Found
# location: https://github.com/
```

Unknown or expired slug → `404 Not Found`.

### `GET /api/links` — list all links

```bash
curl http://localhost:8080/api/links
```

```json
{
  "links": [
    {
      "slug": "gh",
      "target_url": "https://github.com/",
      "short_url": "http://localhost:8080/gh",
      "click_count": 3,
      "created_at": "2026-07-21T12:00:00Z",
      "expires_at": null
    }
  ],
  "count": 1
}
```

Cached in Redis (30s TTL), invalidated immediately on create/delete. This
means `click_count` in the list can lag the true value by up to the TTL —
use `GET /api/links/:slug` for an always-fresh count.

### `GET /api/links/:slug` — single link detail + traffic aggregates

```bash
curl http://localhost:8080/api/links/gh
```

```json
{
  "slug": "gh",
  "target_url": "https://github.com/",
  "short_url": "http://localhost:8080/gh",
  "click_count": 3,
  "created_at": "2026-07-21T12:00:00Z",
  "expires_at": null,
  "clicks_last_24h": 3,
  "clicks_last_7d": 3,
  "unique_visitors": 2,
  "last_clicked_at": "2026-07-21T14:02:11Z",
  "daily_clicks": [
    { "date": "2026-07-08", "count": 0 },
    { "date": "2026-07-21", "count": 3 }
  ]
}
```

`unique_visitors` counts distinct client IPs seen for this link (best
effort — proxies/NAT mean this is an approximation, not a hard identity
count). `daily_clicks` covers the last 14 days (zero-filled), for
charting. Not cached — always reflects live click data. Unknown slug →
`404 Not Found`.

### `DELETE /api/links/:slug`

```bash
curl -X DELETE http://localhost:8080/api/links/gh
# 204 No Content
```

Unknown slug → `404 Not Found`. Invalidates both the per-slug redirect
cache and the list cache.

### `GET /health`

```bash
curl http://localhost:8080/health
```

```json
{ "status": "ok", "database": "ok", "cache": "ok" }
```

Returns `"degraded"` overall status if either dependency is unreachable,
while still returning `200` (this is a liveness/diagnostic endpoint, not
a strict readiness gate — adjust if your infra expects a non-200 on
degradation).

## Click analytics

Each redirect records a row in `click_events` (timestamp, user-agent, IP)
via a background task, and increments `links.click_count`. This happens
after the redirect response is already sent, so it never adds latency to
`GET /:slug`.
