"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/lib/auth";
import { Api, ApiError, BillingPlan, BillingSummary, CheckoutResult } from "@/lib/api";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Spinner, fmtUSD, useToast } from "@/components/ui";

const CHECKOUT_JS = "https://checkout.razorpay.com/v1/checkout.js";

type RazorpayResponse = {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
};
type RazorpayCtor = new (opts: Record<string, unknown>) => {
  open: () => void;
  on: (event: string, cb: (r: { error?: { description?: string } }) => void) => void;
};

/** Load Razorpay Checkout once, on demand. */
function loadCheckout(): Promise<RazorpayCtor> {
  const w = window as unknown as { Razorpay?: RazorpayCtor };
  if (w.Razorpay) return Promise.resolve(w.Razorpay);
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = CHECKOUT_JS;
    s.async = true;
    s.onload = () => (w.Razorpay ? resolve(w.Razorpay) : reject(new Error("Checkout didn't load")));
    s.onerror = () => reject(new Error("Couldn't reach Razorpay Checkout"));
    document.head.appendChild(s);
  });
}

/** A billing date, without the time of day. */
const day = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

const STATUS: Record<string, { label: string; tone: string }> = {
  none: { label: "", tone: "" },
  created: { label: "Awaiting payment", tone: "warn" },
  authenticated: { label: "Active", tone: "ok" },
  active: { label: "Active", tone: "ok" },
  pending: { label: "Payment retrying", tone: "warn" },
  halted: { label: "Payment failed", tone: "err" },
  cancelled: { label: "Cancelled", tone: "" },
  completed: { label: "Ended", tone: "" },
  expired: { label: "Expired", tone: "" },
  manual: { label: "Arranged", tone: "ok" },
};

