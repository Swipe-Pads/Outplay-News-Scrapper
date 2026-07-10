# Weekly digest mailing — setup guide

The weekly digest is mailed to Shopify subscribers via **Cloudflare Email
Service** (public beta since Apr 2026). One personalized email per recipient
(individual HMAC unsubscribe links), throttled, with a KV-backed suppression
list maintained by an unsubscribe Worker.

Docs used (fetched 2026-07-10):
- Send REST API: <https://developers.cloudflare.com/email-service/api/send-emails/rest-api/>
- Named addresses: <https://developers.cloudflare.com/email-service/examples/email-sending/recipients/>
- Limits (50 rcpt/msg, 5 MiB): <https://developers.cloudflare.com/email-service/platform/limits/>
- Domain setup: <https://developers.cloudflare.com/email-service/configuration/domains/>
- KV REST API: <https://developers.cloudflare.com/api/resources/kv/>

## How the flow works (publish gates mailing)

1. **Monday ~09:00** — the `weekly-digest.yml` workflow creates a **draft**
   blog post on Shopify; a human reviews and **publishes** it in Shopify Admin.
2. **Monday 13:00 UTC** — the `weekly-mailing.yml` workflow runs
   `python -m src.pipeline --send-mailing`:
   - fetches the latest **published** article from blog `SHOPIFY_BLOG_ID`;
   - gates: `published_at` within the last **5 days** AND article id **not**
     in `data/mailed.json` (restored from the `scraper-data` branch);
   - fetches subscribers (Shopify GraphQL, `emailMarketingConsent.marketingState == SUBSCRIBED`);
   - drops addresses present in the KV suppression list (unsubscribes);
   - sends one email per recipient via Cloudflare Email Service
     (subject = article title, throttled at `MAIL_RATE_PER_SEC`, default 5/s,
     retry with backoff on 429/5xx);
   - records the article id in `data/mailed.json` and persists it back to the
     `scraper-data` branch.
3. If the human never publishes, the gate fails and **nothing is sent** —
   publishing the post is the "go" button for the mailing.

Local dry-run (no sends): `python -m src.pipeline --mailing-dry-run`

## One-time setup

### 1. Cloudflare Email Service — sending domain

In the Cloudflare dashboard (zone `outplay.game`):
1. Email Service → **Set up Email Sending** for subdomain `mail.outplay.game`
   (Email Sending requires a Workers Paid plan while in beta).
2. Add the DNS records Cloudflare generates (SPF, DKIM, DMARC, MX/return-path)
   — automatic when the zone is on Cloudflare.
3. Wait for the domain to show **verified**, then send a test from the
   dashboard. Sender address: `digest@mail.outplay.game` (`MAIL_FROM`).

### 2. Cloudflare API token

Create a token (My Profile → API Tokens → Create Token) with:
- **Email Sending: Send** (account-scoped) — for the send endpoint
- **Workers KV Storage: Read** (account-scoped) — for the suppression list

This is `CF_EMAIL_API_TOKEN`. `CF_ACCOUNT_ID` is on the dashboard right rail.

### 3. Unsubscribe Worker + KV namespace

```bash
cd workers/unsubscribe
npx wrangler kv namespace create SUPPRESSIONS   # copy the id it prints
# paste the id into wrangler.toml ([[kv_namespaces]].id) — it is also KV_NAMESPACE_ID
npx wrangler secret put UNSUB_SECRET            # any long random string
npx wrangler deploy
```

The deployed Worker URL (workers.dev or a custom route like
`https://unsub.outplay.game`) is `UNSUBSCRIBE_BASE_URL`.

Link format the mailer generates:
`{UNSUBSCRIBE_BASE_URL}?e=<email>&t=<hex hmac_sha256(lowercased email, UNSUB_SECRET)>`
The Worker verifies the HMAC, writes KV key = lowercased email, and shows a
branded confirmation page. Invalid token → 400. The same URL is also sent in
`List-Unsubscribe` / `List-Unsubscribe-Post` headers (RFC 8058 one-click).

**The `UNSUB_SECRET` Worker secret and the mailer's `UNSUB_SECRET` env var
must be identical.**

### 4. GitHub Actions secrets

Repo → Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `CF_ACCOUNT_ID` | Cloudflare account id |
| `CF_EMAIL_API_TOKEN` | token from step 2 |
| `KV_NAMESPACE_ID` | id from step 3 |
| `UNSUB_SECRET` | same string as the Worker secret |
| `UNSUBSCRIBE_BASE_URL` | deployed Worker URL |
| `MAIL_FROM` | `digest@mail.outplay.game` |
| `SHOPIFY_CLIENT_ID` | already set for weekly-digest |
| `SHOPIFY_CLIENT_SECRET` | already set for weekly-digest |

(`SHOPIFY_STORE_DOMAIN` and `SHOPIFY_BLOG_ID` are plain env values in the
workflow file.) The Shopify app additionally needs the `read_customers`
scope for the subscriber GraphQL query.

### 5. Footer address

Replace `PHYSICAL_ADDRESS_PLACEHOLDER` in `src/email_template.py` with the
real company postal address (CAN-SPAM/GDPR requirement) before the first
real send.

## Operational notes

- **Suppression is best-effort at send time**: if KV is unreachable the run
  logs a warning and continues; unsubscribes are honored on the next run.
  Cloudflare additionally auto-suppresses hard bounces and spam complaints
  on their side (<https://developers.cloudflare.com/email-service/concepts/suppressions/>).
- **Quota**: new Email Service accounts start with a conservative daily send
  quota that scales with good deliverability; request an increase via the
  form linked from the Limits page if the subscriber list outgrows it.
- **Re-running**: `data/mailed.json` dedupes per article id — re-running the
  workflow the same week is a no-op unless a new post was published.
