# FluidBuddha compliance pack

Policies, plans and the SOC 2 control matrix for FluidBuddha (M2-11). They
describe what the product and the team actually do, and point to the code,
configuration and records that prove it.

**Status:** drafts written with the M2-11 controls, 5 November 2026. Before
relying on them with a customer or an auditor:

1. Fill in the named people for each role in the table below.
2. Have the policies approved by leadership and the DPA reviewed by a lawyer.
3. Start collecting the evidence listed in the [control matrix](control-matrix.md).
   SOC 2 Type I looks at the design on one date; Type II at 3–12 months of the
   controls operating.

| Document | What it covers |
|---|---|
| [Information security policy](information-security-policy.md) | The umbrella policy: scope, roles, principles, review cycle |
| [Access control policy](access-control-policy.md) | Accounts, roles, two-factor, sessions, reviews, joiners/leavers |
| [Change management policy](change-management-policy.md) | Branches, review, CI gates, migrations, releases, emergency fixes |
| [Incident response plan](incident-response-plan.md) | Severity, roles, the steps, customer and regulator notice |
| [Business continuity and disaster recovery](business-continuity.md) | Backups, restore drills, RPO/RTO, dependencies |
| [Vendor management policy](vendor-management-policy.md) | Choosing and reviewing suppliers |
| [Sub-processors](subprocessors.md) | Who processes customer data for us, and where |
| [Data classification and retention](data-classification-retention.md) | Data types, how each is protected, how long it's kept |
| [Acceptable use policy](acceptable-use-policy.md) | Rules for staff and contractors |
| [Risk assessment](risk-assessment.md) | Method and the current risk register |
| [Data processing agreement (template)](dpa-template.md) | The DPA we sign with customers |
| [SOC 2 control matrix](control-matrix.md) | Each Trust Services Criterion → control → owner → policy → evidence |

## Roles

The policies name roles, not people, so they survive team changes.

| Role | Responsibilities | Person |
|---|---|---|
| **Security lead** | Owns this pack, the risk register, incident response, access reviews | _to fill_ |
| **Engineering lead** | Change management, CI, dependencies, backups and restores | _to fill_ |
| **Operations lead** | Production infrastructure, monitoring, vendor accounts | _to fill_ |
| **Privacy lead** | DPA, sub-processors, data subject requests, retention | _to fill_ |
| **Leadership** | Approves policies yearly, accepts residual risks | _to fill_ |

In a small team one person holds several roles; the separation that matters for
SOC 2 is that a change to production is reviewed by someone other than its
author (see [change management](change-management-policy.md)).

## Review

Every document is reviewed at least yearly and after a significant change (new
product area, new sub-processor, a serious incident). The review is recorded in
the document's change log and in the [control matrix](control-matrix.md).
