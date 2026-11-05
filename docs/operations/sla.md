# Service levels (99.9 %)

**Owner:** Operations lead · **Version:** 1.0 (5 Nov 2026)

## The commitment

**99.9 % monthly availability** of the hosted service: the API (widget answers,
voice, the console's backend) answers requests without a server error. That is
at most **43 minutes** of unavailability a month (the *error budget*: 0.1 % of
requests). Planned maintenance announced on the status page at least 48 hours
ahead, and announced and kept under 30 minutes, doesn't count.

## How it's measured (SLIs and SLOs)

| SLI | SLO | Measured from |
|---|---|---|
| Availability: requests without a 5xx | 99.9 % over 30 days | `fb_http_requests_total{status="5xx"}` / all |
| Readiness: minutes the API component is up | 99.9 % over 30 days | status page samples (every minute) |
| Voice latency: time to first audio | p95 < 1.5 s | `fb_time_to_first_audio_seconds` |
| Whole turn | p95 < 8 s | `fb_turn_seconds` |

Alerts (`deploy/monitoring/alerts.yml`) page on a fast burn of the error budget
(2 % of the month's budget in an hour) and open a ticket on a slow burn (5 % in
six hours), the standard multi-window pair; latency alerts follow the SLO. The
public status page shows the 90-day uptime of each component.

## The controls behind it

| Control | Where |
|---|---|
| Readiness of every dependency; 503 when a critical one fails, so traffic moves | `/readyz` (`app/observability/health.py`) |
| Graceful shutdown: voice sessions finish their answer and move (1012/1013); widget reconnects | `app/transport/drain.py`, widget `VoiceClient` |
| More than one replica, shared sessions and rate limits | `REDIS_URL` (F-3) |
| Backups with point-in-time recovery; quarterly restore drills | managed Postgres PITR (hosted); `deploy/selfhost/bin/backup.sh` (self-hosted); `backend/scripts/restore_drill.sh` |
| Alert rules on the metrics, each with a runbook section | `deploy/monitoring/`, [incident-runbook.md](incident-runbook.md) |
| A public status page with incidents | `/status` |
| Load tests for the voice path before releases | `backend/loadtest/voice.py` (below) |

SOC 2 **Type II** is these controls operating, with evidence, for 3–12 months
under audit (see `docs/compliance/control-matrix.md`): the status page
samples, alert history, restore-drill records and post-incident reviews are
that evidence.

## Capacity

Before each release, and after a change to the voice path, run the load test
against staging with production settings:

```bash
cd backend
python -m loadtest.voice --url wss://staging-api.example.com/ws/voice --key fbk_… \
    --sessions 200 --turns 3 --ramp 30 --think 1 --max-p95-ttfa 1.5 --json load.json
```

It exits non-zero if a turn fails or p95 time to first audio is over the
target. Plan for peak concurrent voice sessions per replica at 70 % of the
level where p95 starts to climb; scale out on `fb_ws_connections` per replica.

Baseline (5 Nov 2026, one worker on a developer laptop with the load
generator on the same machine, `MOCK_AI` — so this is the platform's own
overhead: transport, routing, retrieval, audio framing, not the model's
latency; 3 turns per session, 10 s ramp, ~1 s think time):

| Concurrent sessions | Turns | Failed | p50 / p95 time to first audio | p95 whole turn |
|---|---|---|---|---|
| 50 | 150 | 0 | 0.63 s / 1.62 s | 2.3 s |
| 100 | 300 | 0 | 1.92 s / 5.93 s | 8.7 s |
| 200 | 587 | 5 (timeouts) | 5.99 s / 15.2 s | 22.2 s |

Throughput levels off at about 8 turns a second per worker, so plan for about
35 concurrent voice sessions per worker and scale with `WEB_CONCURRENCY` and
replicas; repeat on production-like hardware with the real models before
committing to customer capacity.
