"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRequireAuth } from "@/lib/auth";
import { API_BASE, Api, ApiError, LiveConversation, LiveLine, LiveSession, getCsrf } from "@/lib/api";
import { OperatorCall } from "@/lib/operatorCall";
import { useQueryParam } from "@/lib/location";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Spinner, useToast } from "@/components/ui";

type LiveEvent = Record<string, unknown> & { type: string; session_id?: string };
type Selected = { wid: string; sid: string };

const EVENTS_URL = `${API_BASE.replace(/^http/, "ws")}/tenant/live/events`;

function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 60 ? `${s}s` : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`;
}

export default function LivePage() {
  const auth = useRequireAuth();
  const toast = useToast();
  const wanted = useQueryParam("session");
  const [sessions, setSessions] = useState<LiveSession[] | null>(null);
  const [connected, setConnected] = useState(false);
  const [picked, setSelected] = useState<Selected | null>(null);
  const [conv, setConv] = useState<LiveConversation | null>(null);
  const [call, setCall] = useState<"idle" | "ringing" | "connected">("idle");
  const callRef = useRef<OperatorCall | null>(null);
  const selectedRef = useRef<Selected | null>(null);
  const handlerRef = useRef<(ev: LiveEvent) => void>(() => {});

  // A ?session= link (e.g. from a hot-lead alert) opens that conversation.
  const linked = !picked && wanted ? sessions?.find((x) => x.session_id === wanted) : undefined;
  const selWid = picked?.wid ?? linked?.website_id;
  const selSid = picked?.sid ?? linked?.session_id;
  const selected: Selected | null = selWid && selSid ? { wid: selWid, sid: selSid } : null;

  const refreshList = useCallback(() => { Api.live().then(setSessions).catch(() => {}); }, []);

  const append = useCallback((sid: string, lines: LiveLine[]) => {
    if (selectedRef.current?.sid !== sid) return;
    setConv((c) => {
      if (!c) return c;
      const known = new Set(c.events.filter((e) => e.id != null).map((e) => e.id));
      return { ...c, events: [...c.events, ...lines.filter((l) => l.id == null || !known.has(l.id))] };
    });
  }, []);

  // Event handling lives in a ref so the socket (opened once) always sees the latest state.
  useEffect(() => {
    selectedRef.current = selWid && selSid ? { wid: selWid, sid: selSid } : null;
    handlerRef.current = (ev: LiveEvent) => {
      const sid = ev.session_id ?? "";
      const now = new Date().toISOString();
      switch (ev.type) {
        case "snapshot":
          setSessions(ev.sessions as LiveSession[]);
          break;
        case "visitor_joined":
        case "takeover_started":
        case "takeover_ended":
          refreshList();
          if (selectedRef.current?.sid === sid && ev.type !== "visitor_joined") {
            const sel = selectedRef.current;
            Api.liveConversation(sel.wid, sel.sid).then(setConv).catch(() => {});
            if (ev.type === "takeover_ended") callRef.current?.hangup(false, "The conversation was handed back.");
          }
          break;
        case "visitor_left":
          setSessions((list) => list?.filter((s) => s.session_id !== sid) ?? list);
          if (selectedRef.current?.sid === sid) {
            setConv((c) => (c ? { ...c, live: false } : c));
            callRef.current?.hangup(false, "The visitor left.");
          }
          break;
        case "agent_turn":
          setSessions((list) => list?.map((s) => s.session_id === sid
            ? { ...s, last_question: String(ev.question), turns: s.turns + 1 } : s) ?? list);
          append(sid, [{ sender: "visitor", text: String(ev.question), at: now },
            { sender: "agent", text: String(ev.answer), at: now }]);
          break;
        case "visitor_message":
        case "operator_message": {
          const m = ev.message as LiveLine;
          if (ev.type === "visitor_message")
            setSessions((list) => list?.map((s) => s.session_id === sid ? { ...s, last_question: m.text } : s) ?? list);
          append(sid, [m]);
          break;
        }
        case "call_answer":
          if (callRef.current?.sessionId === sid) void callRef.current.answered(String(ev.sdp));
          break;
        case "call_ice":
          if (callRef.current?.sessionId === sid) void callRef.current.ice(ev.candidate as RTCIceCandidateInit);
          break;
        case "call_decline":
          if (callRef.current?.sessionId === sid) callRef.current.hangup(false, "The visitor declined the call.");
          break;
        case "call_hangup":
          if (callRef.current?.sessionId === sid) callRef.current.hangup(false, "The visitor hung up.");
          break;
      }
    };
  }, [selWid, selSid, refreshList, append]);

  // One event socket for the page; reconnects if dropped.
  useEffect(() => {
    if (!auth.tenant) return;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let ws: WebSocket | null = null;
    const open = () => {
      ws = new WebSocket(EVENTS_URL);
      ws.onopen = () => {
        ws?.send(JSON.stringify({ csrf: getCsrf() }));
        setConnected(true);
      };
      ws.onmessage = (e) => {
        try {
          handlerRef.current(JSON.parse(e.data));
        } catch { /* ignore a malformed event */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(open, 3000);
      };
    };
    open();
    return () => {
      closed = true;
      clearTimeout(retry);
      ws?.close();
    };
  }, [auth.tenant]);

  // Load the selected conversation.
  useEffect(() => {
    if (!selWid || !selSid) return;
    let live = true;
    Api.liveConversation(selWid, selSid).then((c) => { if (live) setConv(c); }).catch(() => {});
    return () => { live = false; };
  }, [selWid, selSid]);

  if (auth.loading || !auth.tenant) return <LoadingScreen />;
  const me = auth.tenant.user?.id;
  const current = sessions?.find((s) => s.session_id === selected?.sid) ?? null;
  const holder = conv?.takeover ?? null;
  const mine = !!holder && holder.operator_user_id === me;

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    try {
      await fn();
      if (ok) toast(ok);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong", "err");
    }
  };

  const startCall = async () => {
    if (!selected) return;
    const c = new OperatorCall(selected.wid, selected.sid,
      (why) => { callRef.current = null; setCall("idle"); toast(why); },
      () => setCall("connected"));
    callRef.current = c;
    setCall("ringing");
    try {
      await c.start();
    } catch (e) {
      c.hangup(false, e instanceof ApiError ? e.message : "Your microphone isn't available.");
    }
  };

  return (
    <>
      <AppHeader />
      <main className="content" style={{ margin: "0 auto" }}>
        <div className="row between wrap page-head" style={{ gap: 12 }}>
          <div>
            <h1 className="h-page">Live</h1>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              Visitors talking to your agent right now. Take over a conversation to answer in person, or
              call them by voice.
            </p>
          </div>
          <span className={`badge ${connected ? "ok" : ""}`}><span className="dot" />{connected ? "live" : "connecting…"}</span>
        </div>

        <div className="grid" style={{ gridTemplateColumns: "minmax(260px, 340px) 1fr", gap: 16, alignItems: "start" }}>
          <section className="card card-pad-sm" aria-label="Live visitors">
            {!sessions ? <div className="skeleton" style={{ height: 160 }} />
              : sessions.length === 0 ? <div className="empty">Nobody is talking to your agent right now.</div>
              : sessions.map((s) => (
                <button key={s.session_id} type="button" onClick={() => setSelected({ wid: s.website_id, sid: s.session_id })}
                  className="card card-pad-sm" style={{ width: "100%", textAlign: "left", marginBottom: 8, cursor: "pointer",
                    color: "inherit", font: "inherit",
                    borderColor: selected?.sid === s.session_id ? "var(--accent)" : undefined }}>
                  <div className="row between" style={{ gap: 6 }}>
                    <strong style={{ fontSize: "0.9rem" }}>{s.website_name}</strong>
                    <span className="faint" style={{ fontSize: "0.76rem" }}>{ago(s.started_at)}</span>
                  </div>
                  <div className="row wrap" style={{ gap: 6, marginTop: 4 }}>
                    <span className="badge">{s.channel}</span>
                    {s.hot && <span className="badge err">hot lead {s.lead_score}</span>}
                    {s.persona && <span className="badge">{s.persona}</span>}
                    {s.takeover && <span className="badge ok">{s.takeover.operator_name}</span>}
                  </div>
                  <div className="muted" style={{ fontSize: "0.82rem", marginTop: 6, overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {s.last_question ?? (s.page ? `on ${s.page}` : "just arrived")}
                  </div>
                </button>
              ))}
          </section>

          <section className="card" aria-label="Conversation">
            {!selected ? <div className="empty">Pick a visitor to see the conversation.</div>
              : !conv ? <div className="skeleton" style={{ height: 240 }} /> : (
                <>
                  <div className="row between wrap" style={{ gap: 8, marginBottom: 12 }}>
                    <div>
                      <strong>{current?.website_name ?? "Conversation"}</strong>
                      <div className="faint" style={{ fontSize: "0.8rem" }}>
                        {current?.channel === "voice" ? "Voice" : "Text"}{current?.page ? ` · on ${current.page}` : ""}
                        {current?.persona ? ` · ${current.persona}` : ""}{!conv.live ? " · left the site" : ""}
                      </div>
                    </div>
                    <div className="row" style={{ gap: 8 }}>
                      {!holder && conv.live && auth.can("editor") && (
                        <button className="btn btn-primary btn-sm"
                          onClick={() => act(() => Api.takeOver(selected.wid, selected.sid), "You've taken over")}>Take over</button>
                      )}
                      {mine && conv.live && current?.channel === "voice" && (call === "idle"
                        ? <button className="btn btn-sm" onClick={startCall}>Call by voice</button>
                        : <button className="btn btn-danger btn-sm" onClick={() => callRef.current?.hangup(true)}>
                            {call === "ringing" ? "Cancel call" : "Hang up"}</button>)}
                      {holder && (mine || auth.can("admin")) && (
                        <button className="btn btn-sm" onClick={() => act(async () => {
                          callRef.current?.hangup(true);
                          await Api.releaseLive(selected.wid, selected.sid);
                        }, "Handed back to the agent")}>Hand back</button>
                      )}
                    </div>
                  </div>
                  {holder && !mine && <div className="notice" style={{ marginBottom: 10 }}>{holder.operator_name} has this conversation.</div>}
                  {call !== "idle" && <div className="notice" style={{ marginBottom: 10 }}>
                    {call === "ringing" ? <><Spinner /> Calling — waiting for the visitor to accept…</> : "On a call with the visitor."}</div>}
                  <Timeline lines={conv.events} />
                  {mine && conv.live && <Composer onSend={(text) => act(async () => {
                    const m = await Api.sendLive(selected.wid, selected.sid, text);
                    append(selected.sid, [m]);
                  })} />}
                </>
              )}
          </section>
        </div>
      </main>
    </>
  );
}

function Timeline({ lines }: { lines: LiveLine[] }) {
  const end = useRef<HTMLDivElement | null>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [lines.length]);
  return (
    <div className="stack" style={{ gap: 8, maxHeight: 460, overflowY: "auto", paddingRight: 4 }}>
      {lines.length === 0 && <div className="empty">No messages yet.</div>}
      {lines.map((l, i) => l.sender === "system" ? (
        <div key={l.id ?? i} className="faint" style={{ fontSize: "0.78rem", textAlign: "center" }}>{l.text}</div>
      ) : (
        <div key={l.id ?? i} style={{ alignSelf: l.sender === "visitor" ? "flex-start" : "flex-end", maxWidth: "80%" }}>
          <div className="faint" style={{ fontSize: "0.72rem", marginBottom: 2,
            textAlign: l.sender === "visitor" ? "left" : "right" }}>
            {l.sender === "visitor" ? "Visitor" : l.sender === "agent" ? "Agent" : (l.author ?? "You")}
          </div>
          <div style={{ padding: "8px 12px", borderRadius: 12, fontSize: "0.88rem", lineHeight: 1.45,
            background: l.sender === "visitor" ? "var(--bg-elev)" : l.sender === "agent" ? "rgba(255,255,255,0.06)" : "var(--accent-soft)",
            border: "1px solid var(--line)" }}>{l.text}</div>
        </div>
      ))}
      <div ref={end} />
    </div>
  );
}

function Composer({ onSend }: { onSend: (text: string) => Promise<void> }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form className="row" style={{ gap: 8, marginTop: 12 }} onSubmit={async (e) => {
      e.preventDefault();
      if (!text.trim()) return;
      setBusy(true);
      await onSend(text.trim());
      setText("");
      setBusy(false);
    }}>
      <input className="input" value={text} onChange={(e) => setText(e.target.value)}
        placeholder="Write to the visitor…" aria-label="Message to the visitor" autoFocus />
      <button className="btn btn-primary" disabled={busy || !text.trim()}>{busy ? <Spinner /> : "Send"}</button>
    </form>
  );
}
