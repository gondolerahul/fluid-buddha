"use client";

/**
 * The version switch: which world is on screen, and a one-click way to another (WebsitePlan.md §3.2,
 * "always show which version is on screen"). It sits beside the logo, in the footer and in the phone menu.
 * The label is rendered for all four worlds and shown by CSS from <html data-world>, so it never flashes.
 */
import { useEffect, useRef, useState } from "react";
import type { WorldId } from "@/content/worlds/types";
import { currentWorld, goWorld, VERSIONS, WORLD_IDS } from "@/lib/world";

const Chev = () => (
  <svg className="chev" viewBox="0 0 10 10" aria-hidden><path d="M1.5 3.5 5 7l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
);

function Options({ onPick, current }: { onPick: (id: WorldId) => void; current: WorldId }) {
  return (
    <>
      {WORLD_IDS.map((id) => (
        <button key={id} type="button" role="menuitemradio" aria-checked={id === current} className="vs-opt" onClick={() => onPick(id)}>
          <i aria-hidden />
          <b>{VERSIONS[id].label}</b>
          <small>{VERSIONS[id].line}</small>
        </button>
      ))}
    </>
  );
}

export default function VersionSwitch({ placement = "down", variant = "menu", onDone }: {
  placement?: "down" | "up"; variant?: "menu" | "list"; onDone?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<WorldId>("default");
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the world is set on <html> in the browser
    setCurrent(currentWorld());
    const mo = new MutationObserver(() => setCurrent(currentWorld()));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-world"] });
    return () => mo.disconnect();
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) { if (e.key === "Escape") { setOpen(false); box.current?.querySelector<HTMLButtonElement>(".vs-btn")?.focus(); } return; }
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  const pick = (id: WorldId) => { setOpen(false); onDone?.(); if (id !== currentWorld()) goWorld(id, "menu"); };

  if (variant === "list") {
    return <div className="vs-list" role="menu" aria-label="Choose a version of this site"><Options onPick={pick} current={current} /></div>;
  }
  return (
    <div className="vs" ref={box}>
      <button type="button" className="vs-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}
              aria-label={`Version of this site: ${VERSIONS[current].label}. Change`}>
        <span className="dot" aria-hidden />
        {WORLD_IDS.map((id) => <span key={id} className="vs-name" data-for={id}>{VERSIONS[id].label}</span>)}
        <Chev />
      </button>
      {open && (
        <div className={`vs-menu${placement === "up" ? " up" : ""}`} role="menu" aria-label="Choose a version of this site">
          <p>This site changes its look and words for you.</p>
          <Options onPick={pick} current={current} />
        </div>
      )}
    </div>
  );
}

export { Chev };
