/**
 * Sandbox preview gateway (WebsiteConcept.md §10.1).
 * Validates the request, then forwards it to the sandbox preview service in the product backend
 * (SANDBOX_API_URL). Until that service is deployed, it answers 503 with a clear message.
 */
const FREE_MAIL = /@(gmail|yahoo|outlook|hotmail|icloud|proton|rediffmail|live)\./i;

export async function POST(request: Request) {
  let body: { site?: string; email?: string };
  try { body = await request.json(); } catch { return Response.json({ message: "Invalid request." }, { status: 400 }); }
  const site = (body.site ?? "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/[/?#].*$/, "");
  const email = (body.email ?? "").trim();
  const emailDomain = email.split("@")[1]?.toLowerCase() ?? "";
  if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(site)) return Response.json({ message: "Please enter a valid website address." }, { status: 400 });
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return Response.json({ message: "Please enter a valid email." }, { status: 400 });
  const free = FREE_MAIL.test(email);
  if (!free && !(emailDomain === site || emailDomain.endsWith("." + site) || site.endsWith("." + emailDomain)))
    return Response.json({ message: `Your email should be on ${site}.` }, { status: 400 });

  const upstream = process.env.SANDBOX_API_URL;
  if (!upstream) {
    return Response.json(
      { message: "The live preview service is being connected. Leave your details on the Book a demo page and we'll send your preview as soon as it's ready." },
      { status: 503 },
    );
  }
  const r = await fetch(`${upstream.replace(/\/$/, "")}/sandbox/start`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ site, email, pages: free ? 3 : 8 }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) return Response.json({ message: j.message ?? "The preview service couldn't start your preview." }, { status: r.status });
  return Response.json({ message: j.message ?? `We've sent a one-time code to ${email}. Enter it to start reading ${site}.` });
}
