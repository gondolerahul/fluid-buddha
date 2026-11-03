"use client";
import { useEffect, useState } from "react";
import { Api, Conversation } from "@/lib/api";
import { Modal, Spinner } from "@/components/ui";

/** A visitor conversation, turn by turn, with the sources behind each answer. */
export function TranscriptModal({ id, cid, onClose }: { id: string; cid: string; onClose: () => void }) {
  const [conv, setConv] = useState<Conversation | null>(null);
  useEffect(() => { Api.conversation(id, cid).then(setConv).catch(() => {}); }, [id, cid]);
  return (
    <Modal open onClose={onClose} title="Transcript">
      {!conv ? <Spinner /> : (
        <div className="stack">
          {conv.transcript.map((t, i) => (
            <div key={i} className="stack-sm">
              <div><span className="eyebrow">Visitor</span><div>{t.question}</div></div>
              <div>
                <span className="eyebrow">Agent{t.served_from_cache ? " · cached" : ""}</span>
                <div className="muted">{t.answer}</div>
                {t.found && t.sources.length > 0 && (
                  <div className="faint" style={{ fontSize: "0.8rem", marginTop: 4 }}>
                    Sources: {t.sources.map((s) => s.label || s.document).join(", ")}
                  </div>
                )}
                {t.unanswered && <span className="badge warn" style={{ marginTop: 6 }}>Not in your content</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
