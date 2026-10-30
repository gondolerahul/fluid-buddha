// Renders a flowchart with sequential node reveal (in sync with the spoken
// explanation, Req 3.5.2) using the shared incremental-reveal helper.

import { revealSequence } from './reveal';

interface FlowNode { id?: string; label?: string }
interface FlowEdge { from?: string; to?: string }

export function buildFlowchart(state: Record<string, unknown>): HTMLElement {
  const nodes = (state.nodes as FlowNode[] | undefined) ?? [];
  const edges = (state.edges as FlowEdge[] | undefined) ?? [];

  const root = document.createElement('div');
  root.className = 'flow';
  if (nodes.length === 0) {
    root.innerHTML = '<div class="empty">No diagram data.</div>';
    return root;
  }

  const revealed: HTMLElement[] = [];
  nodes.forEach((node, i) => {
    const n = document.createElement('div');
    n.className = 'flow-node';
    n.textContent = node.label ?? `Node ${i + 1}`;
    root.appendChild(n);
    revealed.push(n);
    if (i < nodes.length - 1) {
      const edge = document.createElement('div');
      edge.className = 'flow-edge';
      edge.textContent = '↓';
      root.appendChild(edge);
      revealed.push(edge);
    }
  });
  revealSequence(revealed, { stepMs: 250 });

  if (edges.length > 0) {
    const meta = document.createElement('div');
    meta.className = 'caption';
    meta.style.marginTop = '8px';
    meta.textContent = `${edges.length} connections`;
    root.appendChild(meta);
  }
  return root;
}
