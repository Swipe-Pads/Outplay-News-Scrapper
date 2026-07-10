# Deployment — GitHub Actions + Shopify Email

The weekly digest runs entirely on GitHub Actions — no server, no local machine needed.

## How it works

Every **Monday 07:00 UTC** (09:00 Warsaw in summer) the `Weekly digest` workflow:

1. restores `data/articles.db` from the `scraper-data` branch (created automatically on first run)
2. scrapes all sources → scores articles (AI gamer-value) → composes the digest HTML
3. creates a **draft** article on the Shopify blog (`mobile-gaming-news`, blog id `126947590478`) with a branded cover image and click-worthy excerpt
4. pushes the updated DB back to `scraper-data` and uploads the digest HTML/PNG as workflow artifacts

You can also trigger it manually: **Actions → Weekly digest → Run workflow**.

## One-time setup — repository secrets

Settings → Secrets and variables → Actions → New repository secret:

| Secret | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `YOUTUBE_API_KEY` | Google Cloud console (YouTube Data API v3) |
| `REDDIT_CLIENT_ID` | reddit.com/prefs/apps |
| `REDDIT_CLIENT_SECRET` | reddit.com/prefs/apps |
| `SHOPIFY_CLIENT_ID` | Shopify Dev Dashboard → app credentials |
| `SHOPIFY_CLIENT_SECRET` | Shopify Dev Dashboard → app credentials (`shpss_…`) |

Shopify auth uses the **client credentials grant** (24h tokens exchanged at runtime) — there is no static admin token to rotate.

## Weekly human steps (~3 minutes)

1. **Review & publish the draft**: Shopify admin → Content → Blog posts → open the new draft → check → **Publish**.
2. **Send the mailing (Shopify Email)**: admin → Marketing → Create campaign → **Shopify Email** → pick the "blog post" layout → select the freshly published post → send to the *Email subscribers* segment.
   - Shopify Email is free up to 10,000 mails/month; consent and unsubscribes are handled by Shopify.
   - When the list grows, consider Klaviyo with an RSS flow (`/blogs/mobile-gaming-news.atom`) to automate this step entirely.

## Notes

- The article is always created as a **draft** (`published: false`) — nothing goes live without a human click.
- GitHub cron can start a few minutes late; irrelevant for a weekly digest.
- Costs: public repo = unlimited free minutes; a run takes ~10-15 min.
