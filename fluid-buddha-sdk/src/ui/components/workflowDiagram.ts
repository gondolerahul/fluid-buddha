// Workflow diagram — a horizontal, left-to-right flow of steps (wrapping) with
// arrow connectors and distinct shapes for start/decision/end nodes. Distinct
// from the (vertical) flowchart; both reveal incrementally (Req 3.5.2).

import { revealSequence } from './reveal';

interface WorkflowStep {
  id?: string;
  label?: string;
  type?: 'start' | 'process' | 'decision' | 'end';
}

export interface WorkflowState {
  steps?: WorkflowStep[];
  /** Optional branch labels between steps, e.g. {from, to, label:"yes"}. */
  transitions?: { from?: string; to?: string; label?: string }[];
}

export function buildWorkflowDiagram(state: Record<string, unknown>): HTMLElement {
  const steps = (state.steps as WorkflowStep[] | undefined) ?? [];
  const transitions =
    (state.transitions as WorkflowState['transitions'] | undefined) ?? [];

  const root = document.createElement('div');
  root.className = 'wf';
  if (steps.length === 0) {
    root.innerHTML = '<div class="empty">No workflow data.</div>';
    return root;
  }

  const labelFor = (from?: string, to?: string): string =>
    transitions.find((t) => t.from === from && t.to === to)?.label ?? '';

  const revealed: HTMLElement[] = [];
  steps.forEach((step, i) => {
    const node = document.createElement('div');
    node.className = `wf-node wf-${step.type ?? 'process'}`;
    node.textContent = step.label ?? `Step ${i + 1}`;
    root.appendChild(node);
    revealed.push(node);
    if (i < steps.length - 1) {
      const arrow = document.createElement('div');
      arrow.className = 'wf-arrow';
      const branch = labelFor(step.id, steps[i + 1].id);
      arrow.textContent = branch ? `${branch} →` : '→';
      root.appendChild(arrow);
      revealed.push(arrow);
    }
  });
  revealSequence(revealed, { stepMs: 250 });
  return root;
}
