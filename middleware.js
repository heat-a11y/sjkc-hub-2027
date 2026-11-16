// Vercel Edge Middleware — the WHOLE auth lives here (no separate /api/login
// function, which avoids Vercel function-routing conflicts in static projects).
//
//  - Unauthenticated visitor -> redirected to /login.html (PII page never served)
//  - POST /api/login {password} -> validates server-side, sets HttpOnly HMAC
//    session cookie, then redirects into the app
//  - Authenticated visitor -> request passes through to the app
//
// Edge runtime: Web Crypto only (crypto.subtle), no Node 'crypto'.

export const config = {
  matcher: ["/", "/index.html", "/api/login", "/login.html"],
};

// ---------- HMAC session helpers (Web Crypto) ----------
async function sign(payload) {
  const secret = (process.env.AUTH_SECRET || "").trim();
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function validSession(cookies) {
  const raw = cookies["pmsite_session"];
  if (!raw) return false;
  const dot = raw.lastIndexOf(".");
  if (dot <= 0) return false;
  const expStr = raw.slice(0, dot);
  const sig = raw.slice(dot + 1);
  const exp = parseInt(expStr, 10);
  if (!exp || exp < Date.now()) return false; // expired
  const expected = await sign(expStr);
  if (expected.length !== sig.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0;
}

function parseCookies(req) {
  const cookies = {};
  const header = req.headers.get("cookie") || "";
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq > 0) cookies[part.slice(0, eq).trim()] = part.slice(eq + 1).trim();
  }
  return cookies;
}

// ---------- Main middleware ----------
export default async function middleware(req) {
  const url = new URL(req.url);
  const cookies = parseCookies(req);
  const sitePassword = (process.env.SITE_PASSWORD || "").trim();

  // If no SITE_PASSWORD is configured in env, allow direct access out-of-the-box
  if (!sitePassword) {
    return undefined;
  }

  // --- The login page itself always loads (no PII on it) ---
  if (url.pathname === "/login.html") {
    return undefined;
  }

  // --- Login submission ----------
  if (url.pathname === "/api/login") {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed" }), {
        status: 405, headers: { "Content-Type": "application/json" },
      });
    }
    let body = {};
    try { body = await req.json(); } catch {}
    if (sitePassword && body.password === sitePassword) {
      const exp = Date.now() + 12 * 3600 * 1000;
      const token = `${exp}.${await sign(String(exp))}`;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Set-Cookie": `pmsite_session=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${12 * 3600}`,
        },
      });
    }
    return new Response(JSON.stringify({ error: "Incorrect password" }), {
      status: 401, headers: { "Content-Type": "application/json" },
    });
  }

  // --- Everything else: require a valid session ---
  if (await validSession(cookies)) {
    return undefined; // authed -> serve the app (with the PII data)
  }

  // Not authed -> never send the page; bounce to login
  return new Response(null, {
    status: 307,
    headers: { Location: "/login.html" },
  });
}
