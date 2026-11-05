# Incident response plan

**Owner:** Security lead · **Review:** yearly and after every SEV-1/SEV-2 ·
**Version:** 1.0 (5 Nov 2026, draft)

## 1. What counts as an incident

Anything that harms, or could harm, the confidentiality, integrity or
availability of customer data or the service: a breach or suspected breach, a
leaked secret, one customer seeing another's data, the agent saying something
harmful at scale, an outage, data loss, a compromised staff account or device,
a supplier's incident that affects us.

Report it at once to the Security lead (and the security channel). When in
doubt, report.

## 2. Severity

| Level | Examples | Response |
|---|---|---|
| **SEV-1** | Confirmed breach of customer data; cross-account data exposure; full outage; leaked production secret | Immediately, around the clock; leadership informed within 1 hour |
| **SEV-2** | Suspected breach; partial outage (voice down, widget failing for some sites); a security vulnerability being exploited | Within 1 hour in working hours, 4 hours otherwise |
| **SEV-3** | Vulnerability not exploited; degraded performance; a single customer's issue | Next working day |

## 3. Roles

- **Incident lead** (Security lead by default): runs the response, decides, communicates.
- **Technical lead** (Engineering or Operations lead): investigates and fixes.
- **Communications** (Privacy lead for data incidents): customers, regulators, suppliers.

## 4. Steps

1. **Detect and log.** Open an incident record: time, who reported, what is known.
   Sources: alerts (Prometheus metrics, Sentry), customer reports, the audit
   log, CI secret scanning, a supplier's notice.
2. **Contain.** Typical moves, all available today:
   - rotate a widget key (console) or revoke sessions (`/auth/sessions/revoke-others`, removing a member);
   - rotate `JWT_SECRET` (ends every session) or add a new `SECRETS_KEY`;
   - disable an action, an integration or a website; lower the spend cap;
   - block an origin at the proxy; scale down a misbehaving component.
3. **Investigate.** Preserve evidence first (logs with request ids, audit
   events, database snapshot). Find the cause, the time window, the accounts
   and data affected.
4. **Fix and recover.** Through the normal change process, or the emergency
   path ([change management](change-management-policy.md) §5). Restore data
   from backup if needed ([continuity](business-continuity.md)).
5. **Notify** (data incidents):
   - affected customers **without undue delay and within 72 hours** of becoming
     aware, with what happened, what data, what we've done, what they should do;
   - India: CERT-In within **6 hours** for reportable cyber incidents (CERT-In
     directions, April 2022); the Data Protection Board and affected people as
     the DPDP Act 2023 and its rules require;
   - customers are responsible for notifying their own visitors where they are
     the controller; we support them (see the [DPA](dpa-template.md)).
6. **Review.** Within 5 working days of a SEV-1/2: a blameless post-incident
   review with timeline, cause, what worked, and actions with owners and dates.
   Actions are tracked to completion; the risk register is updated.

## 5. Contacts

Keep this list current (and somewhere reachable when the main systems are down):
Security lead, Engineering lead, Operations lead, Privacy lead, Leadership;
hosting provider support; Razorpay; SMTP provider; Google Cloud; CERT-In
(incident@cert-in.org.in); legal counsel.

## 6. Testing

A tabletop exercise at least yearly (for example: a leaked `SECRETS_KEY`, or a
customer reporting another account's leads in their console), recorded with
findings.
