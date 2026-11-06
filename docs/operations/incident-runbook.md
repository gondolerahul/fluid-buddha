# Incident runbook (operations)

**Owner:** Operations lead · **Review:** quarterly and after every SEV-1/SEV-2 ·
**Version:** 1.0 (5 Nov 2026)

How to run an outage or degradation, from the page to the post-incident
review. Security and data incidents follow the
[incident response plan](../compliance/incident-response-plan.md) (same
severities and roles); this runbook covers availability and performance, and
each alert in [`deploy/monitoring/alerts.yml`](../../deploy/monitoring/alerts.yml)
links to its section below. The SLA and its error budget are in [sla.md](sla.md).

## Taking a page

1. **Acknowledge** in the pager within 5 minutes (SEV-1/2). You are the
   incident lead until you hand it over.
2. **Look**: `https://<api>/readyz` (each dependency, with timings),
   `https://<api>/status`, the Grafana / Prometheus view of the alert, and
   `docker compose logs --since 15m backend` (or the platform's log search —
   every line carries a `request_id`).
3. **Classify** (SEV-1 full outage or data at risk; SEV-2 partial: voice down,
   one region, slow; SEV-3 degraded, one customer). Open a channel
   `#inc-<date>-<word>` for SEV-1/2.
4. **Tell customers** within 15 minutes for SEV-1/2 — post on the status page
   (below), then update at least every 30 minutes until resolved.
5. **Mitigate first, fix second**: roll back, fail over, scale out, switch a
   site to its own model (M3-4) or to the platform's, shed load.
6. **Resolve** on the status page once the alert has been clear for 15 minutes.
7. **Review** within 5 working days (template at the end), blameless; actions
   tracked to done.

## Posting on the status page

Operators post with the `STATUS_TOKEN` (in the password manager):

```bash
API=https://api.fluidbuddha.com; T="Authorization: Bearer $STATUS_TOKEN"
# open
curl -sS -X POST $API/status/incidents -H "$T" -H 'Content-Type: application/json' -d '{
  "title": "Voice answers are slow", "impact": "major", "components": ["voice"],
  "status": "investigating", "body": "Voice answers are taking longer than usual. We are looking into it."}'
# update (identified → monitoring → resolved)
curl -sS -X POST $API/status/incidents/<id>/updates -H "$T" -H 'Content-Type: application/json' \
  -d '{"status": "resolved", "body": "Fixed. Answers are back to normal speed."}'
```

`impact`: `minor`, `major` (component shown degraded), `critical` (shown down),
`maintenance` (post `scheduled` ahead, `identified` when it starts). Components:
`api`, `voice`, `jobs`, `email`. Plain words, what visitors and customers
notice, no internal names; never guess an ETA.

## Alerts

### FluidBuddhaDown

A replica stopped answering `/metrics`. Check the host / container
(`docker compose ps`, platform events: OOM-killed? crash loop?). If it's one of
several replicas, the load balancer has already dropped it (readiness): replace
it and investigate the logs. If it's the only one: restart
(`docker compose up -d backend`), post on the status page, then investigate.

### FluidBuddhaNotReady

A critical dependency is failing: `/readyz` says which.

- `db`: database down, full disk, connections exhausted. Managed Postgres: check
  its console and fail over. Self-hosted: `docker compose logs postgres`, disk
  space (`df -h`). Connections: look for a stuck migration or a runaway job.
- `migrations`: the schema isn't at this version — a deploy started before its
  migration finished, or a rollback ran against a newer schema. Let the newest
  replica finish starting (it migrates), or roll forward. Never edit
  `alembic_version` by hand.
- `redis`: sessions and rate limits are shared there. Restart Redis; the app
  rebuilds what it needs (visitors may have to ask again).

### Error rate

`FluidBuddhaErrorBudgetFastBurn` (page) / `SlowBurn` (ticket): more than 1.44 %
(fast) or 0.6 % (slow) of requests are 5xx. Find the route:
`topk(5, sum by (route) (rate(fb_http_requests_total{status="5xx"}[5m])))`.
A deploy in the last hour? Roll it back first. One site? Check its integrations
and actions. All routes? Usually the database (see NotReady).

### Slow voice

`FluidBuddhaSlowFirstAudio` / `VerySlowFirstAudio` / `SlowTurns`: visitors wait
for the first sound. `fb_stage_seconds` shows which stage (`asr`, `router`,
`retrieval`, `thinker`, `tts`). TTS or model slow: check the provider's
status page and our engine errors; move affected sites to another region or
their own model. Retrieval slow: database load (long queries in
`pg_stat_activity`). Many voice sessions per replica (`fb_ws_connections`):
scale out — see [load testing](sla.md#capacity).

### Model errors

`FluidBuddhaModelErrors`: calls to an engine (`llm`, `tts`, `asr`, `embed`) are
failing. Quota, auth or the provider's outage. Answers fall back to cached and
grounded replies where they can. Rotate the key if auth, raise the quota, or
switch region; a customer's own model (M3-4) shows its error in their console
and falls back to the platform model by itself.

### Stuck drain

`FluidBuddhaDraining` for 10 minutes: a replica began shutting down but didn't
exit. Its voice sessions were told to move and closed (1012) after their answer;
something is holding the process. Kill it (`docker compose kill backend` /
delete the pod); visitors reconnect to other replicas.

### Job failing

`FluidBuddhaJobFailing` / `FluidBuddhaCrawlsFailing`: a background job keeps
failing (`fb_job_runs_total{outcome="error"}` by `job`). Logs for
`app.jobs` show the error. Email outbox: SMTP credentials or the provider.
Retention: database locks. Crawls: a site blocking us, or DNS.

### Cost cap

`FluidBuddhaCostCapNear` / `Reached`: a site's widget used 80 % / 100 % of its
daily spend cap; at 100 % it answers from the cache only. Usually real traffic
(a campaign launch) — tell the customer and raise their cap if they agree;
occasionally abuse (one IP, bots) — block it.

## Graceful restarts

Deploys and scale-downs send SIGTERM: the replica fails readiness, tells its
voice sessions to move, lets each finish the answer it's speaking, closes them
with 1012, and refuses new sockets with 1013; the widget reconnects to another
replica within about 2 seconds. Keep the platform's grace period above
`DRAIN_SECONDS` (25 s) + 20 s (Compose: `stop_grace_period: 60s`; Kubernetes:
`terminationGracePeriodSeconds: 60`). Roll one replica at a time.

## Restoring data

Database restore and point-in-time recovery:
[business continuity §4](../compliance/business-continuity.md) and, for
self-hosted installs, [deploy/selfhost/README.md](../../deploy/selfhost/README.md#point-in-time-recovery).

## Post-incident review (template)

- **Summary** — what happened, in two sentences customers would understand.
- **Impact** — who, what, how long; error budget used.
- **Timeline** (UTC) — detection, page, acknowledgement, mitigation, resolution.
- **Root cause and contributing factors** — why, five times; no blame.
- **What went well / what didn't** — detection, tooling, communication.
- **Actions** — each with an owner and a date; at least one that prevents or
  detects this class of problem sooner.
