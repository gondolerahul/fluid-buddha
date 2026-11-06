# Monitoring FluidBuddha

- `prometheus.yml` — scrape each backend replica's `/metrics` (bearer
  `METRICS_TOKEN`) and load the rules.
- `alerts.yml` — alert rules on the metrics the app exports: availability
  (error-budget burn, a replica down or not ready, a stuck drain), voice
  latency (time to first audio, whole turns), model errors, background jobs,
  spend caps. Each alert carries `severity` (`page` / `ticket`) and a link to
  its section of [the incident runbook](../../docs/operations/incident-runbook.md).
  The SLOs behind them: [docs/operations/sla.md](../../docs/operations/sla.md).

Check them after editing (CI does too):

```bash
docker run --rm --entrypoint promtool -v "$PWD:/m:ro" prom/prometheus:v3.16.0 check rules /m/alerts.yml
```

Route `severity="page"` to the pager and `severity="ticket"` to the team's
queue in Alertmanager. The public status page (`/status`) is separate: it
measures the same readiness checks every minute and shows incidents posted by
the on-call engineer.
