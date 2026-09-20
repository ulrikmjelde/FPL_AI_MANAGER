# FPL Shadow Manager

AI-first FPL agent that follows one creator on X, interprets confirmed decisions (including linked YouTube videos), mirrors them when possible, adapts them to your squad when necessary, validates the result deterministically, and can execute transfers through FPL's unofficial web API.

> **Important:** FPL's write API is undocumented/unofficial and can change without notice. Automated access may conflict with Premier League/FPL terms. Use only on your own account and understand the account/ToS risk before setting `AUTO_TRANSFER=true`.

## Architecture

```text
X -> source watcher -> AI interpreter -> CONFIRMED?
                                 |
                                 v
                         current FPL squad
                                 |
                  exact mirror -> if impossible
                                 |
                                 v
                         AI intent mirror
                                 |
                                 v
                     deterministic validator
                                 |
                    AUTO_TRANSFER=true?
                      /             \
                  dry-run       FPL POST /transfers/
                                    |
                                    v
                              read-back verify
```

AI decides **what** to do. Deterministic code decides whether the plan is legal and inside your policy. Only the FPL client sees the FPL token.

## 1. What you need

Create these accounts/services in this order:

1. **OpenAI API** — create an API key.
2. **X Developer account/app** — obtain a Bearer Token with permission to read the followed account's posts. Your X plan must allow the required read volume.
3. **Fantasy Premier League account** — log in normally and note your FPL Entry ID.
4. **FPL auth token** — while logged into `fantasy.premierleague.com`, open browser DevTools -> Network, reload the FPL page, open an authenticated request such as `/api/my-team/<id>/`, and copy the value of `X-API-Authorization`. Put the JWT/token in `FPL_ACCESS_TOKEN`. Never commit it.
5. **Docker** for local testing.
6. **Always-on hosting + Postgres** for production. The simplest hosted path is one long-running Railway service from this repo plus a Railway Postgres database. A small always-on VPS running `docker compose` also works.

The current FPL auth scheme uses `X-API-Authorization: Bearer <token>` on authenticated API calls. The repo also supports `FPL_REFRESH_TOKEN` when you have one, but initial refresh-token acquisition is intentionally not guessed/automated here because the PL OIDC flow and redirect registration can change.

## 2. Configure locally

```bash
cp .env.example .env
```

Fill these required values in `.env`:

```dotenv
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-terra

X_BEARER_TOKEN=...
X_CREATOR_USERNAME=the_account_without_at

FPL_ENTRY_ID=1234567
FPL_ACCESS_TOKEN=eyJ...
```

Keep this safe initially:

```dotenv
AUTO_TRANSFER=false
PROCESS_INITIAL_HISTORY=false
```

`PROCESS_INITIAL_HISTORY=false` is deliberate: the first run records the newest X post as a baseline and **will not execute old creator posts**.

Recommended initial policy:

```dotenv
ALLOW_ALTERNATIVE_PLAYERS=true
ALLOW_MULTI_TRANSFER=true
ALLOW_POINTS_HITS=false
MAX_POINTS_HIT=0
MAX_TRANSFERS_PER_DECISION=3
MIN_SOURCE_CONFIDENCE=0.95
MIN_AI_CONFIDENCE=0.85
AUTO_USE_CHIPS=false
```

Optional notification webhook:

```dotenv
NOTIFY_WEBHOOK_URL=https://...
```

## 3. Start locally

```bash
docker compose up -d --build
```

