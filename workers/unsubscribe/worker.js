/**
 * SwipePads unsubscribe Worker.
 *
 * GET /?e=<email>&t=<hmac_sha256(lowercased email, UNSUB_SECRET) hex>
 *   - valid token  -> writes KV key = lowercased email (value: JSON with
 *                     timestamp) into the SUPPRESSIONS namespace and returns
 *                     a small branded HTML confirmation
 *   - invalid      -> 400
 *
 * The Python mailer (src/mailer.py: unsubscribe_token) computes the same
 * HMAC; the shared secret lives in the UNSUB_SECRET Worker secret
 * (`wrangler secret put UNSUB_SECRET`).
 *
 * Also accepts POST for RFC 8058 one-click unsubscribe
 * (List-Unsubscribe-Post: List-Unsubscribe=One-Click).
 */

const BRAND = {
  bg: "#090a12",
  card: "#1a1a25",
  text: "#f5f6fc",
  dim: "#9aa0b0",
  accent: "#0fecff",
};

function page(title, message, status = 200) {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
</head>
<body style="margin:0;padding:0;background:${BRAND.bg};font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:520px;margin:80px auto;padding:40px 32px;background:${BRAND.card};border:1px solid ${BRAND.accent};border-radius:16px;text-align:center;">
    <div style="font-size:12px;font-weight:bold;letter-spacing:4px;color:${BRAND.accent};text-transform:uppercase;">SwipePads Weekly</div>
    <h1 style="color:${BRAND.text};font-size:26px;margin:16px 0 8px;">${title}</h1>
    <p style="color:${BRAND.dim};font-size:15px;line-height:1.6;margin:0;">${message}</p>
  </div>
</body>
</html>`;
  return new Response(html, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

async function hmacHex(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(message),
  );
  return [...new Uint8Array(signature)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Constant-time-ish comparison of two hex strings. */
function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "POST") {
      return page("Method not allowed", "Use the unsubscribe link from your email.", 405);
    }

    const url = new URL(request.url);
    const email = (url.searchParams.get("e") || "").trim().toLowerCase();
    const token = (url.searchParams.get("t") || "").trim().toLowerCase();

    if (!email || !token || !email.includes("@")) {
      return page("Invalid link", "This unsubscribe link is missing or malformed.", 400);
    }

    const expected = await hmacHex(env.UNSUB_SECRET, email);
    if (!safeEqual(expected, token)) {
      return page("Invalid link", "This unsubscribe link is not valid.", 400);
    }

    await env.SUPPRESSIONS.put(
      email,
      JSON.stringify({ unsubscribed_at: new Date().toISOString() }),
    );

    return page(
      "You're unsubscribed",
      `${email} won't receive the weekly digest anymore. Changed your mind? Just subscribe again on the site.`,
    );
  },
};
