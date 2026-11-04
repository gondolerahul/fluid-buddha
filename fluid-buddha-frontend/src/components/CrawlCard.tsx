"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Api, ApiError, CrawlJob, DesignInfo } from "@/lib/api";
import { useWebsite } from "@/components/WebsiteContext";
import { Spinner, useToast } from "@/components/ui";

const PHASES: Array<[CrawlJob["phase"], string]> = [
  ["crawling", "Reading pages"],
  ["ingesting", "Teaching the agent"],
  ["personas", "Finding your audiences"],
  ["design", "Matching your brand"],
];

function fmtDuration(s: number | null): string {
  if (s == null) return "";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return m ? `${m}m ${sec}s` : `${sec}s`;
}

/** Paste a URL → the site is crawled, ingested, and given personas and brand
 *  tokens (WS9). Polls the job while it runs. */
export function CrawlCard({ id, onIngested }: { id: string; onIngested: () => void }) {
  const { website, reload } = useWebsite();
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [pages, setPages] = useState(25);
  const [depth, setDepth] = useState(2);
  const [job, setJob] = useState<CrawlJob | null>(null);
  const [design, setDesign] = useState<DesignInfo | null>(null);
  const [starting, setStarting] = useState(false);
  const [touched, setTouched] = useState(false);
  const [tick, setTick] = useState(0);
  const lastStatus = useRef<string | null>(null);

  // Fetch the latest job whenever `tick` changes; reload the sources and the
  // design once a running job finishes.
  useEffect(() => {
    let alive = true;
    Api.latestCrawl(id)
      .then((j) => {
        if (!alive) return;
        setJob(j);
        if (j?.status === "done") {
          if (lastStatus.current === "running") onIngested();
          Api.getDesign(id).then(setDesign).catch(() => {});
        }
        lastStatus.current = j?.status ?? null;
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [id, tick, onIngested]);

  // Poll while the job runs.
  useEffect(() => {
    if (job?.status !== "running") return;
    const t = setTimeout(() => setTick((n) => n + 1), 1500);
    return () => clearTimeout(t);
  }, [job]);

  const shownUrl = touched ? url : website?.domain ? `https://${website.domain}` : "";

  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setStarting(true);
    try {
      const j = await Api.startCrawl(id, { url: shownUrl.trim() || undefined, max_pages: pages, max_depth: depth });
      lastStatus.current = "running";
      setJob(j);
      setDesign(null);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not start the crawl", "err");
    } finally {
      setStarting(false);
    }
  };

  const applyAccent = async (color: string) => {
    try {
      await Api.updateWebsite(id, { accent: color });
      reload();
      toast("Widget accent updated");
    } catch {
      toast("Could not update the accent", "err");
    }
  };

  const running = job?.status === "running";
  const phaseIdx = job ? PHASES.findIndex(([p]) => p === job.phase) : -1;
  const colors = design?.extracted?.colors ?? {};

  return (
    <section className="card" style={{ marginBottom: 22 }}>
      <div className="row between" style={{ alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div style={{ maxWidth: 520 }}>
          <h2>Crawl your website</h2>
          <p className="muted" style={{ fontSize: "0.86rem" }}>
            Paste your site&apos;s address. We read its pages (respecting robots.txt), teach them to the
            agent, and pick up your audiences and brand colours.
          </p>
        </div>
      </div>

      <form onSubmit={start} className="row" style={{ gap: 8, marginTop: 14, flexWrap: "wrap" }}>
        <input className="input" style={{ flex: "1 1 280px" }} value={shownUrl} required
          onChange={(e) => { setTouched(true); setUrl(e.target.value); }}
          placeholder="https://www.example.com" aria-label="Website address" disabled={running} />
        <select className="select" style={{ width: "auto" }} value={pages} disabled={running}
          onChange={(e) => setPages(Number(e.target.value))} aria-label="Pages to read">
          {[10, 25, 50].map((n) => <option key={n} value={n}>Up to {n} pages</option>)}
        </select>
        <select className="select" style={{ width: "auto" }} value={depth} disabled={running}
          onChange={(e) => setDepth(Number(e.target.value))} aria-label="Link depth">
          <option value={1}>1 click deep</option>
          <option value={2}>2 clicks deep</option>
          <option value={3}>3 clicks deep</option>
        </select>
        <button className="btn btn-primary" disabled={running || starting}>
          {running || starting ? <Spinner /> : job ? "Crawl again" : "Crawl site"}
        </button>
      </form>

      {job && (
        <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
          {running && (
            <div className="row" style={{ gap: 18, flexWrap: "wrap", fontSize: "0.86rem" }} aria-live="polite">
              {PHASES.map(([p, label], i) => (
                <span key={p} className={i < phaseIdx ? "muted" : i === phaseIdx ? "" : "faint"}>
                  {i < phaseIdx ? "✓ " : i === phaseIdx ? "● " : "○ "}{label}
                  {p === "crawling" && i === phaseIdx && job.pages_found ? ` (${job.pages_found})` : ""}
                </span>
              ))}
            </div>
          )}

          {job.status === "failed" && (
            <div className="notice err">Crawl failed: {job.error || "unknown error"}</div>
          )}

          {job.status === "done" && (
            <div className="stack-sm">
              <div style={{ fontSize: "0.92rem" }}>
                <strong>Your agent is ready</strong>{" "}
                <span className="muted">
                  — {job.pages_ingested} page{job.pages_ingested === 1 ? "" : "s"} learned in{" "}
                  {fmtDuration(job.duration_s)}
                  {job.pages_skipped ? ` · ${job.pages_skipped} skipped` : ""}
                </span>
              </div>
              <div className="faint" style={{ fontSize: "0.8rem" }}>{job.start_url}</div>
              <div className="row" style={{ gap: 10, flexWrap: "wrap", fontSize: "0.86rem" }}>
                {job.personas_added > 0 ? (
                  <Link href={`/websites/${id}/settings`} className="badge accent">
                    {job.personas_added} audience{job.personas_added === 1 ? "" : "s"} found — review
                  </Link>
                ) : (
                  <span className="badge">Audiences: kept yours, or none found</span>
                )}
              </div>
              {Object.keys(colors).length > 0 && (
                <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                  <span className="muted" style={{ fontSize: "0.84rem" }}>Brand colours:</span>
                  {Object.entries(colors).map(([role, c]) => (
                    <button key={role} type="button" className="btn btn-ghost btn-sm"
                      onClick={() => applyAccent(c)} title={`Use ${c} as the widget accent`}
                      style={{ gap: 6 }}>
                      <span style={{ width: 14, height: 14, borderRadius: 4, background: c,
                        border: "1px solid var(--border)", display: "inline-block" }} />
                      {role}
                      {website?.accent?.toLowerCase() === c.toLowerCase() && <span className="faint"> ✓</span>}
                    </button>
                  ))}
                </div>
              )}
              <div>
                <Link className="btn btn-primary btn-sm" href={`/websites/${id}/install#preview`}>
                  Preview on your site →
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