export default function BillingPage() {
  const auth = useRequireAuth();
  const toast = useToast();
  const [data, setData] = useState<BillingSummary | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => Api.billing().then(setData).catch(() => {}), []);
  useEffect(() => { if (auth.tenant) load(); }, [auth.tenant, load]);

  if (auth.loading || !auth.tenant) return <LoadingScreen />;

  const cur = data?.currency ?? "INR";
  const money = (minor: number) => new Intl.NumberFormat(cur === "INR" ? "en-IN" : undefined, {
    style: "currency", currency: cur,
    maximumFractionDigits: minor % 100 === 0 ? 0 : 2,
  }).format(minor / 100);

  const choose = async (plan: BillingPlan) => {
    setBusy(plan.key);
    try {
      const r = await Api.checkout(plan.key);
      if (r.action === "changed") {
        toast(r.effective === "now" ? `Switched to ${plan.name}` : `${plan.name} starts at your next renewal`);
        await load();
        return;
      }
      await pay(r, plan);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not start checkout", "err");
    } finally {
      setBusy(null);
    }
  };

  const pay = async (r: Extract<CheckoutResult, { action: "checkout" }>, plan: BillingPlan) => {
    const Razorpay = await loadCheckout();
    await new Promise<void>((done) => {
      const rzp = new Razorpay({
        key: r.key_id,
        subscription_id: r.subscription_id,
        name: "FluidBuddha",
        description: r.scheduled_for
          ? `${plan.name} plan, from ${day(r.scheduled_for)}`
          : `${plan.name} plan`,
        prefill: { email: r.email, name: r.name },
        theme: { color: "#ffd23f" },
        handler: async (resp: RazorpayResponse) => {
          try {
            setData(await Api.verifyPayment(resp));
            toast(r.scheduled_for ? `${plan.name} starts on ${day(r.scheduled_for)}`
              : `You're on ${plan.name}`);
          } catch (e) {
            toast(e instanceof ApiError ? e.message : "Payment received; confirming shortly", "err");
            load();
          }
          done();
        },
        modal: { ondismiss: () => { load(); done(); } },
      });
      rzp.on("payment.failed", (f) => toast(f.error?.description || "The payment didn't go through", "err"));
      rzp.open();
    });
  };

  const cancel = async () => {
    if (!window.confirm("Cancel your subscription? You keep your plan until the end of this billing period, then move to Free"
      + (data?.next ? " (the scheduled plan change is withdrawn too)." : "."))) return;
    setBusy("cancel");
    try {
      setData(await Api.cancelSubscription());
      toast("Subscription will end at the close of this period");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not cancel", "err");
    } finally {
      setBusy(null);
    }
  };

  const current = data?.catalog.find((p) => p.key === data.plan);
  const st = STATUS[data?.status ?? "none"] ?? { label: data?.status ?? "", tone: "" };
  const u = data?.usage;
  const pctUsed = u && u.included ? Math.min(100, (u.conversations / u.included) * 100) : 0;
  const paid = data && data.plan !== "free";
  const next = data?.next ?? null;
  const nextPlan = next ? data?.catalog.find((p) => p.key === next.plan) : undefined;
  const switchApproved = !!next && (next.status === "authenticated" || next.status === "active");

  return (
    <>
      <AppHeader />
      <main className="content stack" style={{ margin: "0 auto" }}>
        <div className="page-head">
          <h1 className="h-page">Billing</h1>
          <p className="muted">Your plan covers every website on this account. A conversation is one
            visitor session the agent answered.</p>
        </div>

        {!data ? <div className="skeleton" style={{ height: 220 }} /> : (
          <>
            <section className="card">
              <div className="row between wrap" style={{ gap: 12 }}>
                <div>
                  <span className="eyebrow">Current plan</span>
                  <div className="row" style={{ gap: 10, marginTop: 6, alignItems: "baseline" }}>
                    <span style={{ fontSize: "1.5rem", fontWeight: 600 }}>{current?.name ?? data.plan}</span>
                    {st.label && <span className={`badge ${st.tone}`}>{st.label}</span>}
                  </div>
                  <p className="muted" style={{ fontSize: "0.86rem", marginTop: 6 }}>
                    {paid ? "Billing period" : "This month"}: {day(data.period.start)} – {day(data.period.end)}
                  </p>
                  {data.cancel_at_cycle_end && !switchApproved && (
                    <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
                      Ends at the close of this period, then Free.</p>
                  )}
                  {next && switchApproved && (
                    <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
                      Moves to {nextPlan?.name}{data.next?.starts_at ? ` on ${day(data.next.starts_at)}` : " at your next renewal"}
                      {" — its payment is approved."}</p>
                  )}
                  {next && !switchApproved && nextPlan && (
                    <div className="notice warn row between wrap" style={{ marginTop: 8, gap: 10 }}>
                      <span>Approve the new plan&apos;s payment in Razorpay to move to {nextPlan.name}
                        {data.next?.starts_at ? ` on ${day(data.next.starts_at)}` : " at your next renewal"}.</span>
                      <button className="btn btn-primary btn-sm" disabled={busy !== null}
                        onClick={() => choose(nextPlan)}>
                        {busy === nextPlan.key ? <Spinner /> : "Approve in Razorpay"}</button>
                    </div>
                  )}
                  {data.pending_plan && !data.cancel_at_cycle_end && (
                    <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
                      Moves to {data.catalog.find((p) => p.key === data.pending_plan)?.name} at your next renewal.</p>
                  )}
                  {data.status === "halted" && (
                    <div className="notice err" style={{ marginTop: 8 }}>
                      Razorpay couldn&apos;t collect the last payment, so the account is on Free limits.
                      Choose a plan below to subscribe again.</div>
                  )}
                </div>
                {paid && (!data.cancel_at_cycle_end || switchApproved) && (
                  <button className="btn btn-sm btn-danger" onClick={cancel} disabled={busy !== null}>
                    {busy === "cancel" ? <Spinner /> : "Cancel subscription"}</button>
                )}
              </div>

              {u && (
                <div style={{ marginTop: 18 }}>
                  <div className="row between" style={{ fontSize: "0.88rem", marginBottom: 6 }}>
                    <span><strong>{u.conversations.toLocaleString()}</strong>
                      {u.included != null ? ` of ${u.included.toLocaleString()} conversations` : " conversations"}</span>
                    {u.extra > 0 && <span className="muted">{u.extra.toLocaleString()} extra · {money(u.overage_amount)} on your next invoice</span>}
                  </div>
                  {u.included != null && (
                    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pctUsed)}
                      aria-label="Conversations used this period"
                      style={{ height: 8, borderRadius: 4, background: "var(--line)", overflow: "hidden" }}>
                      <div style={{ width: `${pctUsed}%`, height: "100%", borderRadius: 4,
                        background: u.limit_reached ? "var(--err)" : pctUsed > 80 ? "var(--warn)" : "var(--accent)" }} />
                    </div>
                  )}
                  {u.limit_reached && (
                    <div className="notice err" style={{ marginTop: 10 }}>
                      The Free allowance is used up: the agent isn&apos;t starting new conversations on your
                      websites until next month. Upgrade to keep it answering.</div>
                  )}
                </div>
              )}
            </section>

            <section>
              <h3 style={{ marginBottom: 12 }}>Plans</h3>
              {!data.checkout_enabled && (
                <div className="notice warn" style={{ marginBottom: 12 }}>
                  Payments aren&apos;t set up on this server yet (Razorpay keys missing), so plans can&apos;t be bought here.</div>
              )}
              <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 14 }}>
                {data.catalog.map((p) => {
                  const isCurrent = p.key === data.plan && (!data.cancel_at_cycle_end || switchApproved);
                  const isNext = switchApproved && p.key === next?.plan;
                  return (
                    <div key={p.key} className="card card-pad-sm stack-sm"
                      style={isCurrent ? { borderColor: "rgba(255,210,63,0.45)" } : undefined}>
                      <div className="eyebrow">{p.name}</div>
                      <div style={{ fontSize: "1.4rem", fontWeight: 600 }}>
                        {p.self_serve ? (p.price ? <>{money(p.price)}<span className="muted" style={{ fontSize: "0.85rem", fontWeight: 400 }}> / month</span></> : "Free")
                          : "Custom"}
                      </div>
                      <div className="muted" style={{ fontSize: "0.86rem" }}>
                        {p.included != null ? `${p.included.toLocaleString()} conversations a month` : "Volume to fit"}
                      </div>
                      <div className="faint" style={{ fontSize: "0.8rem", minHeight: 18 }}>
                        {p.overage != null ? `then ${money(p.overage)} each` : p.included != null ? "Stops at the limit" : "Invoiced by arrangement"}
                      </div>
                      <div style={{ marginTop: 6 }}>
                        {isCurrent ? <span className="badge accent">Current plan</span>
                          : isNext ? <span className="badge ok">Starts {next?.starts_at ? day(next.starts_at) : "at renewal"}</span>
                          : p.key === "free" ? null
                          : !p.self_serve ? <span className="muted" style={{ fontSize: "0.84rem" }}>Talk to us</span>
                          : (
                            <button className="btn btn-primary btn-sm" disabled={!data.checkout_enabled || busy !== null}
                              onClick={() => choose(p)}>
                              {busy === p.key ? <Spinner /> : paid ? `Switch to ${p.name}` : `Choose ${p.name}`}
                            </button>
                          )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="faint" style={{ fontSize: "0.78rem", marginTop: 8 }}>
                Payments are handled by Razorpay. Paying by card, upgrades start now and smaller plans at your next renewal; with UPI Autopay, any change starts at your next renewal.
              </p>
            </section>

            <section className="card">
              <h3 style={{ marginBottom: 12 }}>This period by website</h3>
              {data.sites.length === 0 ? <div className="empty">No websites yet.</div> : (
                <table className="table">
                  <thead><tr><th>Website</th><th>Conversations</th><th>Turns</th><th>Our cost</th><th>Per conversation</th></tr></thead>
                  <tbody>
                    {data.sites.map((s) => (
                      <tr key={s.website_id}>
                        <td><Link href={`/websites/${s.website_id}/analytics`}>{s.name}</Link></td>
                        <td>{s.conversations.toLocaleString()}</td>
                        <td>{s.turns.toLocaleString()}</td>
                        <td className="mono">{fmtUSD(s.cost_usd)}</td>
                        <td className="mono">{s.cost_per_conversation_usd == null ? "—" : fmtUSD(s.cost_per_conversation_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="faint" style={{ fontSize: "0.78rem", marginTop: 8 }}>
                Our cost is what the AI models and voice cost to serve those conversations (USD).
              </p>
            </section>

            {data.overage_history.length > 0 && (
              <section className="card">
                <h3 style={{ marginBottom: 12 }}>Extra conversations billed</h3>
                <table className="table">
                  <thead><tr><th>Period</th><th>Conversations</th><th>Extra</th><th>Amount</th><th>Status</th></tr></thead>
                  <tbody>
                    {data.overage_history.map((o) => (
                      <tr key={o.period_start}>
                        <td>{day(o.period_start)} – {day(o.period_end)}</td>
                        <td>{o.conversations.toLocaleString()}</td>
                        <td>{o.extra.toLocaleString()}</td>
                        <td className="mono">{money(o.amount)}</td>
                        <td>{o.status === "nothing" ? <span className="faint">Nothing extra</span>
                          : o.status === "addon" ? <span className="badge ok">On next invoice</span>
                          : o.status === "paid" ? <span className="badge ok">Paid</span>
                          : o.status === "link" && o.payment_link_url ? (
                            <a className="btn btn-primary btn-sm" href={o.payment_link_url}
                              target="_blank" rel="noopener noreferrer">Pay now</a>
                          ) : <span className="badge warn">Being billed</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}
          </>
        )}
      </main>
    </>
  );
}
