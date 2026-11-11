"use client";

/**
 * "Your pages change for the kind of visitor": one page, three visitors. Choosing a visitor
 * rearranges the same approved blocks (a FLIP animation: each block moves from where it was to where
 * it now belongs), and the product's own "Why this?" line says why.
 */
import { useLayoutEffect, useRef, useState } from "react";

type BlockId = "hero" | "pricing" | "security" | "proof" | "resume" | "cta";
const BLOCK: Record<BlockId, { label: string; lines: number }> = {
  hero: { label: "Your hero", lines: 2 },
  pricing: { label: "Pricing", lines: 3 },
  security: { label: "Security", lines: 3 },
  proof: { label: "How it is measured", lines: 2 },
  resume: { label: "Where you left off", lines: 2 },
  cta: { label: "Book a demo", lines: 0 },
};
const WHY: Record<string, string> = {
  pricing: "Why this? You came from a pricing ad.",
  security: "Why this? You arrived from a security search.",
  back: "Why this? You came back and chose “Remember me”.",
};

export default function FitDemo({ states }: { states: { id: string; label: string; line: string; order: BlockId[] }[] }) {
  const [cur, setCur] = useState(states[0].id);
  const refs = useRef(new Map<BlockId, HTMLDivElement>());
  const before = useRef(new Map<BlockId, DOMRect>());
  const state = states.find((s) => s.id === cur) ?? states[0];

  const pick = (id: string) => {
    if (id === cur) return;
    refs.current.forEach((el, k) => before.current.set(k, el.getBoundingClientRect()));
    setCur(id);
  };

  useLayoutEffect(() => {
    if (!before.current.size) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    refs.current.forEach((el, k) => {
      const was = before.current.get(k), now = el.getBoundingClientRect();
      if (reduced) return;
      if (!was) { el.animate([{ opacity: 0, transform: "scale(.96)" }, { opacity: 1, transform: "none" }], { duration: 520, easing: "cubic-bezier(.22,1,.36,1)" }); return; }
      const dy = was.top - now.top;
      if (Math.abs(dy) > 1) el.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 720, easing: "cubic-bezier(.22,1,.36,1)" });
    });
    before.current.clear();
  }, [cur]);

  return (
    <div className="fit">
      <div className="fit-tabs" role="tablist" aria-label="Choose a visitor">
        {states.map((s) => (
          <button key={s.id} type="button" role="tab" aria-selected={s.id === cur} onClick={() => pick(s.id)}>
            <b>{s.label}</b><span>{s.line}</span>
          </button>
        ))}
      </div>
      <div className="fit-page ui-frame" role="tabpanel" aria-label={`The page for: ${state.label}`}>
        <div className="fit-chrome" aria-hidden><i /><i /><i /><span>yourcompany.com</span></div>
        <div className="fit-blocks">
          {state.order.map((id, i) => (
            <div key={id} ref={(el) => { if (el) refs.current.set(id, el); else refs.current.delete(id); }} className={`fit-b fit-${id}${i === 0 ? " first" : ""}`}>
              <b>{BLOCK[id].label}</b>
              {Array.from({ length: BLOCK[id].lines }, (_, k) => <span key={k} className="ln" style={{ width: `${88 - k * 17}%` }} />)}
            </div>
          ))}
        </div>
        <p className="fit-why">{WHY[state.id]}</p>
      </div>
    </div>
  );
}
