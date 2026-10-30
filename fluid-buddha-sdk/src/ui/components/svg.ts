// Tiny namespaced-SVG helper for the diagram/chart renderers. The LLM never
// emits raw markup — these build safe SVG nodes from typed JSON state.

export const SVG_NS = 'http://www.w3.org/2000/svg';

export function svgNode<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs?: Record<string, string | number>,
  text?: string,
): SVGElementTagNameMap[K] {
  const n = document.createElementNS(SVG_NS, tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (text != null) n.textContent = text;
  return n;
}

/** A root <svg> with a viewBox; scales responsively to the card width. */
export function svgRoot(width: number, height: number): SVGSVGElement {
  const svg = svgNode('svg', {
    viewBox: `0 0 ${width} ${height}`,
    width: '100%',
    preserveAspectRatio: 'xMidYMid meet',
  });
  svg.setAttribute('role', 'img');
  return svg;
}

/**
 * Append the shared "liquid glass" gradients + glow filter to an <svg> so the
 * diagram/chart renderers all read as frosted, lit glass rather than flat fills.
 * Idempotent per <svg>. Stop colours pull the live `--fb-accent` through inline
 * styles so theming still flows from :host.
 *
 *  - url(#fbGlassFill)  : a vertical frosted-white sheen (neutral surfaces)
 *  - url(#fbAccentFill) : an accent-tinted glass (charts / highlighted nodes)
 *  - url(#fbEdge)       : a bright top edge → dim bottom (the rim light)
 *  - url(#fbGlow)       : a soft outer glow / drop shadow
 */
export function ensureGlassDefs(svg: SVGSVGElement): void {
  if (svg.querySelector('defs.fb-glass-defs')) return;
  const defs = svgNode('defs');
  defs.setAttribute('class', 'fb-glass-defs');

  const grad = (
    id: string,
    stops: { offset: string; style: string }[],
    vertical = true,
  ): SVGLinearGradientElement => {
    const g = svgNode('linearGradient', {
      id,
      x1: '0', y1: '0', x2: vertical ? '0' : '1', y2: vertical ? '1' : '0',
    });
    for (const s of stops) {
      const st = svgNode('stop', { offset: s.offset });
      st.setAttribute('style', s.style);
      g.appendChild(st);
    }
    return g;
  };

  defs.appendChild(grad('fbGlassFill', [
    { offset: '0%', style: 'stop-color:#ffffff;stop-opacity:0.20' },
    { offset: '48%', style: 'stop-color:#ffffff;stop-opacity:0.06' },
    { offset: '100%', style: 'stop-color:#ffffff;stop-opacity:0.02' },
  ]));
  defs.appendChild(grad('fbAccentFill', [
    { offset: '0%', style: 'stop-color:var(--fb-accent);stop-opacity:0.55' },
    { offset: '100%', style: 'stop-color:var(--fb-accent);stop-opacity:0.14' },
  ]));
  defs.appendChild(grad('fbEdge', [
    { offset: '0%', style: 'stop-color:#ffffff;stop-opacity:0.65' },
    { offset: '55%', style: 'stop-color:#ffffff;stop-opacity:0.16' },
    { offset: '100%', style: 'stop-color:#ffffff;stop-opacity:0.05' },
  ]));

  // Soft outer glow so glass elements feel lit and lifted off the surface.
  const glow = svgNode('filter', {
    id: 'fbGlow', x: '-40%', y: '-40%', width: '180%', height: '180%',
  });
  const blur = svgNode('feDropShadow', {
    dx: '0', dy: '1.5', stdDeviation: '3.2', 'flood-color': '#000000',
    'flood-opacity': '0.45',
  });
  glow.appendChild(blur);
  defs.appendChild(glow);

  svg.insertBefore(defs, svg.firstChild);
}
