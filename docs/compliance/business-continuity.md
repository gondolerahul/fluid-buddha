# Business continuity and disaster recovery

**Owner:** Operations lead (with the Engineering lead) · **Review:** yearly ·
**Version:** 1.0 (5 Nov 2026, draft)

## 1. Objectives

| | Target | How |
|---|---|---|
| **RPO** (data we can lose) | 24 hours (1 hour with point-in-time recovery) | Daily `pg_dump` backups; WAL archiving / managed PITR in production |
| **RTO** (time to restore service) | 4 hours | Stateless backend replicas, scripted restore, documented runbook |

The backend keeps no state outside Postgres (and optional Redis for shared
sessions and rate limits, which can be lost safely), so recovering the database
recovers the service.

## 2. Backups

`backend/scripts/backup.sh`:

- `pg_dump` custom format, compressed; a SHA-256 checksum beside each copy;
- optional encryption with [age](https://age-encryption.org) (`BACKUP_AGE_RECIPIENT`);
- copies older than `RETENTION_DAYS` (default 30) are pruned;
- each run appends a line to `backup-log.jsonl` (time, file, size, checksum,
  schema revision) — the evidence that backups ran.

Production schedule: daily at 02:00 IST, copied to storage in a different
location from the database (another region or provider), encrypted. Access to
backups is limited like access to the database.

```bash
# daily (cron)
DATABASE_URL=postgresql://backup_user:***@db:5432/cortex \
BACKUP_DIR=/var/backups/fluidbuddha BACKUP_AGE_RECIPIENT=age1... \
  /opt/fluidbuddha/backend/scripts/backup.sh
```

## 3. Restore drills

`backend/scripts/restore_drill.sh` restores the newest (or a given) copy into a
scratch database, checks the checksum, the schema revision and that the core
tables exist with data, records the result in `drills/drill-<time>.json`, and
drops the scratch database. It exits non-zero on any failure.

Run it **at least quarterly** and after any change to the backup set-up; file
the JSON record as evidence. First drill: 5 Nov 2026 on the development
database (passed in 8 s; a deliberately corrupted copy was refused).

## 4. Restoring production (runbook)

1. Declare an incident ([incident plan](incident-response-plan.md)); stop writes
   (scale the backend to zero or put the proxy in maintenance).
2. Pick the copy: the newest good one, or a point in time before the damage.
3. Check it: `restore_drill.sh <file>` with `KEEP_DRILL_DB=1` restores into a
   scratch database you can inspect.
4. Restore into a new database (`pg_restore --no-owner -d <new>`), point
   `CORTEX_DB_URL` at it, start one backend replica — migrations bring the
   schema up to date — check `/ready`, then scale out.
5. Tell customers what window of data (if any) was lost.
6. Post-incident review.

## 5. Dependencies and their failure

| Dependency | If it fails |
|---|---|
| Google Cloud Vertex AI (models, speech) | The agent can't answer; the widget shows the enquiry form / text fallback. M3-4 adds other model providers. |
| Postgres | Service down → restore (above). |
| Redis (optional) | Sessions and rate limits fall back per replica. |
| Razorpay | New payments and plan changes wait; existing service continues. |
| SMTP provider | Emails queue in the outbox and retry with backoff. |
| coturn (voice handoff) | Operators fall back to text takeover. |

## 6. People

At least two people can deploy, restore and rotate secrets. The runbooks live
in this repository so they're available offline from any clone.