Check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/fpl/check
```

Trigger an immediate X poll:

```bash
curl -X POST http://localhost:8000/run-now
```

First successful `run-now` should normally return `baselined_at` if this is a new database.

## 4. Test before enabling transfers

Leave `AUTO_TRANSFER=false` until all of these work:

- `/health` returns OK.
- `/fpl/check` returns 15 picks and your bank value.
- `/run-now` can read the creator's X account.
- A new creator post produces no crashes.
- If a confirmed decision appears, the result is `DRY_RUN` rather than an execution.

Then enable autonomous transfers:

```dotenv
AUTO_TRANSFER=true
```

Restart:

```bash
docker compose up -d --build
```

From this point, a qualifying `CONFIRMED` decision can be executed automatically if confidence thresholds and validator rules pass.

## 5. Production on Railway

A simple production setup is **two services**: this app + Postgres. The app has its own internal scheduler, so you do not need Railway Cron.

1. Push this repo to GitHub.
2. Create a Railway project.
3. Add **PostgreSQL**.
4. Add a service from the GitHub repo. Railway will use the included `Dockerfile`.
5. In the app service's Variables, paste the environment variables from `.env`.
6. Set `DATABASE_URL` to a reference to Railway Postgres `DATABASE_URL`. The app automatically converts `postgresql://` to SQLAlchemy's async `postgresql+asyncpg://` form.
7. Deploy and open `/health`.
8. Run `/fpl/check`.
9. Keep `AUTO_TRANSFER=false` for the first baseline run.
10. When the baseline and dry-run behavior are verified, change `AUTO_TRANSFER=true`.

Railway supports long-running services and managed Postgres, which fits this single-process scheduler design. If you prefer a VPS, run the provided `docker-compose.yml` and ensure Docker restarts on boot.

## 6. How decisions work

The interpreter classifies each new source item as:

```text
COMMENTARY -> IDEA -> LEANING -> LIKELY -> CONFIRMED
```

Only `CONFIRMED` can reach the transfer planner.

The planner then:

1. Resolves creator player names against live FPL player IDs.
2. Attempts an exact mirror.
3. If exact mirroring is impossible, asks the AI to produce an intent-preserving plan from a constrained candidate pool.
4. Validates budget, squad positions, max 3 players per club, transfer count and points-hit policy.
5. Re-reads your FPL squad immediately before execution.
6. Aborts if the live state changed after planning.
7. Sends `POST /api/transfers/` only if `AUTO_TRANSFER=true`.
8. Re-reads the squad after the request for verification.

## 7. YouTube behavior

If an X post contains an expanded YouTube URL, the app attempts to read a public transcript using `youtube-transcript-api`. If no transcript is available, it simply analyzes the X post itself. No YouTube API key is currently required.

This is intentionally modular: a later version can add audio transcription as a separate fallback without changing the decision engine.

## 8. FPL token expiry

If `FPL_ACCESS_TOKEN` expires and you have no `FPL_REFRESH_TOKEN`, authenticated FPL operations will fail safely; no transfer is attempted. Replace `FPL_ACCESS_TOKEN` and restart the service.

If you have a current PL refresh token, set:

```dotenv
FPL_REFRESH_TOKEN=...
```

The client will call the PL OIDC token endpoint and retry once after 401/403.

**Do not store your PL password in this repo.**

## 9. Key files

```text
app/services/ai_brain.py     AI interpretation + intent-mirror planning
app/services/validator.py    hard FPL/policy validation
app/services/fpl_client.py   FPL reads + transfer POST
app/services/x_client.py     X polling
app/services/youtube.py      YouTube transcript extraction
app/workers/monitor.py       end-to-end autonomous loop
app/core/config.py           environment/settings
.env.example                 every secret and policy setting
```

## 10. Current deliberate limitations

- No automatic chip use (`AUTO_USE_CHIPS=false` and executor does not yet submit chips).
- No automated captain/bench changes yet.
- No guaranteed automated acquisition of the initial FPL OIDC refresh token.
- Public YouTube transcripts are best-effort.
- X API availability/cost depends on your X developer plan.
- FPL endpoints are unofficial and may change.

These are isolated behind service classes so they can be replaced without redesigning the AI core.

## Useful source references

- FPL 2026/27 endpoint catalogue: https://github.com/jakesmith1997-sfc/fpl-api
- 2026 authenticated write/API findings: https://github.com/MoayadAbbara/FPL-MCP/blob/main/docs/FINDINGS.md
- Railway Postgres docs: https://docs.railway.com/databases/postgresql
- Railway long-running service docs: https://docs.railway.com/build-deploy
- OpenAI API docs: https://platform.openai.com/docs
