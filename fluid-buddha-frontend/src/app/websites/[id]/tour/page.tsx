"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, TourStop } from "@/lib/api";
import { Spinner, useToast } from "@/components/ui";

type EditStop = { narration: string; moveType: "none" | "scroll" | "navigate"; target: string };

function toEdit(s: TourStop): EditStop {
  const m = (s.move || {}) as Record<string, string>;
  const type = (m.type as "scroll" | "navigate") || "none";
  return { narration: s.narration, moveType: type === "scroll" || type === "navigate" ? type : "none",
    target: type === "scroll" ? m.target || "" : type === "navigate" ? m.route || "" : "" };
}
function toStop(e: EditStop): TourStop {
  if (e.moveType === "scroll") return { narration: e.narration, move: { type: "scroll", target: e.target || "down" } };
  if (e.moveType === "navigate") return { narration: e.narration, move: { type: "navigate", route: e.target || "/" } };
  return { narration: e.narration };
}

export default function TourPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [stops, setStops] = useState<EditStop[] | null>(null);
  const [exists, setExists] = useState(false);
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState(false);

  useEffect(() => {
    Api.getTour(id)
      .then((t) => { setStops(t.stops.map(toEdit)); setExists(t.exists); })
      .catch(() => setStops([]));
  }, [id]);

  const update = (i: number, patch: Partial<EditStop>) =>
    setStops((s) => s!.map((st, j) => (j === i ? { ...st, ...patch } : st)));
  const move = (i: number, dir: -1 | 1) =>
    setStops((s) => {
      const a = [...s!]; const j = i + dir;
      if (j < 0 || j >= a.length) return a;
      [a[i], a[j]] = [a[j], a[i]]; return a;
    });
  const remove = (i: number) => setStops((s) => s!.filter((_, j) => j !== i));
  const add = () => setStops((s) => [...(s || []), { narration: "", moveType: "none", target: "" }]);

  const save = async () => {
    const clean = (stops || []).filter((s) => s.narration.trim());
    if (clean.length === 0) { toast("Add at least one stop with narration", "err"); return; }
    setBusy(true);
    try {
      await Api.saveTour(id, clean.map(toStop));
      setExists(true);
      toast("Tour saved");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save tour", "err");
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    setGen(true);
    try {
      const t = await Api.generateTour(id);
      setStops(t.stops.map(toEdit)); setExists(true);
      toast("Tour generated from your content");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Generate failed — ingest content first", "err");
    } finally {
      setGen(false);
    }
  };

  if (stops === null) return <div className="skeleton" style={{ height: 240 }} />;

  return (
    <div className="fade-in">
      <div className="row between page-head">
        <div>
          <h2>Guided tour</h2>
          <p className="muted" style={{ fontSize: "0.88rem" }}>
            What the agent says and where it moves on a visitor&apos;s first walkthrough.
            {!exists && " No tour yet — generate one or build it by hand."}
          </p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={generate} disabled={gen}>
            {gen ? <Spinner /> : "✨ Generate from content"}
          </button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>
            {busy ? <Spinner /> : "Save tour"}
          </button>
        </div>
      </div>

      <div className="stack">
        {stops.length === 0 && <div className="empty">No stops yet. Add one or generate from your content.</div>}
        {stops.map((s, i) => (
          <div key={i} className="card card-pad-sm">
            <div className="row between" style={{ marginBottom: 10 }}>
              <span className="eyebrow">Stop {i + 1}</span>
              <div className="row" style={{ gap: 4 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => move(i, -1)} disabled={i === 0}>↑</button>
                <button className="btn btn-ghost btn-sm" onClick={() => move(i, 1)} disabled={i === stops.length - 1}>↓</button>
                <button className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(i)}>✕</button>
              </div>
            </div>
            <div className="field" style={{ marginBottom: 12 }}>
              <label className="label">Narration <span className="faint">(spoken aloud)</span></label>
              <textarea className="textarea" value={s.narration} rows={2}
                onChange={(e) => update(i, { narration: e.target.value })}
                placeholder="What the agent says at this stop…" />
            </div>
            <div className="grid grid-2" style={{ gap: 12 }}>
              <div className="field">
                <label className="label">After speaking</label>
                <select className="select" value={s.moveType}
                  onChange={(e) => update(i, { moveType: e.target.value as EditStop["moveType"] })}>
                  <option value="none">Stay (no move)</option>
                  <option value="scroll">Scroll</option>
                  <option value="navigate">Navigate</option>
                </select>
              </div>
              {s.moveType !== "none" && (
                <div className="field">
                  <label className="label">{s.moveType === "scroll" ? "Direction / section" : "Route"}</label>
                  <input className="input mono" value={s.target}
                    onChange={(e) => update(i, { target: e.target.value })}
                    placeholder={s.moveType === "scroll" ? "down / top / pricing" : "/pricing"} />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <button className="btn" style={{ marginTop: 16 }} onClick={add}>+ Add stop</button>
    </div>
  );
}
