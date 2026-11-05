// A tenant's own component in a sandboxed iframe (M2-8).
//
// The URL comes from the site's registration (the server puts it in the
// state; the agent only supplies props). The frame runs scripts but is
// otherwise locked down: no same-origin access, no top navigation, no forms,
// no popups, no referrer. The only conversation is a fixed postMessage
// contract, checked by the sender being this frame:
//
//   widget → frame   {type: "fb:init", props}            once loaded
//   frame → widget   {type: "fb:resize", height}         80–800 px
//   frame → widget   {type: "fb:state", state}           ≤ 2 kB of JSON, passed to the agent
//
// Anything else is ignored.

import { RenderContext } from './interactive';

const MIN_H = 80;
const MAX_H = 800;
const MAX_STATE = 2000;

/** Apply one message from the frame (exported for the contract test). */
export function embedMessage(frame: HTMLIFrameElement, data: unknown, ctx?: RenderContext): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as { type?: unknown; height?: unknown; state?: unknown };
  if (d.type === 'fb:resize' && typeof d.height === 'number' && isFinite(d.height)) {
    frame.style.height = `${Math.round(Math.min(MAX_H, Math.max(MIN_H, d.height)))}px`;
    return true;
  }
  if (d.type === 'fb:state' && d.state && typeof d.state === 'object' && !Array.isArray(d.state)) {
    let size = Infinity;
    try {
      size = JSON.stringify(d.state).length;
    } catch {
      /* not serialisable */
    }
    if (size > MAX_STATE) return false;
    ctx?.reportState?.({ state: d.state as Record<string, unknown> });
    return true;
  }
  return false;
}

export function buildEmbed(state: Record<string, unknown>, ctx?: RenderContext): HTMLElement {
  const wrap = document.createElement('div');
  wrap.className = 'embed';
  const src = String(state.src || '');
  if (!/^https:\/\/[^\s"'<>]+$/.test(src)) {
    wrap.className = 'empty';
    return wrap;
  }
  const frame = document.createElement('iframe');
  frame.setAttribute('sandbox', 'allow-scripts');
  frame.setAttribute('referrerpolicy', 'no-referrer');
  frame.setAttribute('loading', 'lazy');
  frame.title = String(state.name || 'component');
  frame.style.cssText = `width:100%;height:240px;border:0;border-radius:10px;background:transparent`;
  frame.src = src;
  const props = state.props && typeof state.props === 'object' ? state.props : {};
  frame.addEventListener('load', () => {
    // The sandboxed frame's origin is opaque ("null"), so '*' is the only
    // target that reaches it; props are not secret.
    frame.contentWindow?.postMessage({ type: 'fb:init', props }, '*');
  });
  const onMessage = (e: MessageEvent) => {
    if (!frame.isConnected) {
      window.removeEventListener('message', onMessage);
      return;
    }
    if (e.source !== frame.contentWindow) return;
    embedMessage(frame, e.data, ctx);
  };
  window.addEventListener('message', onMessage);
  wrap.append(frame);
  return wrap;
}
