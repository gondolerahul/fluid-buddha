# Operator guide: your steps for the Azure launch

This is the account owner's checklist for the plan in
[azure-production-plan.md](azure-production-plan.md). Engineering (Claude Code) builds the deployment and,
from your `az login`, runs the Azure steps. Some steps only you can do, because they need your accounts for
Google Cloud, Microsoft 365, GoDaddy and GitHub, or a secret only you should handle.

**How we work together**
- **Part A** has no dependency on engineering. Start now. Most of the elapsed time goes on Google key
  policies and the Microsoft 365 domain and DNS.
- **Part B onwards** follows the deployment pull request. Provisioning can start before the merge.
- **⏸ Sync** marks a point where you tell engineering something before the next step.
- **Never paste a secret into the chat**: the JSON key, client secrets, passwords, Razorpay secrets, the SSH
  private key. Secrets go straight into Key Vault (B3). Identifiers are fine to share: project ID, tenant
  and client IDs, IP addresses, resource names.

---

## Part A: do now

### A1. Azure (done by engineering)

Engineering checked from your `az login`:
- You are **Owner** on the **Pay-As-You-Go** subscription.
- Central India has vCPU quota to spare, and **Standard_B2as_v2** is offered there without restrictions.
- FluidBuddha's names (`rg-fb-prod-core`, `rg-fb-prod-data`, network `10.52.0.0/24`) don't touch anything
  else in the subscription.

Done: you confirmed **Pay-As-You-Go** (decision D11).

### A2. SSH key and your IP (5 min)

