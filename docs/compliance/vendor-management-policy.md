# Vendor management policy

**Owner:** Operations lead (Privacy lead for sub-processors) · **Review:** yearly ·
**Version:** 1.0 (5 Nov 2026, draft)

## 1. Scope

Every supplier whose service we depend on to run FluidBuddha, and especially
**sub-processors**: suppliers that store or process customer data
([list](subprocessors.md)).

## 2. Before signing up

The Operations lead checks, and records in the vendor register:

- what data the supplier will get, and whether we can send less;
- their security assurance: SOC 2 Type II or ISO 27001 report, or a security
  questionnaire for smaller suppliers;
- where the data will be stored and processed (India first; anything else
  needs the Privacy lead's approval and must be allowed by our DPA);
- a data processing agreement with confidentiality, security, breach notice,
  sub-processing and deletion terms;
- how we would leave (export, deletion, alternatives).

A new sub-processor is announced to customers **30 days** before it starts
processing their data (DPA §6), and the list is updated.

## 3. Risk tiers

| Tier | Meaning | Review |
|---|---|---|
| High | Holds or processes customer data, or the service can't run without it | Yearly: new assurance report, any incidents, still needed |
| Medium | Internal tools with limited data | Every two years |
| Low | No customer data, easily replaced | When renewed |

## 4. During the relationship

- Accounts with two-factor, owned by the company (not a person's private account).
- Keys and secrets for the supplier stored encrypted / in the secret store and
  rotated when someone with access leaves.
- Supplier incidents that affect us are handled under the
  [incident plan](incident-response-plan.md).

## 5. Ending

Remove our data (request deletion confirmation), revoke keys, update the
register and the sub-processor list.

## 6. The register

Kept by the Operations lead: supplier, purpose, data, tier, location, assurance
document and date, DPA signed (date), owner, next review.
