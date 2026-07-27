/**
 * SwipePads newsletter-inbox Worker.
 *
 * Receives emails routed to the news.outplay.game subdomain (Cloudflare
 * Email Routing catch-all rule -> this Worker) and stores the raw MIME
 * message in the NEWSLETTERS KV namespace. The Python scraper reads and
 * parses these in the weekly digest run (src/sources/newsletter.py).
 *
 * KV layout:
 *   key       nl:<received ISO date>:<random hex>   (sortable by date)
 *   value     raw MIME message (headers + body)
 *   metadata  { from, to, subject, date }           (for cheap list-only scans)
 *   TTL       30 days — KV is a buffer, not an archive; the digest run
 *             consumes mails well within the window and the article DB is
 *             the system of record.
 */

const TTL_SECONDS = 30 * 24 * 60 * 60;

/** Trim a header to keep total KV metadata under its 1024-byte limit. */
function clip(value, max = 200) {
  return (value || "").slice(0, max);
}

export default {
  async email(message, env, ctx) {
    const raw = await new Response(message.raw).arrayBuffer();

    const received = new Date().toISOString();
    const id = crypto.randomUUID().slice(0, 8);
    const key = `nl:${received}:${id}`;

    await env.NEWSLETTERS.put(key, raw, {
      expirationTtl: TTL_SECONDS,
      metadata: {
        from: clip(message.from),
        to: clip(message.to),
        subject: clip(message.headers.get("subject")),
        date: clip(message.headers.get("date"), 64),
      },
    });
  },
};