The key is for emergency access only; deployments don't use SSH.

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
```

```powershell
ssh-keygen -t ed25519 -C "fluidbuddha-prod" -f "$env:USERPROFILE\.ssh\fluidbuddha_prod"
```

- Set a passphrase when asked.
- Back up both files (`fluidbuddha_prod` and `fluidbuddha_prod.pub`) in your password manager.
- Find your public IP: search "what is my IP" in a browser. SSH will only accept this address.

⏸ **Sync:** say "key ready", and share your public IP and the email address for alerts.

### A3. Google Cloud for Vertex AI (30–60 min)

1. At console.cloud.google.com, **create a project**, for example `fluidbuddha-prod`. Note its **Project ID**,
   which may differ from the name. Link a **billing account**.
2. **Enable three APIs** (APIs & Services → Library): **Vertex AI API**, **Cloud Speech-to-Text API**,
   **Cloud Text-to-Speech API**.
3. **Create a service account** (IAM & Admin → Service Accounts → Create) named `fluidbuddha-backend`. Grant
   it three roles:
   - **Vertex AI User**
   - **Cloud Speech Client**
   - **Service Usage Consumer**
4. **Create its key:** open the service account → **Keys → Add key → Create new key → JSON**. A `.json` file
   downloads. Keep it private. It goes into Key Vault in B3, then you delete the downloaded copy.
   - If Google refuses with *"Service account key creation is disabled"*, your organisation enforces the
     policy `iam.disableServiceAccountKeyCreation`. An organisation admin can switch it off for this one
     project: **IAM & Admin → Organization Policies → "Disable service account key creation" → Manage
     policy → Override → Off**.
   - Alternatively, say so, and we switch to keyless federation from the Azure VM. That is more setup.
5. **Models.** Production uses the same models as your working local setup, in region `us-central1`:
   - `gemini-3.8-flash` (fast)
   - `gemini-4-argon` (thinking)
   - `text-embedding-004` (embeddings, 768 dimensions)
   - `gemini-3.1-flash-tts-preview` (voice)

   If any of them asks for access approval in **Vertex AI → Model Garden** for this new project, request it
   now. If you'd rather use different models, say so before launch: **the embedding model can't change after
   the first ingestion** without re-embedding everything.
6. **Budget** (Billing → Budgets & alerts): for example $100 a month for this project, alerts at 50 %, 90 %
   and 100 %.

⏸ **Sync:** share the **Project ID** (not the key) and confirm the models are available.

### A4. Microsoft 365 for email (45 min, plus DNS waiting time)

The app sends invitations, recaps, digests and alerts from `no-reply@fluidbuddha.com` through Microsoft
Graph. Microsoft is retiring password sign-in for SMTP, so there is no SMTP password: an app registration
sends as that one mailbox, and Exchange refuses it everything else.

Do all of this in **your Microsoft 365 tenant** (the one your company email lives in), as a global admin.
It is not the Azure tenant.

1. **The domain.** Microsoft 365 admin center (admin.microsoft.com) → **Settings → Domains**. If
   `fluidbuddha.com` isn't listed: **Add domain** → `fluidbuddha.com` → verify with the **TXT** record it
   shows, added at GoDaddy (A5). Then let it show the records for Exchange and add them at GoDaddy yourself:
   - **MX** for `@` (replies and bounces then reach the shared mailbox);
   - **TXT** for `@`: `v=spf1 include:spf.protection.outlook.com -all`. A domain may have only one SPF
     record: if one exists, add `include:spf.protection.outlook.com` to it;
   - the **autodiscover** CNAME, if offered.
2. **The mailbox.** Admin center → **Teams & groups → Shared mailboxes → Add a shared mailbox**: name
   `FluidBuddha`, email `no-reply@fluidbuddha.com`. Shared mailboxes need no licence.
3. **DKIM.** Microsoft Defender portal (security.microsoft.com) → **Email & collaboration → Policies & rules
   → Threat policies → Email authentication settings → DKIM** → `fluidbuddha.com` → **Create DKIM keys**. Add
   the two CNAME records it shows (`selector1._domainkey`, `selector2._domainkey`) at GoDaddy, wait for
   them to resolve, then switch **Sign messages for this domain with DKIM signatures** on.
4. **DMARC.** At GoDaddy: TXT, name `_dmarc`, value `v=DMARC1; p=none; rua=mailto:<a mailbox you read>`.
   Move to `p=quarantine` after a few weeks of clean reports.
5. **The app registration.** Microsoft Entra admin center (entra.microsoft.com), signed in to the same
   tenant → **App registrations → New registration**:
   - Name `fluidbuddha-mail`, **single tenant**, no redirect URI.
   - On its **Overview**, note the **Application (client) ID** and the **Directory (tenant) ID**.
   - **Certificates & secrets → New client secret**, valid 24 months. Copy the **Value** (shown once) straight
     into Key Vault in B3, or keep it in your password manager until then. Put the expiry date in your
     calendar.
   - **Don't add API permissions.** Exchange grants the one mailbox in the next step; a Graph `Mail.Send`
     permission here would let the app send as anyone.
   - Then open **Enterprise applications → fluidbuddha-mail** and note its **Object ID**. It differs from
     the app registration's.
6. **Limit the app to the mailbox.** In PowerShell on this machine, as an Exchange admin:

   ```powershell
   Install-Module ExchangeOnlineManagement -Scope CurrentUser
   ```

   ```powershell
   Connect-ExchangeOnline
   ```

   Smaller tenants first need Exchange customization switched on, once per tenant. If it says it's
   already on, go to the next command:

   ```powershell
   Enable-OrganizationCustomization
   ```

   It can take up to an hour to apply. Until then, the next commands answer *"The command you tried to
   run isn't currently allowed in your organization"*: wait and run them again.

   Then, with the IDs from step 5. If `New-ServicePrincipal` says the service principal already exists,
   go on to the next command:

   ```powershell
   New-ServicePrincipal -AppId "<client ID>" -ObjectId "<enterprise application object ID>" -DisplayName "FluidBuddha mail"
   ```

   ```powershell
   New-ManagementScope -Name "FluidBuddha sender" -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'no-reply@fluidbuddha.com'"
   ```

   ```powershell
   New-ManagementRoleAssignment -App "<client ID>" -Role "Application Mail.Send" -CustomResourceScope "FluidBuddha sender"
   ```

   Check it. The line for `Application Mail.Send` must say `InScope: True`:

   ```powershell
   Test-ServicePrincipalAuthorization -Identity "<client ID>" -Resource no-reply@fluidbuddha.com
   ```

   Exchange can take up to 2 hours to apply this. Until then, sending answers "403 Access denied".

⏸ **Sync:** share the **tenant ID** and **client ID** (identifiers, fine to share) and say "mail app
ready". The client secret goes only into Key Vault.

### A5. GoDaddy DNS preparation (10 min)

1. GoDaddy → **My Products → fluidbuddha.com → DNS**. Check that the **nameservers** are GoDaddy's
   (`…domaincontrol.com`). If they aren't, DNS is managed somewhere else: say so.
2. Note the current records for `@`, `www`, `app` and `gateway`. If any point to something live today, say
   so before B4.
3. Set the **TTL** of those records to **600 seconds** (Custom), so the switch-over spreads quickly.
   **Don't change their values yet.**
4. **Domain forwarding** (the Forwarding section): make sure none is set for the domain or the subdomains.
   Forwarding overrides A records.
5. If there are **CAA** records, one must allow `letsencrypt.org`. If there are none, that's fine.
6. The Microsoft 365 records from A4 (TXT, MX, SPF, DKIM, DMARC) go here too. They don't conflict with the
   A records in B4.

### A6. GitHub (10 min)

1. Repository **Settings → Environments → New environment** named `production`:
   - **Required reviewers:** yourself. Every deploy then waits for your click.
   - **Deployment branches and tags:** Selected branches → `main`.
2. **Settings → Actions → General**: allow GitHub-authored actions and verified creators (`azure/login`,
   `docker/*`). Workflow permissions can stay "read"; the Release workflow asks for what it needs.

Engineering can create the environment for you with `gh` instead: say "create it".

### A7. Decisions (2 min)

Reply in chat to D4–D11 in [the plan, §14](azure-production-plan.md#14-decisions-defaults-apply-unless-the-owner-says-otherwise).
Anything you don't answer uses the default. The main ones:
- Razorpay live keys at launch (D4)?
- "Sign in with Google" at launch (D5)?
- Launch with the website's sandbox form on its fallback message (D6)?
- Pay-As-You-Go subscription (D11)?

### A8. Optional: Docker Desktop on this machine

Start Docker Desktop if it's installed. Engineering can then build and test the images, and run the secret
scanner, locally.

---

## Part B: the deployment

### B1. Review and merge (15 min)

Engineering opens a pull request from `feature/azure-production`. Check that it's green, read the summary,
and merge it into `main`. The website work, including the water-film frames, must be merged too: Release
builds from git.

### B2. Provision Azure (15 min, engineering)

This creates everything in [plan §3](azure-production-plan.md#3-azure-resources): two resource groups, the
VM, network, firewall, static IP, Key Vault, registry, backup storage, the GitHub identities, alerts and the
budget. It can run before B1.

1. Engineering runs a preview with your SSH public key, IP and alert email, and shows you every resource it
   would create. Nothing is created yet.
2. You say yes. Engineering runs it for real, with `-SetGitHubVariables` so the GitHub repository variables
   are set too (B5).

To run it yourself instead, from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\azure\infra\provision.ps1 -SshPublicKeyPath "$env:USERPROFILE\.ssh\fluidbuddha_prod.pub" -AdminIp "<your IP>" -AlertEmail "<alert email>" -Preview
```

Leave out `-Preview` to create it. It ends by printing these outputs, none of them secret: `PUBLIC_IP`,
`PUBLIC_FQDN`, `KEY_VAULT`, `ACR_NAME`, `RESOURCE_GROUP`, `VM_NAME`, `STORAGE_ACCOUNT`,
`AZURE_BUILD_CLIENT_ID`, `AZURE_DEPLOY_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.

### B3. Put your secrets in Key Vault (20 min)

Portal → **Key vaults → `kv-fb-prod-…` → Objects → Secrets → Generate/Import**. Create each secret below.
Names must match exactly. Provisioning gave you the right to do this.

| Name | Value | Needed |
|---|---|---|
| `GOOGLE-CLOUD-PROJECT` | Your GCP Project ID (A3) | Yes |
| `VERTEX-SA-JSON` | The service-account key file. Use the command below rather than the portal box. | Yes |
| `GRAPH-TENANT-ID` | Directory (tenant) ID of your Microsoft 365 tenant (A4, step 5) | Yes |
| `GRAPH-CLIENT-ID` | Application (client) ID of `fluidbuddha-mail` | Yes |
| `GRAPH-CLIENT-SECRET` | The client secret's **Value** | Yes |
| `RAZORPAY-KEY-ID`, `RAZORPAY-KEY-SECRET`, `RAZORPAY-WEBHOOK-SECRET` | From Razorpay (Part D, step 5) | If billing at launch |
| `GOOGLE-CLIENT-ID`, `GOOGLE-CLIENT-SECRET` | From Google (Part D, step 6) | If Google sign-in |
| `SENTRY-DSN` | From sentry.io | Optional |

`ALERT-EMAIL` is already there: provisioning stored it.

The key file is easiest from PowerShell. It goes straight from your disk into the vault:

```powershell
az keyvault secret set --vault-name "<KEY_VAULT>" --name VERTEX-SA-JSON --file "$env:USERPROFILE\Downloads\<key-file>.json" --output none
```

Then delete the file from Downloads.

**Don't create** `POSTGRES-PASSWORD`, `JWT-SECRET`, `SECRETS-KEY`, `TURN-SECRET`, `METRICS-TOKEN` or
`STATUS-TOKEN`. The first deploy generates them and stores them in the vault. **Never delete or change
`SECRETS-KEY`**: it decrypts API keys stored in the database.

⏸ **Sync:** say "secrets in".

### B4. Point the domains at the VM (10 min, plus up to 1 hour to spread)

At GoDaddy DNS, using `PUBLIC_IP` from B2:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `PUBLIC_IP` | 600 s |
| A | `app` | `PUBLIC_IP` | 600 s |
| A | `gateway` | `PUBLIC_IP` | 600 s |
| CNAME | `www` | `@` (GoDaddy's default; keep it if present) | 1 hour |

Replace the existing values. If GoDaddy has a "Parked" A record on `@`, edit it to the IP. Changing `@` is
the switch-over: whatever `fluidbuddha.com` shows today stops at that moment.

Check it:

```powershell
"fluidbuddha.com","app.fluidbuddha.com","gateway.fluidbuddha.com" | ForEach-Object { Resolve-DnsName $_ -Type A -Server 8.8.8.8 }
```

All three must show `PUBLIC_IP` **before the first deploy**, so certificates can be issued.

### B5. GitHub repository variables (engineering, with B2)

Provisioning sets these under **Settings → Secrets and variables → Actions → Variables** when it runs with
`-SetGitHubVariables`. They are identifiers, not secrets:
- `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- `AZURE_BUILD_CLIENT_ID`, `AZURE_DEPLOY_CLIENT_ID`
- `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`, `ACR_NAME`

Leave `NEXT_PUBLIC_FB_KEY` for Part D.

---

## Part C: first deploy (together, about 1 hour)

1. GitHub → **Actions → Release → Run workflow**, from `main`, ref `main`. When it pauses at "production",
   click **Review deployments → Approve**.
2. Engineering watches the build and deploy, then checks:
   - certificates on all four names;
   - every `/readyz` dependency green (database, Redis, jobs, models, email);
   - the status page;
   - console sign-in;
   - a voice session;
   - the TURN relay;
   - a test email;
   - the first backup reaching Blob storage, and both restore drills.
3. You open these three pages and check they load over HTTPS:
   - https://fluidbuddha.com
   - https://app.fluidbuddha.com
   - https://gateway.fluidbuddha.com/status

---

## Part D: go live in the console (about 1 hour)

1. **Your account.** Register at `https://app.fluidbuddha.com/register`. You become the Owner of the
   FluidBuddha workspace. Turn on **two-step sign-in** under Security straight away.
2. **The website.**
   1. **Add website**: name FluidBuddha, domain `fluidbuddha.com`.
   2. Open **Ingestion → Crawl your website** with `https://fluidbuddha.com`. Wait for it to finish.
   3. Review the personas and tour.
   4. Set the design to **Level 3, "The Atmosphere"**.
   5. On **Install**, copy the key `fbk_…`.
3. **Put the agent on the site.** Add the key as the GitHub repository variable `NEXT_PUBLIC_FB_KEY`. It is
   public (it ships in the page), so a variable is fine. Then run **Release** again and approve.
4. **Test together.**
   - [ ] Ask Pragya answers from the site, with sources
   - [ ] Voice: allow the microphone, ask in English, then in Hindi
   - [ ] A lead is captured and appears in the console
   - [ ] Live inbox: from a **phone on mobile data** (not office Wi-Fi), start a chat; take it over in the console; start a **voice handoff**; both sides hear each other
   - [ ] Team → invite a second email address; the invitation arrives in the inbox, not spam
   - [ ] Status page shows all green
   - [ ] (billing) a test purchase; (Google sign-in) sign in with Google
5. **Optional: Razorpay billing.**
   1. In the Razorpay Dashboard, switch to live mode. **API Keys → Generate**: store them in Key Vault as
      `RAZORPAY-KEY-ID` and `RAZORPAY-KEY-SECRET`.
   2. **Webhooks → Add**:
      - URL: `https://gateway.fluidbuddha.com/billing/razorpay/webhook`
      - Events: all `subscription.*` events and `payment_link.paid`
      - Secret: your choice; store it as `RAZORPAY-WEBHOOK-SECRET`
   3. Run **Release** again (same commit). Secrets apply on each deploy.
6. **Optional: Sign in with Google.**
   1. In your GCP project, **APIs & Services → OAuth consent screen**: External, app name FluidBuddha,
      authorised domain `fluidbuddha.com`. Publish it.
   2. **Credentials → Create credentials → OAuth client ID → Web application**, with authorised redirect URI
      `https://gateway.fluidbuddha.com/auth/sso/callback`.
   3. Store `GOOGLE-CLIENT-ID` and `GOOGLE-CLIENT-SECRET` in Key Vault, then run **Release** again.

---

## Part E: the first weeks

- **Uptime monitors.** A free UptimeRobot or Better Stack account, 5-minute checks, alerts to email or phone:
  - `https://fluidbuddha.com`
  - `https://app.fluidbuddha.com/login`
  - `https://gateway.fluidbuddha.com/readyz`
- **Calendar reminders:**
  - a monthly restore drill (engineering runs it, you approve);
  - the `fluidbuddha-mail` client-secret expiry (A4). Make a new secret a week before, put it in Key Vault
    as `GRAPH-CLIENT-SECRET`, run Release with the current commit, then delete the old secret in Entra;
  - the yearly domain renewal at GoDaddy.
- **After 2–4 weeks:** buy a 1-year reservation for the VM size (Portal → Reservations), once usage confirms
  the size. That is about a third off the VM.
- **If your IP changes** and SSH is needed: Portal → `nsg-fb-prod-app` → Inbound rules → `ssh-operator` →
  update the source, or ask engineering to re-run provisioning with the new `-AdminIp`.
- **Applying a changed secret:** edit it in Key Vault, then run Release with the current commit.

---

## Quick reference

| What | Where |
|---|---|
| Marketing site | https://fluidbuddha.com |
| Console | https://app.fluidbuddha.com |
| API, status page | https://gateway.fluidbuddha.com, https://gateway.fluidbuddha.com/status |
| Azure resources | `rg-fb-prod-core` (VM, network, registry) and `rg-fb-prod-data` (Key Vault, backups), Central India, Pay-As-You-Go |
| Secrets | Key Vault `kv-fb-prod-…` |
| Deploy, roll back | GitHub → Actions → Release (an older commit rolls back) |
| Backups | Storage account `stfbprodbk…`, container `backups` |
| Email | Microsoft 365, shared mailbox `no-reply@fluidbuddha.com`, app `fluidbuddha-mail` |
| How to operate it | [azure-runbook.md](azure-runbook.md) |
